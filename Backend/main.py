# main.py
from fastapi import FastAPI, UploadFile, Form, HTTPException, Response, Body
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO
from docx import Document
import google.generativeai as genai
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen.canvas import Canvas 

import json
import re
import pdfplumber
from dotenv import load_dotenv
import os
from typing import List, Optional
import uuid
import zipfile
import asyncio
import random
import logging
import traceback # For better error logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create uploads and rubrics directories if they don't exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("rubrics", exist_ok=True)

# Initialize FastAPI app
app = FastAPI()

# Get allowed origins from environment or use defaults
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
origins = allowed_origins.split(",")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ['*'] else ["*"], # Use configured origins or allow all if '*'
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Allowed file types
ALLOWED_TYPES = {
    'application/pdf',
    'text/plain',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

# Default rubric
DEFAULT_RUBRIC = """
Standard Academic Essay Evaluation Rubric:

1. Thesis & Argument (0-10):
   - Clear, specific thesis statement
   - Well-developed argument with logical progression
   - Strong supporting evidence

2. Organization & Structure (0-10):
   - Effective introduction and conclusion
   - Clear paragraph structure with topic sentences
   - Smooth transitions between ideas

3. Evidence & Analysis (0-10):
   - Relevant, specific evidence supporting claims
   - Thoughtful analysis of evidence
   - Consideration of counterarguments

4. Writing Style & Clarity (0-10):
   - Clear, concise prose
   - Appropriate academic tone
   - Varied sentence structure

5. Grammar & Mechanics (0-10):
   - Correct grammar, spelling, and punctuation
   - Proper citation format
   - Appropriate word choice
"""

# In-memory storage for multi-essay PDF generation (simple approach)
# Consider a more robust solution (e.g., Redis, temporary file storage) for production
evaluation_storage = {}

# Essay Processing Functions
async def extract_text(file: UploadFile) -> str:
    """Extract text from uploaded files (PDF, TXT, DOCX)."""
    logger.info(f"Attempting to extract text from file: '{file.filename}' (Type: {file.content_type})")
    content = await file.read()
    if not content:
        logger.warning(f"File '{file.filename}' is empty.")
        raise ValueError(f"Cannot read an empty file: '{file.filename}'.")

    filename = file.filename.lower() if file.filename else ""

    try:
        # Handle TXT files
        if file.content_type == 'text/plain' or filename.endswith('.txt'):
            logger.info(f"Extracting text from TXT: {file.filename}")
            try:
                return content.decode('utf-8')
            except UnicodeDecodeError:
                logger.warning(f"UTF-8 decoding failed for {file.filename}, trying latin-1.")
                try:
                    return content.decode('latin-1')
                except UnicodeDecodeError:
                    logger.error(f"Failed to decode TXT file '{file.filename}'. Unsupported encoding.")
                    raise ValueError(f"Failed to decode TXT file '{file.filename}'. Encoding not supported.")

        # Handle PDF files
        elif file.content_type == 'application/pdf' or filename.endswith('.pdf'):
            logger.info(f"Extracting text from PDF: {file.filename}")
            try:
                with pdfplumber.open(BytesIO(content)) as pdf:
                    text = '\n'.join([page.extract_text() or '' for page in pdf.pages])
                    if not text.strip():
                        logger.warning(f"Extracted text from PDF '{file.filename}' is empty or contains only whitespace.")
                    return text
            except Exception as e:
                logger.error(f"Error extracting text from PDF '{file.filename}': {str(e)}")
                raise ValueError(f"Failed to extract text from PDF '{file.filename}': {str(e)}")

        # Handle DOCX files
        elif file.content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or filename.endswith('.docx'):
            logger.info(f"Extracting text from DOCX: {file.filename}")
            try:
                with BytesIO(content) as doc_file:
                    doc = Document(doc_file)
                    text = '\n'.join([para.text for para in doc.paragraphs])
                    if not text.strip():
                         logger.warning(f"Extracted text from DOCX '{file.filename}' is empty or contains only whitespace.")
                    return text
            except Exception as e:
                logger.error(f"Error extracting text from DOCX '{file.filename}': {str(e)}")
                raise ValueError(f"Failed to extract text from DOCX '{file.filename}': {str(e)}")

        else:
            logger.error(f"Unsupported file format: {file.content_type} for file '{file.filename}'")
            raise ValueError(f"Unsupported file format: {file.content_type} for file {file.filename}")

    except ValueError as ve:
        raise ve # Re-raise specific ValueErrors
    except Exception as e:
        logger.error(f"Unexpected error during text extraction for '{file.filename}': {str(e)}")
        raise ValueError(f"An unexpected error occurred while processing the file '{file.filename}'.")

def split_essays(text: str) -> List[str]:
    """Split text into multiple essays based on student name pattern."""
    logger.info("Attempting to split text into multiple essays.")
    # Use multiple patterns to match student identifiers more reliably
    # Patterns look for the identifier at the beginning of a line, possibly after some whitespace
    patterns = [
        r"^\s*Student Name:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})", # Allows apostrophes/hyphens, up to 4 name parts
        r"^\s*Student:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})",
        r"^\s*Name:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})"
    ]

    all_matches = []
    for pattern in patterns:
        # Use re.MULTILINE to match ^ at the start of each line
        matches = list(re.finditer(pattern, text, re.MULTILINE))
        all_matches.extend(matches)

    # Sort matches by their starting position
    all_matches.sort(key=lambda m: m.start())
    logger.info(f"Found {len(all_matches)} potential student name markers using patterns.")

    # If no markers found, try splitting by multiple newlines as a fallback
    if not all_matches:
        # Look for separators like 4 or more newlines (adjust sensitivity as needed)
        chunks = re.split(r'\n{4,}', text.strip())
        # Filter out very short chunks that are unlikely to be full essays
        potential_essays = [chunk for chunk in chunks if len(chunk.strip()) > 200]

        if len(potential_essays) > 1:
            logger.info(f"No name markers found. Split text into {len(potential_essays)} essays based on newline separators.")
            return potential_essays
        else:
            logger.info("No clear separators found. Treating text as a single essay.")
            return [text] # Treat as single essay

    # If only one marker found, it's likely a single essay with a name
    if len(all_matches) == 1:
         logger.info("Only one student name marker found. Treating as a single essay.")
         return [text]

    # Extract essays based on marker positions
    essays = []
    last_pos = 0
    for i, match in enumerate(all_matches):
        start_pos = match.start()
        # Add the text between the previous marker (or start) and this marker
        if start_pos > last_pos:
            # Check if the previous segment looks like an essay (not just headers/whitespace)
            prev_segment = text[last_pos:start_pos].strip()
            if len(prev_segment) > 100: # Heuristic: minimum length for a segment to be considered
                 # If this isn't the first marker, add the segment *before* it
                 if i > 0:
                    essays.append(prev_segment)
                 # For the first marker, this captures text *before* the first name
                 # Only add if it seems substantial (might be intro page etc)
                 elif len(prev_segment) > 500:
                     logger.warning(f"Found substantial text ({len(prev_segment)} chars) before the first name marker. Including as separate segment.")
                     essays.append(prev_segment)

        # If it's the last match, take all text from its start to the end
        if i == len(all_matches) - 1:
            essays.append(text[start_pos:])
        else:
            # Otherwise, take text until the start of the next match
            next_start_pos = all_matches[i + 1].start()
            essays.append(text[start_pos:next_start_pos])
        last_pos = start_pos # Update last_pos for the next iteration's calculation

    # Filter out potentially empty or very short segments
    final_essays = [essay.strip() for essay in essays if len(essay.strip()) > 200] # Min length threshold

    logger.info(f"Split text into {len(final_essays)} essays based on name markers.")
    # Log preview of each detected essay's start
    for i, essay in enumerate(final_essays):
        student_name_match = re.search(r"^\s*(?:Student Name|Student|Name):\s*(\S+\s*\S*)", essay, re.MULTILINE)
        student_name = student_name_match.group(1).strip() if student_name_match else f"Unknown_{i+1}"
        logger.debug(f"Essay {i+1}: Starts with Name='{student_name}', Length={len(essay)} chars, Preview='{essay[:100].replace(os.linesep, ' ')}...'")

    return final_essays

async def evaluate_essays(essay_text: str, rubric_text: str | None, api_key: str) -> List[dict]:
    """Split and evaluate multiple essays if detected, or evaluate as single essay."""
    logger.info("Starting essay evaluation process.")

    essays = split_essays(essay_text)
    num_essays = len(essays)
    logger.info(f"Document processing yielded {num_essays} essay(s).")

    results = []
    base_delay = 1.5  # Base delay in seconds between API calls
    max_delay_increment = 1.0 # Max random addition to delay

    # Process each essay
    for i, essay_content in enumerate(essays):
        essay_num = i + 1
        if not essay_content.strip():
            logger.warning(f"Skipping empty essay segment #{essay_num}.")
            continue

        logger.info(f"Processing essay {essay_num}/{num_essays}...")
        # Extract a preview for logging (avoid logging full essay)
        preview = essay_content[:150].replace('\n', ' ').strip() + "..."
        logger.debug(f"Essay {essay_num} preview: {preview}")

        # Add delay between API calls, especially for multiple essays, skip for first
        if i > 0:
            delay = base_delay + random.uniform(0, max_delay_increment)
            logger.info(f"Waiting {delay:.2f}s before calling API for essay {essay_num} to avoid rate limits.")
            await asyncio.sleep(delay)

        try:
            evaluation = await evaluate_essay(essay_content, rubric_text, api_key)
            student_name = evaluation.get('student_name', f'Unknown_{essay_num}')
            logger.info(f"Evaluation successful for essay {essay_num} (Student: {student_name})")
            results.append(evaluation)
        except Exception as e:
            logger.error(f"Error processing essay {essay_num}: {str(e)}", exc_info=True) # Log traceback

            # Try to extract student name even if evaluation failed
            student_name = "Unknown"
            try:
                name_patterns = [
                    r"^\s*Student Name:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})",
                    r"^\s*Student:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})",
                    r"^\s*Name:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})"
                ]
                for pattern in name_patterns:
                    name_match = re.search(pattern, essay_content, re.MULTILINE)
                    if name_match:
                        student_name = name_match.group(1).strip()
                        break
            except Exception as name_extract_err:
                 logger.warning(f"Could not extract student name from failed essay {essay_num}: {name_extract_err}")
                 student_name = f"Failed_Essay_{essay_num}"


            # Add a placeholder result for the failed essay
            results.append({
                "student_name": student_name,
                "overall_score": 0,
                "criteria": [{"name": "Processing Error", "score": 0, "max_score": 10, "feedback": f"Failed to evaluate: {str(e)}"}],
                "suggestions": ["Evaluation failed due to a processing error. Please check the essay content or API key/limits."],
                "highlighted_passages": [],
                "error": True # Flag indicating failure
            })

    logger.info(f"Finished processing. Generated {len(results)} evaluation results.")
    return results

async def evaluate_essay(essay_text: str, rubric_text: str | None, api_key: str) -> dict:
    """Evaluate a single essay using the Gemini API with retry logic."""
    if not api_key:
        logger.error("API key is missing for evaluation.")
        raise ValueError("API key is required for evaluation.")

    genai.configure(api_key=api_key)
    model_name = 'gemini-1.5-flash' # Use Flash model for potentially faster/cheaper evals
    logger.info(f"Using Gemini model: {model_name}")
    model = genai.GenerativeModel(model_name)

    rubric = rubric_text if rubric_text and rubric_text.strip() else DEFAULT_RUBRIC
    logger.debug(f"Using rubric:\n{rubric[:300]}...") # Log start of rubric

    # --- Rubric Parsing ---
    # More robust pattern: handles spaces, optional description start, captures score range
    criteria_pattern = r"^\s*(\d+)\.\s*([\w\s&,\-\(\)]+?)\s+\(0-(\d+)\):?"
    criteria_matches = re.findall(criteria_pattern, rubric, re.MULTILINE)

    criteria_names = []
    criteria_max_scores = []
    if criteria_matches:
        criteria_names = [match[1].strip() for match in criteria_matches]
        criteria_max_scores = [int(match[2]) for match in criteria_matches]
        logger.info(f"Extracted {len(criteria_names)} criteria from rubric: {criteria_names}")
    else:
        logger.warning("Could not parse criteria from rubric using pattern. Using default structure (5 criteria, 10 points each).")
        # Fallback if pattern fails
        num_lines = len(rubric.strip().split('\n'))
        criteria_count = max(1, num_lines // 4) # Rough estimate
        criteria_count = min(criteria_count, 8) # Cap at 8
        criteria_names = [f"Criterion {i+1}" for i in range(criteria_count)]
        criteria_max_scores = [10] * criteria_count

    max_score_total = sum(criteria_max_scores) if criteria_max_scores else 50
    criteria_count = len(criteria_names)

    # --- Student Name Extraction ---
    student_name = "Unknown"
    # Prioritize patterns at the start of the text/line
    name_patterns = [
        r"^\s*Student Name:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})", # Start of line/text
        r"^\s*Name:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})",
        r"^\s*Student:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})",
        r"^\s*Author:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})",
        r"^\s*By:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})"
    ]
    # Look in the first few lines for the name
    first_lines = "\n".join(essay_text.split('\n')[:5])
    for pattern in name_patterns:
        name_match = re.search(pattern, first_lines, re.IGNORECASE | re.MULTILINE)
        if name_match:
            student_name = name_match.group(1).strip()
            logger.info(f"Extracted student name: {student_name}")
            break

    # If still unknown, check if the very first line looks like just a name
    if student_name == "Unknown":
        first_line = essay_text.split('\n')[0].strip()
        # Regex: Allows 1-4 words, only letters, apostrophes, hyphens, spaces
        if re.fullmatch(r"[A-Za-z'\-]+(?: [A-Za-z'\-]+){0,3}", first_line):
             # Check if the second line looks like a title or course info (heuristic)
             second_line = essay_text.split('\n')[1].strip() if len(essay_text.split('\n')) > 1 else ""
             if not re.match(r"^(?:Student|Name|Date|Course|Professor|Assignment)", second_line, re.IGNORECASE):
                 student_name = first_line
                 logger.info(f"Extracted student name from first line: {student_name}")


    # --- Prompt Construction ---
    prompt = f"""
    Please act as an academic evaluator. Evaluate the following essay based STRICTLY on the provided rubric.

    **Evaluation Task:**
    1.  Read the essay carefully.
    2.  Use ONLY the criteria and scoring scales defined in the RUBRIC section below.
    3.  Score each criterion numerically based on its specified maximum score (e.g., 0-{criteria_max_scores[0] if criteria_max_scores else 10}).
    4.  Provide concise, specific feedback for EACH criterion, explaining the score given.
    5.  Calculate the `overall_score` as the simple sum of the individual criteria scores.
    6.  Provide 3-5 overall `suggestions` for improvement, focusing on the most impactful areas based on the rubric.
    7.  Identify 3-5 specific `highlighted_passages` from the essay text that exemplify areas needing improvement. For each passage:
        *   Quote the exact text (`text`, keep under 100 chars).
        *   Briefly explain the `issue` according to the rubric criteria.
        *   Offer a concrete `suggestion` for fixing it.
        *   Optionally provide a short `example_revision`.
    8.  Output the evaluation ONLY in the following JSON format. Ensure the JSON is valid. Do not include ```json markers or any text outside the JSON structure.

    **RUBRIC:**
    ```
    {rubric}
    ```

    **ESSAY:**
    ```
    {essay_text}
    ```

    **JSON Output Format:**
    {{
        "student_name": "{student_name}",
        "overall_score": number (Sum of criteria scores, max {max_score_total}),
        "criteria": [
            {{
                "name": "Exact Criterion Name 1 from Rubric",
                "score": number (0-{criteria_max_scores[0] if criteria_max_scores else 'MaxScore1'}),
                "max_score": {criteria_max_scores[0] if criteria_max_scores else 'MaxScore1'},
                "feedback": "Specific feedback for Criterion 1 based on the essay."
            }},
            // ... Repeat for ALL {criteria_count} criteria from the rubric
            {{
                "name": "Exact Criterion Name {criteria_count} from Rubric",
                "score": number (0-{criteria_max_scores[-1] if criteria_max_scores else 'MaxScoreN'}),
                "max_score": {criteria_max_scores[-1] if criteria_max_scores else 'MaxScoreN'},
                "feedback": "Specific feedback for Criterion {criteria_count}."
            }}
        ],
        "suggestions": [
            "Overall suggestion 1.",
            "Overall suggestion 2.",
            "Overall suggestion 3."
            // Up to 5 suggestions
        ],
        "highlighted_passages": [
            {{
                "text": "Exact phrase from essay...",
                "issue": "Specific problem (e.g., unclear topic sentence, weak evidence).",
                "suggestion": "How to improve this specific phrase/sentence.",
                "example_revision": "Optional: Rewritten example."
            }}
            // Repeat for 3-5 passages
        ]
    }}
    """

    # --- API Call with Retry ---
    max_retries = 3
    base_delay = 2.0  # seconds

    for attempt in range(max_retries):
        logger.info(f"Attempt {attempt + 1}/{max_retries} to call Gemini API for student: {student_name}")
        try:
            response = await model.generate_content_async(prompt) # Use async version
            raw_response_text = response.text
            logger.debug(f"Raw API response (first 500 chars): {raw_response_text[:500]}")

            # Clean the response: remove markdown code blocks, strip whitespace
            cleaned_response = re.sub(r'^```json\s*|\s*```$', '', raw_response_text, flags=re.MULTILINE | re.DOTALL).strip()

            # Attempt to parse JSON
            try:
                result = json.loads(cleaned_response)
                logger.info("Successfully parsed JSON response from API.")
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON parsing failed: {json_err}. Raw response snippet: {cleaned_response[:500]}...")
                # Attempt simple fixes (e.g., dangling commas - complex fixes are hard)
                fixed_json_str = re.sub(r',\s*([\}\]])', r'\1', cleaned_response) # Remove trailing commas before } or ]
                try:
                    result = json.loads(fixed_json_str)
                    logger.info("JSON parsed successfully after simple fix (trailing comma).")
                except json.JSONDecodeError:
                    logger.error("JSON parsing failed even after simple fix. Raising error.")
                    # Re-raise or handle as unrecoverable for this attempt
                    raise ValueError(f"Failed to parse JSON response from API: {json_err}")


            # --- Response Validation and Sanitization ---
            logger.info("Validating and sanitizing evaluation result structure.")

            # Ensure top-level keys exist
            result.setdefault("student_name", student_name)
            result.setdefault("overall_score", 0)
            result.setdefault("criteria", [])
            result.setdefault("suggestions", [])
            result.setdefault("highlighted_passages", [])

            # Validate criteria format and count
            validated_criteria = []
            api_criteria = result.get("criteria", [])
            if isinstance(api_criteria, list):
                 # Match API criteria to rubric criteria (case-insensitive fuzzy match might be needed)
                 matched_api_criteria = [None] * criteria_count
                 temp_api_criteria = list(api_criteria) # Copy to modify

                 for i, rubric_name in enumerate(criteria_names):
                     found = False
                     # Try exact match first
                     for j, api_crit in enumerate(temp_api_criteria):
                         if isinstance(api_crit, dict) and api_crit.get("name", "").strip() == rubric_name:
                             matched_api_criteria[i] = api_crit
                             temp_api_criteria.pop(j) # Remove matched item
                             found = True
                             break
                     # Optional: Add fuzzy matching here if needed

                     # If not found, create a placeholder
                     if not found:
                         logger.warning(f"Criterion '{rubric_name}' not found in API response. Creating placeholder.")
                         matched_api_criteria[i] = {
                              "name": rubric_name,
                              "score": 0,
                              "max_score": criteria_max_scores[i],
                              "feedback": "Feedback not provided by AI for this criterion."
                         }
                     else:
                         # Ensure required keys and types for matched criteria
                         crit_item = matched_api_criteria[i]
                         if not isinstance(crit_item, dict): continue # Skip if malformed

                         crit_item["name"] = rubric_name # Enforce exact rubric name
                         crit_item["max_score"] = criteria_max_scores[i] # Enforce rubric max score
                         try:
                              # Ensure score is numeric and within bounds
                              score = float(crit_item.get('score', 0))
                              crit_item['score'] = max(0, min(score, crit_item["max_score"]))
                         except (ValueError, TypeError):
                              logger.warning(f"Invalid score format for criterion '{rubric_name}'. Setting score to 0.")
                              crit_item['score'] = 0
                         crit_item.setdefault("feedback", "No feedback provided.")

                 validated_criteria = [c for c in matched_api_criteria if c is not None] # Filter out any Nones left over

            else:
                logger.warning("API 'criteria' was not a list. Creating default criteria.")
                validated_criteria = [{
                    "name": name, "score": 0, "max_score": max_s, "feedback": "Evaluation error: Malformed criteria response."
                } for name, max_s in zip(criteria_names, criteria_max_scores)]

            result["criteria"] = validated_criteria

            # Recalculate overall score based on validated criteria scores
            calculated_score = sum(c.get('score', 0) for c in result["criteria"])
            if result.get("overall_score") != calculated_score:
                 logger.warning(f"API overall score ({result.get('overall_score')}) differs from calculated sum ({calculated_score}). Using calculated sum.")
                 result["overall_score"] = calculated_score


            # Validate suggestions (ensure list of strings)
            result["suggestions"] = [str(s) for s in result.get("suggestions", []) if isinstance(s, (str, int, float))]

            # Validate highlighted passages (ensure list of dicts with required keys)
            validated_passages = []
            for p in result.get("highlighted_passages", []):
                 if isinstance(p, dict):
                      p.setdefault("text", "")
                      p.setdefault("issue", "")
                      p.setdefault("suggestion", "")
                      p.setdefault("example_revision", "")
                      # Optional: Truncate text if needed
                      p["text"] = p["text"][:150] # Limit passage length
                      validated_passages.append(p)
            result["highlighted_passages"] = validated_passages[:5] # Limit to 5 passages

            logger.info(f"Evaluation validated for student: {student_name}. Score: {result['overall_score']}/{max_score_total}")
            return result # Success

        except genai.types.generation_types.BlockedPromptException as bpe:
             logger.error(f"API call blocked due to safety settings or prompt issues for student {student_name}: {bpe}")
             raise ValueError(f"Evaluation failed: The prompt or essay content was blocked by safety filters. Please review the content.") from bpe
        except Exception as e:
            error_str = str(e).lower()
            logger.error(f"Error during API call or processing (Attempt {attempt + 1}): {error_str}", exc_info=True)

            # Check for rate limit error (common codes/messages)
            is_rate_limit = "429" in error_str or "rate limit" in error_str or "quota exceeded" in error_str or "resource exhausted" in error_str

            if is_rate_limit and attempt < max_retries - 1:
                # Exponential backoff with jitter
                delay = (base_delay * (2 ** attempt)) + random.uniform(0.5, 1.5)
                logger.warning(f"Rate limit detected. Retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)
                continue # Go to next retry iteration
            elif is_rate_limit:
                 logger.error(f"Rate limit error persisted after {max_retries} attempts. Failing evaluation for {student_name}.")
                 # Create a specific error response for rate limit failure
                 return {
                    "student_name": student_name, "overall_score": 0, "max_score_total": max_score_total,
                    "criteria": [{"name": "API Error", "score": 0, "max_score": max_score_total, "feedback": "Evaluation failed due to API rate limits after multiple retries."}],
                    "suggestions": ["Could not evaluate due to rate limits. Try again later or with fewer concurrent requests."],
                    "highlighted_passages": [], "error": True, "error_type": "rate_limit"
                 }
            else:
                 # For other errors, fail faster or after fewer retries if desired
                 if attempt < max_retries - 1:
                      # Optional: Add a shorter delay for non-rate-limit errors before retry
                      await asyncio.sleep(1.0 + random.uniform(0, 0.5))
                      continue
                 else:
                    logger.error(f"Non-rate-limit error persisted after {max_retries} attempts. Failing evaluation for {student_name}.")
                    raise ValueError(f"Failed to evaluate essay after {max_retries} attempts due to API/processing error: {str(e)}") from e


    # This point should theoretically not be reached if logic is correct, but acts as a final fallback.
    logger.error(f"Evaluation failed for {student_name} after exhausting all retries without specific error handling.")
    raise ValueError(f"Failed to evaluate essay '{student_name}' after {max_retries} attempts.")


# PDF Report Generation Class
class PDFReport:
    """Generate a PDF report from evaluation data with enhanced styling."""

    HEADER_COLOR = colors.HexColor('#1a365d')  # Navy blue
    ACCENT_COLOR = colors.HexColor('#3b82f6')  # Blue
    LIGHT_BG = colors.HexColor('#f3f4f6')      # Light gray
    SUCCESS_COLOR = colors.HexColor('#10b981') # Green
    WARNING_COLOR = colors.HexColor('#f59e0b') # Amber
    DANGER_COLOR = colors.HexColor('#ef4444')  # Red
    PURPLE_COLOR = colors.HexColor('#8b5cf6')  # Purple
    TEAL_COLOR = colors.HexColor('#14b8a6')    # Teal
    INDIGO_COLOR = colors.HexColor('#6366f1')  # Indigo
    HIGHLIGHT_COLOR = colors.HexColor('#fef9c3') # Light yellow for highlighting
    TEXT_COLOR = colors.HexColor('#1f2937')    # Darker gray for text

    FONT_NAME = 'Helvetica'
    BOLD_FONT = 'Helvetica-Bold'

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        # Base style
        self.styles.add(ParagraphStyle(name='Base', fontName=self.FONT_NAME, fontSize=10, textColor=self.TEXT_COLOR, leading=14))

        # Titles
        self.styles.add(ParagraphStyle(name='MainTitle', parent=self.styles['h1'], fontName=self.BOLD_FONT, fontSize=20, spaceAfter=10, alignment=TA_CENTER, textColor=self.HEADER_COLOR))
        self.styles.add(ParagraphStyle(name='StudentTitle', parent=self.styles['h2'], fontName=self.FONT_NAME, fontSize=14, spaceAfter=6, alignment=TA_CENTER, textColor=self.ACCENT_COLOR))
        self.styles.add(ParagraphStyle(name='ScoreTitle', parent=self.styles['h3'], fontName=self.BOLD_FONT, fontSize=12, spaceAfter=18, alignment=TA_CENTER))
        self.styles.add(ParagraphStyle(name='SectionTitle', parent=self.styles['h2'], fontName=self.BOLD_FONT, fontSize=14, spaceAfter=10, textColor=self.HEADER_COLOR, borderPadding=5, borderColor=self.LIGHT_BG, borderWidth=1, backColor=self.LIGHT_BG, borderRadius=5))

        # Table Styles
        self.styles.add(ParagraphStyle(name='TableHeader', parent=self.styles['Base'], fontName=self.BOLD_FONT, alignment=TA_CENTER, textColor=colors.white))
        self.styles.add(ParagraphStyle(name='TableCell', parent=self.styles['Base'], alignment=TA_LEFT, leading=12))
        self.styles.add(ParagraphStyle(name='TableCellBold', parent=self.styles['TableCell'], fontName=self.BOLD_FONT))
        self.styles.add(ParagraphStyle(name='TableCellCenter', parent=self.styles['TableCell'], alignment=TA_CENTER))
        self.styles.add(ParagraphStyle(name='FeedbackCell', parent=self.styles['TableCell'], fontSize=9))

        # Suggestions & Highlights
        self.styles.add(ParagraphStyle(name='SuggestionItem', parent=self.styles['Base'], leftIndent=15, bulletIndent=0, spaceBefore=5))
        self.styles.add(ParagraphStyle(name='HighlightBox', parent=self.styles['Base'], fontSize=9, borderPadding=5, borderColor=self.TEAL_COLOR, borderWidth=0.5, borderRadius=3, spaceAfter=5, backColor=colors.HexColor('#f0fdfa')))
        self.styles.add(ParagraphStyle(name='HighlightText', parent=self.styles['Base'], fontSize=9, backColor=self.HIGHLIGHT_COLOR, textColor=colors.black)) # Specific style for the quoted text
        self.styles.add(ParagraphStyle(name='IssueText', parent=self.styles['Base'], fontSize=9, textColor=self.DANGER_COLOR, leftIndent=10, spaceBefore=2))
        self.styles.add(ParagraphStyle(name='SuggestText', parent=self.styles['Base'], fontSize=9, textColor=self.ACCENT_COLOR, leftIndent=10, spaceBefore=2))
        self.styles.add(ParagraphStyle(name='ExampleText', parent=self.styles['Base'], fontSize=9, textColor=self.SUCCESS_COLOR, leftIndent=10, fontName='Helvetica-Oblique', spaceBefore=2))

        # Footer
        self.styles.add(ParagraphStyle(name='Footer', parent=self.styles['Base'], alignment=TA_CENTER, fontSize=8, textColor=colors.grey))

    def _get_score_color(self, score, max_score):
        """Return color based on score percentage."""
        if max_score == 0: return self.TEXT_COLOR # Avoid division by zero
        percentage = score / max_score
        if percentage >= 0.8: return self.SUCCESS_COLOR
        if percentage >= 0.6: return self.ACCENT_COLOR
        if percentage >= 0.4: return self.WARNING_COLOR
        return self.DANGER_COLOR

    def _header(self, canvas, doc):
        """Add header to each page."""
        canvas.saveState()
        canvas.setFont(self.FONT_NAME, 9)
        canvas.setFillColor(colors.grey)
        canvas.drawString(inch, doc.height + doc.topMargin - 0.5*inch, "Essay Evaluation Report")
        canvas.drawRightString(doc.width + doc.leftMargin - inch, doc.height + doc.topMargin - 0.5*inch, f"Page {doc.page}")
        canvas.restoreState()

    def _footer(self, canvas, doc):
         """Add footer to each page."""
         canvas.saveState()
         canvas.setFont(self.FONT_NAME, 8)
         canvas.setFillColor(colors.grey)
         canvas.drawCentredString(doc.width/2 + doc.leftMargin, 0.5*inch, "Generated by AI Essay Grader")
         canvas.restoreState()


    def create(self, evaluation: dict) -> BytesIO:
        """Create a PDF report from a single evaluation dictionary."""
        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter,
                                  rightMargin=0.75*inch, leftMargin=0.75*inch,
                                  topMargin=1*inch, bottomMargin=1*inch)
        elements = []
        logger.info(f"Starting PDF creation for: {evaluation.get('student_name', 'Unknown')}")

        try:
            # --- Safely get evaluation data ---
            student_name = evaluation.get("student_name", "Unknown Student")
            criteria = evaluation.get("criteria", [])
            suggestions = evaluation.get("suggestions", [])
            highlighted_passages = evaluation.get("highlighted_passages", [])

            # Ensure criteria is a list of dicts
            if not isinstance(criteria, list) or not all(isinstance(c, dict) for c in criteria):
                 logger.warning(f"Invalid criteria format for {student_name}. Using default.")
                 criteria = [{"name": "Evaluation Error", "score": 0, "max_score": 10, "feedback": "Could not load criteria."}]

            # Calculate scores safely
            try:
                overall_score = sum(float(c.get("score", 0)) for c in criteria)
                max_score_total = sum(float(c.get("max_score", 10)) for c in criteria) # Default max 10 if missing
                if max_score_total == 0 and criteria: # Handle case where all max_scores are 0 or missing
                     max_score_total = len(criteria) * 10
                elif not criteria:
                    max_score_total = 10 # Avoid division by zero if no criteria
                # Ensure overall_score doesn't exceed calculated max
                overall_score = min(overall_score, max_score_total)

            except (ValueError, TypeError) as score_err:
                 logger.error(f"Error calculating scores for {student_name}: {score_err}. Setting scores to 0.")
                 overall_score = 0
                 max_score_total = sum(10 for c in criteria) if criteria else 10 # Fallback max score


            score_color = self._get_score_color(overall_score, max_score_total)

            # --- PDF Elements ---
            elements.append(Paragraph("Essay Evaluation Report", self.styles['MainTitle']))
            elements.append(Paragraph(f"Student: {student_name}", self.styles['StudentTitle']))
            elements.append(Paragraph(
                f"Overall Score: <font color='{score_color.hexval()}'><b>{overall_score:.1f}</b></font> / {max_score_total:.1f}",
                self.styles['ScoreTitle']
            ))

            # --- Criteria Table ---
            if criteria:
                elements.append(Paragraph("Evaluation Breakdown", self.styles['SectionTitle']))
                elements.append(Spacer(1, 0.15*inch))

                table_data = [
                    [Paragraph('Criterion', self.styles['TableHeader']),
                     Paragraph('Score', self.styles['TableHeader']),
                     Paragraph('Feedback', self.styles['TableHeader'])]
                ]
                table_style = TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), self.HEADER_COLOR),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('FONTNAME', (0,0), (-1,0), self.BOLD_FONT),
                    ('ALIGN', (0,0), (-1,0), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('ALIGN', (1,1), (1,-1), 'CENTER'), # Score column centered
                    ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                    ('RIGHTPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
                ])

                for i, crit in enumerate(criteria):
                    name = crit.get("name", f"Criterion {i+1}")
                    try:
                        score = float(crit.get("score", 0))
                        max_score = float(crit.get("max_score", 10))
                        if max_score == 0: max_score = 10 # Avoid zero max score display
                    except (ValueError, TypeError):
                        score, max_score = 0, 10
                    feedback = crit.get("feedback", "N/A")
                    crit_score_color = self._get_score_color(score, max_score)

                    table_data.append([
                        Paragraph(name, self.styles['TableCellBold']),
                        Paragraph(f"<font color='{crit_score_color.hexval()}'>{score:.1f}</font> / {max_score:.1f}", self.styles['TableCellCenter']),
                        Paragraph(feedback, self.styles['FeedbackCell'])
                    ])

                # Define column widths (adjust as needed)
                col_widths = [2.0*inch, 0.8*inch, 4.0*inch]
                criteria_table = Table(table_data, colWidths=col_widths, style=table_style, repeatRows=1)
                elements.append(criteria_table)
                elements.append(Spacer(1, 0.3*inch))
            else:
                 elements.append(Paragraph("No evaluation criteria data available.", self.styles['Base']))
                 elements.append(Spacer(1, 0.3*inch))


            # --- Areas for Improvement ---
            if highlighted_passages:
                elements.append(Paragraph("Areas for Improvement", self.styles['SectionTitle']))
                elements.append(Spacer(1, 0.15*inch))

                for i, passage in enumerate(highlighted_passages, 1):
                     if not isinstance(passage, dict): continue

                     text = passage.get("text", "N/A").replace('\n', ' ') # Ensure single line
                     issue = passage.get("issue", "N/A")
                     suggestion = passage.get("suggestion", "N/A")
                     example = passage.get("example_revision", "")

                     passage_elements = [
                         Paragraph(f"<b>Passage {i}:</b> <font name='Courier' size='9'><backColor='{self.HIGHLIGHT_COLOR.hexval()}'> {text} </backColor></font>", self.styles['Base']),
                         Paragraph(f"<b>Issue:</b> {issue}", self.styles['IssueText']),
                         Paragraph(f"<b>Suggestion:</b> {suggestion}", self.styles['SuggestText']),
                     ]
                     if example:
                         passage_elements.append(Paragraph(f"<b>Example:</b> {example}", self.styles['ExampleText']))

                     # Create a box around each passage feedback
                     box_table = Table([[passage_elements]], colWidths=[doc.width - 0.2*inch], # Use available width
                                       style=TableStyle([
                                           ('BOX', (0,0), (-1,-1), 0.5, self.TEAL_COLOR),
                                           ('LEFTPADDING', (0,0), (-1,-1), 10),
                                           ('RIGHTPADDING', (0,0), (-1,-1), 10),
                                           ('TOPPADDING', (0,0), (-1,-1), 8),
                                           ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                                           ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')) # Very light blue bg
                                       ]))
                     elements.append(box_table)
                     elements.append(Spacer(1, 0.15*inch))

                elements.append(Spacer(1, 0.15*inch)) # Extra space after the section


            # --- General Suggestions ---
            if suggestions:
                elements.append(Paragraph("General Suggestions", self.styles['SectionTitle']))
                elements.append(Spacer(1, 0.15*inch))
                for i, sug in enumerate(suggestions):
                    # Use reportlab's bullet points
                    elements.append(Paragraph(str(sug), self.styles['SuggestionItem'], bulletText=f'\u2022')) # Unicode bullet
                elements.append(Spacer(1, 0.3*inch))

            # --- Build PDF ---
            doc.build(elements, onFirstPage=self._header, onLaterPages=self._header, canvasmaker=CanvasWithFooter)
            pdf_buffer.seek(0)
            logger.info(f"PDF created successfully for {student_name}. Size: {len(pdf_buffer.getvalue())} bytes.")
            return pdf_buffer

        except Exception as e:
            logger.error(f"Critical error during PDF generation for {evaluation.get('student_name', 'Unknown')}: {e}", exc_info=True)
            # Create a minimal error PDF
            pdf_buffer = BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
            error_elements = [
                Paragraph("Error Generating Report", self.styles['MainTitle']),
                Spacer(1, 0.5*inch),
                Paragraph(f"An unexpected error occurred while generating the PDF report for '{evaluation.get('student_name', 'Unknown')}'.", self.styles['Base']),
                Spacer(1, 0.2*inch),
                Paragraph(f"Error details: {str(e)}", self.styles['Base']),
                Spacer(1, 0.2*inch),
                Paragraph("Please check the server logs for more information.", self.styles['Base'])
            ]
            try:
                doc.build(error_elements)
                pdf_buffer.seek(0)
                logger.info("Generated minimal error PDF.")
                return pdf_buffer
            except Exception as build_err:
                 logger.error(f"Failed even to build the minimal error PDF: {build_err}")
                 # Return an empty buffer as last resort? Or raise?
                 # For now, return empty buffer to avoid crashing the endpoint entirely.
                 return BytesIO()

# Custom Canvas class to draw footer using PDFReport's style
class CanvasWithFooter(Canvas): #reportlab.pdfgen.canvas.Canvas
    def __init__(self, *args, **kwargs):
        Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self._report_instance = PDFReport() # Get styles

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        """add page info to each page (page x of y)"""
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            Canvas.showPage(self)
            Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont(self._report_instance.FONT_NAME, 8)
        self.setFillColor(colors.grey)
        self.drawCentredString(letter[0]/2, 0.5 * inch,
                               f"Page {self._pageNumber} of {page_count} | Generated by AI Essay Grader")


# Rubric management functions
def get_rubric_dir():
    return "rubrics"

def get_saved_rubrics():
    """Get list of saved rubrics."""
    rubrics = []
    rubrics_dir = get_rubric_dir()
    if not os.path.exists(rubrics_dir):
        return []

    for filename in os.listdir(rubrics_dir):
        if filename.endswith(".txt"):
            rubric_id = filename[:-4]
            filepath = os.path.join(rubrics_dir, filename)
            try:
                with open(filepath, "r", encoding='utf-8') as f:
                    content = f.read()
                # Try to extract name from first line, fallback to ID
                first_line = content.strip().split('\n', 1)[0]
                name = first_line[:60].strip() if first_line else f"Rubric {rubric_id[:8]}"
                # Simple preview
                preview = content[:150].replace('\n', ' ') + ('...' if len(content) > 150 else '')

                rubrics.append({
                    "id": rubric_id,
                    "name": name,
                    "preview": preview
                })
            except Exception as e:
                logger.error(f"Error reading rubric file {filename}: {e}")
                continue # Skip corrupted files
    # Sort rubrics by name
    rubrics.sort(key=lambda x: x['name'].lower())
    logger.info(f"Found {len(rubrics)} saved rubrics.")
    return rubrics

def save_rubric(content: str, name: Optional[str] = None, rubric_id: Optional[str] = None) -> str:
    """Save a rubric to file and return its ID."""
    if not rubric_id:
        rubric_id = str(uuid.uuid4())
    rubrics_dir = get_rubric_dir()
    filepath = os.path.join(rubrics_dir, f"{rubric_id}.txt")

    # Prepend name as the first line if provided and not already there
    lines = content.strip().split('\n')
    if name and (not lines or lines[0].strip() != name.strip()):
         content_to_save = f"{name.strip()}\n\n{content.strip()}"
    else:
         content_to_save = content.strip()

    try:
        with open(filepath, "w", encoding='utf-8') as f:
            f.write(content_to_save)
        logger.info(f"Rubric '{name or rubric_id}' saved successfully to {filepath}.")
        return rubric_id
    except Exception as e:
        logger.error(f"Error saving rubric {rubric_id}: {e}")
        raise IOError(f"Could not save rubric file: {e}")


def get_rubric_by_id(rubric_id: str) -> tuple[str, Optional[str]]:
    """Get rubric content and optionally its name by ID."""
    rubrics_dir = get_rubric_dir()
    filepath = os.path.join(rubrics_dir, f"{rubric_id}.txt")
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            content = f.read()
        # Try to parse name from first line
        lines = content.strip().split('\n', 1)
        name = lines[0].strip()
        # Basic check if the first line looks like a title (e.g., ends with ':')
        if len(lines) > 1 and (name.endswith(':') or len(name) < 60):
             # Assume first line is the name, return content without it
             actual_content = lines[1].strip() if len(lines) > 1 else ""
             logger.info(f"Found rubric '{rubric_id}' with name '{name}'.")
             return actual_content, name
        else:
             # Assume no name prefix or first line is part of content
             logger.info(f"Found rubric '{rubric_id}', no distinct name parsed from first line.")
             return content, None # Return full content, no name extracted

    except FileNotFoundError:
        logger.warning(f"Rubric file not found for ID: {rubric_id}")
        raise ValueError(f"Rubric with ID {rubric_id} not found")
    except Exception as e:
        logger.error(f"Error reading rubric {rubric_id}: {e}")
        raise IOError(f"Could not read rubric file: {e}")


def delete_rubric(rubric_id: str) -> bool:
    """Delete a rubric by ID."""
    rubrics_dir = get_rubric_dir()
    filepath = os.path.join(rubrics_dir, f"{rubric_id}.txt")
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Deleted rubric file: {filepath}")
            return True
        else:
            logger.warning(f"Attempted to delete non-existent rubric: {rubric_id}")
            return False
    except Exception as e:
        logger.error(f"Error deleting rubric {rubric_id}: {e}")
        return False

# API Endpoints

@app.post("/verify-api-key/", tags=["API Key"])
async def verify_api_key(api_key: str = Form(...)):
    """Verify if the provided Google Generative AI API key is valid."""
    if not api_key or len(api_key) < 20: # Basic length check
        logger.warning("API key verification failed: Key is too short or empty.")
        raise HTTPException(status_code=400, detail="API key is too short or appears invalid.")

    logger.info(f"Verifying API key (showing first 5 chars): {api_key[:5]}...")
    try:
        genai.configure(api_key=api_key)
        # Attempt to list models as a verification step
        models = list(genai.list_models()) # Use sync version for simplicity here
        if any('generateContent' in m.supported_generation_methods for m in models):
            logger.info(f"API key verification successful. Found {len(models)} models.")
            return {"status": "success", "message": "API key is valid and can generate content."}
        else:
             logger.warning("API key is valid but no models supporting 'generateContent' found.")
             raise HTTPException(status_code=400, detail="API key is valid, but no suitable generative models found.")

    except Exception as e:
        logger.error(f"API key verification failed: {str(e)}")
        # Provide a more generic error to the client for security
        raise HTTPException(status_code=400, detail=f"Invalid API key or connection error. Please check the key and try again.")


@app.post("/evaluate/", tags=["Evaluation"])
async def evaluate_essay_endpoint(
    essay: UploadFile,
    api_key: str = Form(...),
    rubric_text: Optional[str] = Form(None),
    rubric_id: Optional[str] = Form(None)
):
    """
    Evaluate one or more essays from an uploaded file (PDF, TXT, DOCX).
    Returns a single PDF report if one essay is detected, or a JSON response
    with details for multiple essays, allowing subsequent download of individual reports or a ZIP archive.
    """
    logger.info(f"Received evaluation request for file: {essay.filename} (Type: {essay.content_type}, Size: {essay.size})")
    if not essay.filename or essay.size == 0:
        logger.warning("Evaluation failed: Empty file uploaded.")
        raise HTTPException(status_code=400, detail="Cannot process an empty file.")
    if essay.content_type not in ALLOWED_TYPES and not any(essay.filename.lower().endswith(ext) for ext in ['.pdf', '.txt', '.docx']):
        logger.warning(f"Evaluation failed: Invalid file type '{essay.content_type}' for file '{essay.filename}'.")
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_TYPES)} and extensions .pdf, .txt, .docx")

    effective_rubric_text = ""
    rubric_source = "Default"

    # Determine the rubric to use
    if rubric_text and rubric_text.strip():
        effective_rubric_text = rubric_text
        rubric_source = "Direct Text"
        logger.info("Using rubric provided directly in the request.")
    elif rubric_id:
        try:
            content, name = get_rubric_by_id(rubric_id)
            effective_rubric_text = content
            rubric_source = f"Saved Rubric ID: {rubric_id}" + (f" (Name: {name})" if name else "")
            logger.info(f"Using saved rubric: {rubric_source}")
        except ValueError as e:
             logger.warning(f"Could not find rubric with ID {rubric_id}. Falling back to default.")
             effective_rubric_text = DEFAULT_RUBRIC
             rubric_source = "Default (Specified ID not found)"
        except IOError as e:
             logger.error(f"Error reading rubric {rubric_id}: {e}. Falling back to default.")
             effective_rubric_text = DEFAULT_RUBRIC
             rubric_source = "Default (Error reading saved rubric)"
    else:
        effective_rubric_text = DEFAULT_RUBRIC
        logger.info("No rubric provided, using default rubric.")

    pdf_report_generator = PDFReport()

    try:
        # Extract text from the uploaded file
        essay_text_content = await extract_text(essay)
        if not essay_text_content.strip():
             logger.warning(f"Evaluation failed: Extracted text from '{essay.filename}' is empty.")
             raise HTTPException(status_code=400, detail=f"The uploaded file '{essay.filename}' contains no readable text.")

        # Evaluate the essay(s)
        evaluations = await evaluate_essays(essay_text_content, effective_rubric_text or None, api_key) # Pass None if empty

        if not evaluations:
             logger.warning("Evaluation process returned no results.")
             raise HTTPException(status_code=500, detail="Evaluation failed: No results were generated.")

        session_id = str(uuid.uuid4()) # Unique ID for this batch processing

        # --- Handle Single vs Multiple Essays ---
        if len(evaluations) == 1:
            logger.info("Single essay detected. Generating PDF report directly.")
            evaluation = evaluations[0]

            # Calculate max_score for headers
            max_score = 0
            criteria = evaluation.get("criteria", [])
            if isinstance(criteria, list) and criteria:
                try:
                    max_score = sum(int(c.get("max_score", 10)) for c in criteria if isinstance(c, dict))
                except (ValueError, TypeError):
                    logger.warning("Could not accurately sum max scores for single report header, using approximation.")
                    max_score = len(criteria) * 10
            else:
                 logger.warning("No criteria found in single evaluation result for header calculation.")
                 # Attempt to parse from rubric again as fallback
                 try:
                    criteria_pattern = r"^\s*(\d+)\.\s*.*?\(0-(\d+)\):?"
                    matches = re.findall(criteria_pattern, effective_rubric_text, re.MULTILINE)
                    if matches: max_score = sum(int(m[1]) for m in matches)
                    else: max_score = 50 # Absolute fallback
                 except Exception: max_score = 50

            # Generate PDF
            pdf_buffer = pdf_report_generator.create(evaluation)
            pdf_content = pdf_buffer.getvalue()

            if not pdf_content:
                 logger.error("PDF generation resulted in an empty buffer for single essay.")
                 raise HTTPException(status_code=500, detail="Failed to generate PDF report.")

            student_name = evaluation.get("student_name", "Unknown")
            safe_name = re.sub(r'[^\w\-]+', '_', student_name) # Sanitize for filename
            filename = f"{safe_name}_Evaluation_Report.pdf"

            logger.info(f"Returning single PDF report: {filename}")
            return Response(
                content=pdf_content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=\"{filename}\"", # Use quotes for names with spaces
                    "X-Evaluation-Status": "single",
                    "X-Student-Name": student_name, # Send original name
                    "X-Overall-Score": str(evaluation.get('overall_score', 0)),
                    "X-Max-Score": str(max_score),
                    "Access-Control-Expose-Headers": "Content-Disposition, X-Evaluation-Status, X-Student-Name, X-Overall-Score, X-Max-Score" # Expose custom headers
                }
            )

        else:
            # --- Multiple Essays: Store results and return JSON ---
            logger.info(f"Multiple ({len(evaluations)}) essays detected. Storing results for session {session_id}.")
            multi_results_summary = []
            session_storage_entry = {} # Store {filename: evaluation_dict}

            for i, evaluation in enumerate(evaluations):
                student_name = evaluation.get("student_name", f"Essay_{i+1}")
                safe_name = re.sub(r'[^\w\-]+', '_', student_name)
                filename = f"{safe_name}_Evaluation_{i+1}.pdf" # Add index for uniqueness

                # Calculate max score for summary
                max_score = 0
                criteria = evaluation.get("criteria", [])
                if isinstance(criteria, list) and criteria:
                    try:
                        max_score = sum(int(c.get("max_score", 10)) for c in criteria if isinstance(c, dict))
                    except (ValueError, TypeError): max_score = len(criteria) * 10
                else: max_score = 50 # Fallback

                # Store the full evaluation data needed for later PDF/ZIP generation
                session_storage_entry[filename] = evaluation

                # Add summary info for the initial response
                multi_results_summary.append({
                    "id": i, # Simple index
                    "filename": filename,
                    "student_name": student_name,
                    "overall_score": evaluation.get("overall_score", 0),
                    "max_score": max_score,
                    "status": "Error" if evaluation.get("error") else "Completed"
                })

            # Store the evaluations associated with this session ID
            evaluation_storage[session_id] = session_storage_entry
            # Optional: Add TTL or cleanup mechanism for evaluation_storage

            logger.info(f"Returning summary for {len(evaluations)} essays. Session ID: {session_id}")
            return {
                "evaluation_status": "multiple",
                "session_id": session_id,
                "count": len(evaluations),
                "results": multi_results_summary
            }

    except ValueError as e: # Errors from text extraction or evaluation logic
        logger.error(f"ValueError during evaluation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as he: # Re-raise existing HTTP exceptions
        raise he
    except Exception as e: # Catch-all for unexpected server errors
        logger.error(f"Unexpected server error during evaluation: {str(e)}", exc_info=True)
        # Log detailed traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred: {str(e)}")


# Endpoint to download a single report from a multi-essay session
@app.get("/download-report/{session_id}/{filename}", tags=["Download"])
async def download_single_report(session_id: str, filename: str):
    """Download a single PDF report from a previous multi-essay evaluation session."""
    logger.info(f"Request received to download report: Session='{session_id}', Filename='{filename}'")

    if session_id not in evaluation_storage:
        logger.warning(f"Download failed: Session ID '{session_id}' not found in storage.")
        raise HTTPException(status_code=404, detail="Evaluation session not found or expired.")

    session_data = evaluation_storage[session_id]
    if filename not in session_data:
        logger.warning(f"Download failed: Filename '{filename}' not found in session '{session_id}'. Available: {list(session_data.keys())}")
        raise HTTPException(status_code=404, detail="Requested report file not found in this session.")

    evaluation = session_data[filename]
    logger.info(f"Found evaluation data for '{filename}' in session '{session_id}'. Generating PDF.")

    try:
        pdf_report_generator = PDFReport()
        pdf_buffer = pdf_report_generator.create(evaluation)
        pdf_content = pdf_buffer.getvalue()

        if not pdf_content:
             logger.error(f"PDF generation resulted in an empty buffer for '{filename}' (Session: {session_id}).")
             raise HTTPException(status_code=500, detail="Failed to generate the PDF report for this essay.")

        logger.info(f"Successfully generated PDF for '{filename}'. Sending response.")
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        logger.error(f"Error generating single PDF report for download ('{filename}', Session: {session_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error occurred while generating the PDF report: {str(e)}")

# Endpoint to generate and download a ZIP of all reports from a multi-essay session
# Updated to receive session_id via POST body
@app.post("/generate-all-zip/", tags=["Download"])
async def generate_all_zip(data: dict = Body(...)):
    """
    Generate and download a ZIP archive containing all PDF reports
    from a previous multi-essay evaluation session. Requires 'session_id'.
    """
    session_id = data.get("session_id")
    if not session_id:
         logger.warning("ZIP generation request failed: Missing 'session_id' in request body.")
         raise HTTPException(status_code=400, detail="Missing 'session_id' in request body.")

    logger.info(f"Request received to generate ZIP archive for session: '{session_id}'")

    if session_id not in evaluation_storage:
        logger.warning(f"ZIP generation failed: Session ID '{session_id}' not found.")
        raise HTTPException(status_code=404, detail="Evaluation session not found or expired.")

    session_data = evaluation_storage[session_id]
    if not session_data:
         logger.warning(f"ZIP generation failed: Session '{session_id}' contains no evaluation data.")
         raise HTTPException(status_code=404, detail="No evaluation reports found for this session.")

    zip_buffer = BytesIO()
    pdf_report_generator = PDFReport()
    generated_files_count = 0
    failed_files_count = 0

    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename, evaluation in session_data.items():
                 logger.debug(f"Generating PDF for '{filename}' to include in ZIP (Session: {session_id})")
                 try:
                     pdf_buffer = pdf_report_generator.create(evaluation)
                     pdf_content = pdf_buffer.getvalue()
                     if pdf_content:
                         zip_file.writestr(filename, pdf_content)
                         generated_files_count += 1
                         logger.debug(f"Added '{filename}' ({len(pdf_content)} bytes) to ZIP.")
                     else:
                         logger.warning(f"Skipping '{filename}' in ZIP: PDF generation resulted in empty content.")
                         failed_files_count += 1
                 except Exception as e:
                      logger.error(f"Error generating PDF for '{filename}' during ZIP creation: {e}", exc_info=True)
                      failed_files_count += 1
                      # Optional: Add an error marker file to the ZIP?
                      # zip_file.writestr(f"{filename}_ERROR.txt", f"Failed to generate PDF report for this essay. Error: {str(e)}")

        if generated_files_count == 0:
             logger.error(f"ZIP generation failed: Could not generate any valid PDF reports for session '{session_id}'.")
             raise HTTPException(status_code=500, detail="Failed to generate any valid PDF reports for the ZIP archive.")

        zip_buffer.seek(0)
        zip_content = zip_buffer.getvalue()

        logger.info(f"ZIP archive generated for session '{session_id}'. Contains {generated_files_count} reports ({failed_files_count} failed). Size: {len(zip_content)} bytes.")

        # Optional: Clean up session data after successful ZIP generation?
        # del evaluation_storage[session_id]

        return Response(
            content=zip_content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=Evaluation_Reports_{session_id[:8]}.zip",
                "X-Files-Generated": str(generated_files_count),
                "X-Files-Failed": str(failed_files_count),
                "Access-Control-Expose-Headers": "Content-Disposition, X-Files-Generated, X-Files-Failed"
            }
        )

    except Exception as e:
        logger.error(f"Critical error during ZIP archive generation for session '{session_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error occurred while generating the ZIP archive: {str(e)}")


# --- Rubric Management Endpoints ---

@app.get("/rubrics/", tags=["Rubrics"])
async def list_rubrics():
    """List all saved rubrics."""
    logger.info("Request received to list saved rubrics.")
    try:
        rubrics = get_saved_rubrics()
        return {"rubrics": rubrics}
    except Exception as e:
        logger.error(f"Error retrieving saved rubrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error retrieving rubrics: {str(e)}")

@app.get("/rubrics/{rubric_id}", tags=["Rubrics"])
async def get_rubric(rubric_id: str):
    """Get the content of a specific rubric by ID."""
    logger.info(f"Request received to get rubric with ID: {rubric_id}")
    try:
        content, name = get_rubric_by_id(rubric_id)
        return {"id": rubric_id, "name": name, "content": content}
    except ValueError as e: # Not found
        logger.warning(f"Rubric not found: {rubric_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except IOError as e: # Read error
        logger.error(f"Error reading rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting rubric {rubric_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/rubrics/", tags=["Rubrics"], status_code=201)
async def create_rubric(content: str = Form(...), name: Optional[str] = Form(None)):
    """Create and save a new rubric."""
    logger.info(f"Request received to create new rubric. Name: '{name if name else 'None'}'")
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="Rubric content cannot be empty.")
    if name and len(name) > 100:
         raise HTTPException(status_code=400, detail="Rubric name cannot exceed 100 characters.")

    try:
        rubric_id = save_rubric(content, name)
        # Fetch the newly saved rubric to confirm and return details
        saved_content, saved_name = get_rubric_by_id(rubric_id)
        return {"id": rubric_id, "name": saved_name or name, "message": "Rubric saved successfully"}
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save rubric: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating rubric: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error creating rubric: {str(e)}")

@app.put("/rubrics/{rubric_id}", tags=["Rubrics"])
async def update_rubric(rubric_id: str, content: str = Form(...), name: Optional[str] = Form(None)):
    """Update an existing rubric by ID."""
    logger.info(f"Request received to update rubric ID: {rubric_id}. New Name: '{name if name else 'None'}'")
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="Rubric content cannot be empty.")
    if name and len(name) > 100:
         raise HTTPException(status_code=400, detail="Rubric name cannot exceed 100 characters.")

    try:
        # First check if rubric exists by trying to get it (raises ValueError if not found)
        get_rubric_by_id(rubric_id)

        # Save the updated content/name
        save_rubric(content, name, rubric_id)
        # Fetch again to confirm update
        updated_content, updated_name = get_rubric_by_id(rubric_id)
        return {"id": rubric_id, "name": updated_name or name, "message": "Rubric updated successfully"}
    except ValueError: # Not found from get_rubric_by_id
        logger.warning(f"Update failed: Rubric not found: {rubric_id}")
        raise HTTPException(status_code=404, detail=f"Rubric with ID {rubric_id} not found")
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Failed to update rubric: {str(e)}")
    except Exception as e:
        logger.error(f"Error updating rubric {rubric_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error updating rubric: {str(e)}")

@app.delete("/rubrics/{rubric_id}", tags=["Rubrics"], status_code=204)
async def remove_rubric(rubric_id: str):
    """Delete a specific rubric by ID."""
    logger.info(f"Request received to delete rubric ID: {rubric_id}")
    deleted = delete_rubric(rubric_id)
    if deleted:
        # Return No Content response on successful deletion
        return Response(status_code=204)
    else:
        # If delete_rubric returns False, it means file not found or error
        # We'll treat 'not found' as the primary reason for a 404
        # Check if file exists to differentiate between not found and delete error
        filepath = os.path.join(get_rubric_dir(), f"{rubric_id}.txt")
        if not os.path.exists(filepath):
             logger.warning(f"Deletion failed: Rubric not found: {rubric_id}")
             raise HTTPException(status_code=404, detail=f"Rubric with ID {rubric_id} not found")
        else:
             # Should not happen if delete_rubric has error handling, but just in case
             logger.error(f"Deletion failed for rubric {rubric_id}, but file exists. Check permissions.")
             raise HTTPException(status_code=500, detail="Failed to delete rubric due to a server error.")

@app.get("/default-rubric/", tags=["Rubrics"])
async def get_default_rubric():
    """Get the content of the default built-in rubric."""
    logger.info("Request received for default rubric.")
    return {"name": "Default Standard Rubric", "content": DEFAULT_RUBRIC}

@app.post("/generate-rubric/", tags=["Rubrics"])
async def generate_rubric(
    subject: str = Form(...),
    level: str = Form(...),
    criteria_count: int = Form(5),
    api_key: str = Form(...)
):
    """Generate a new rubric using AI based on subject, level, and criteria count."""
    logger.info(f"Request received to generate rubric: Subject='{subject}', Level='{level}', Criteria={criteria_count}")
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required for rubric generation.")
    if not subject or not level:
        raise HTTPException(status_code=400, detail="Subject and level are required.")
    if not (3 <= criteria_count <= 10):
        logger.warning(f"Invalid criteria count ({criteria_count}) requested. Clamping to range [3, 10].")
        criteria_count = max(3, min(criteria_count, 10))

    try:
        genai.configure(api_key=api_key)
        # Use a model suitable for generation tasks
        model = genai.GenerativeModel('gemini-1.5-flash') # Or 'gemini-1.5-pro' if flash isn't sufficient
        logger.info(f"Using model {model.model_name} for rubric generation.")

        prompt = f"""
        Generate an academic essay evaluation rubric tailored for the following specifications:
        - Subject: {subject}
        - Educational Level: {level}
        - Number of Criteria: {criteria_count}
        - Scoring Scale per Criterion: 0-10 points

        Instructions for the rubric structure:
        1. Start with a clear title line, incorporating the subject and level. Example: "{subject} Essay Rubric ({level})"
        2. List exactly {criteria_count} numbered criteria.
        3. For each criterion:
           - State the criterion name clearly (e.g., "Clarity of Argument", "Use of Evidence", "Organization").
           - Indicate the scoring scale: (0-10).
           - Provide 3-4 concise bullet points describing the key elements assessed under that criterion, appropriate for the specified level.
        4. Ensure the criteria are relevant to writing essays in the given {subject}.
        5. Do not add any introductory or concluding text outside the rubric itself. Just provide the rubric.

        Example Format Snippet (Do not copy this example's content):
        [Generated Title Line]

        1. Criterion Name One (0-10):
           - Bullet point description 1.
           - Bullet point description 2.
           - Bullet point description 3.

        2. Criterion Name Two (0-10):
           - Bullet point description 1.
           - Bullet point description 2.
           - Bullet point description 3.
           - Bullet point description 4.

        [... continue for all {criteria_count} criteria ...]
        """

        response = await model.generate_content_async(prompt)
        generated_text = response.text.strip()
        logger.info(f"AI generated rubric content (first 200 chars): {generated_text[:200]}...")

        # Basic validation: Check if it seems to follow the format roughly
        num_numbered_lines = len(re.findall(r"^\s*\d+\.", generated_text, re.MULTILINE))
        if num_numbered_lines < criteria_count * 0.8 or num_numbered_lines > criteria_count * 1.2: # Allow some flexibility
             logger.warning(f"Generated rubric might not have the expected number of criteria ({num_numbered_lines} found vs {criteria_count} requested).")
             # Still return it, but log a warning. Could add more robust validation.

        # Extract generated name (first line) if possible
        lines = generated_text.split('\n', 1)
        generated_name = lines[0].strip() if lines else f"Generated {subject} Rubric"

        return {
            "name": generated_name,
            "content": generated_text,
            "subject": subject,
            "level": level,
            "criteria_requested": criteria_count
        }

    except Exception as e:
        logger.error(f"Error generating rubric with AI: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate rubric using AI: {str(e)}")


@app.post("/upload-rubric-file/", tags=["Rubrics"])
async def upload_rubric_file(file: UploadFile):
    """Upload a rubric file (TXT or PDF) and return its text content."""
    logger.info(f"Request received to upload rubric file: {file.filename} (Type: {file.content_type})")
    if not file.filename or file.size == 0:
        raise HTTPException(status_code=400, detail="Cannot process an empty file.")

    # Check file extension explicitly
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith('.txt') or filename_lower.endswith('.pdf')):
        logger.warning(f"Rubric upload failed: Invalid file extension for '{file.filename}'. Only .txt and .pdf allowed.")
        raise HTTPException(status_code=400, detail="Invalid file type. Only .txt and .pdf files are supported for rubric upload.")

    # Attempt text extraction
    try:
        # Ensure correct content type for extract_text logic if needed
        if filename_lower.endswith('.txt') and file.content_type != 'text/plain':
             logger.debug(f"Adjusting content type for {file.filename} from {file.content_type} to text/plain based on extension.")
             file.content_type = 'text/plain'
        elif filename_lower.endswith('.pdf') and file.content_type != 'application/pdf':
             logger.debug(f"Adjusting content type for {file.filename} from {file.content_type} to application/pdf based on extension.")
             file.content_type = 'application/pdf'

        extracted_text = await extract_text(file)
        if not extracted_text.strip():
             logger.warning(f"Rubric upload: Extracted text from '{file.filename}' is empty.")
             # Decide whether to raise error or return empty text
             # Raising error might be better UX
             raise HTTPException(status_code=400, detail=f"The uploaded file '{file.filename}' contains no readable text.")

        logger.info(f"Successfully extracted text from uploaded rubric file: {file.filename}")
        return {"text": extracted_text, "filename": file.filename}

    except ValueError as e: # Errors from extract_text
        logger.error(f"Error extracting text from uploaded rubric file '{file.filename}': {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected server error during rubric file upload '{file.filename}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error processing rubric file: {str(e)}")


# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    # Read port from environment variable or default to 8000
    port = int(os.environ.get("PORT", 8000))
    # Read host from environment variable or default to "127.0.0.1" for local dev
    # Use "0.0.0.0" to make it accessible on the network
    host = os.environ.get("HOST", "127.0.0.1")
    # Read reload flag from environment, default to False (for production)
    # Set RELOAD=true in .env or environment for development
    reload_flag = os.environ.get("RELOAD", "false").lower() == "true"

    logger.info(f"Starting server on {host}:{port} | Reload: {reload_flag}")
    uvicorn.run("main:app", host=host, port=port, reload=reload_flag)