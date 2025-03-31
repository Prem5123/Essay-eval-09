# Fixes applied:
# 1. Removed redundant/misplaced logger.error and raise ValueError lines from the end of the `evaluate_essay` function (after the retry loop). The loop's internal logic already handles exit conditions (success return, specific error return, or raising an exception on final failure).

from fastapi import FastAPI, UploadFile, Form, HTTPException, Response, Body, File
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO
from docx import Document
import google.generativeai as genai
from reportlab.lib.pagesizes import letter
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
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
import traceback

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
    allow_origins=origins if origins != ['*'] else ["*"],
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

# In-memory storage for multi-essay PDF generation
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
        raise ve
    except Exception as e:
        logger.error(f"Unexpected error during text extraction for '{file.filename}': {str(e)}")
        raise ValueError(f"An unexpected error occurred while processing the file '{file.filename}'.")

def split_essays(text: str) -> List[str]:
    """Split text into multiple essays based on student name pattern."""
    logger.info("Attempting to split text into multiple essays.")
    patterns = [
        r"^\s*Student Name:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})",
        r"^\s*Student:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})",
        r"^\s*Name:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})"
    ]
    all_matches = []
    for pattern in patterns:
        matches = list(re.finditer(pattern, text, re.MULTILINE))
        all_matches.extend(matches)
    all_matches.sort(key=lambda m: m.start())
    logger.info(f"Found {len(all_matches)} potential student name markers using patterns.")

    if not all_matches:
        chunks = re.split(r'\n{4,}', text.strip())
        potential_essays = [chunk for chunk in chunks if len(chunk.strip()) > 200]
        if len(potential_essays) > 1:
            logger.info(f"No name markers found. Split text into {len(potential_essays)} essays based on newline separators.")
            return potential_essays
        else:
            logger.info("No clear separators found. Treating text as a single essay.")
            return [text]

    if len(all_matches) == 1:
        logger.info("Only one student name marker found. Treating as a single essay.")
        return [text]

    essays = []
    last_pos = 0
    for i, match in enumerate(all_matches):
        start_pos = match.start()
        if start_pos > last_pos:
            prev_segment = text[last_pos:start_pos].strip()
            # Include segment before first marker only if it's substantial
            # For subsequent segments, include if they are reasonably long (avoids small fragments between markers)
            if len(prev_segment) > 100:
                if i > 0:
                    essays.append(prev_segment)
                elif len(prev_segment) > 500: # Higher threshold for content before the *first* marker
                    logger.warning(f"Found substantial text ({len(prev_segment)} chars) before the first name marker. Including as separate segment.")
                    essays.append(prev_segment)

        if i == len(all_matches) - 1:
            # Append the rest of the text from the last marker
            essays.append(text[start_pos:])
        else:
            # Append text between current marker and the next marker
            next_start_pos = all_matches[i + 1].start()
            essays.append(text[start_pos:next_start_pos])
        last_pos = start_pos # Update last_pos for the next iteration's check

    # Final filter for substantial essays
    final_essays = [essay.strip() for essay in essays if len(essay.strip()) > 200]
    logger.info(f"Split text into {len(final_essays)} essays based on name markers.")
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
    base_delay = 1.5 # Base delay between API calls
    max_delay_increment = 1.0 # Max random addition to delay

    for i, essay_content in enumerate(essays):
        essay_num = i + 1
        if not essay_content.strip():
            logger.warning(f"Skipping empty essay segment #{essay_num}.")
            continue

        logger.info(f"Processing essay {essay_num}/{num_essays}...")
        preview = essay_content[:150].replace('\n', ' ').strip() + "..."
        logger.debug(f"Essay {essay_num} preview: {preview}")

        # Add delay before API call for essays after the first one
        if i > 0:
            delay = base_delay + random.uniform(0, max_delay_increment)
            logger.info(f"Waiting {delay:.2f}s before calling API for essay {essay_num} to avoid rate limits.")
            await asyncio.sleep(delay)

        try:
            evaluation = await evaluate_essay(essay_content, rubric_text, api_key)
            # Attempt to refine student name from evaluation result if possible
            student_name = evaluation.get('student_name', f'Unknown_{essay_num}')
            logger.info(f"Evaluation successful for essay {essay_num} (Student: {student_name})")
            results.append(evaluation)
        except Exception as e:
            logger.error(f"Error processing essay {essay_num}: {str(e)}", exc_info=True)
            # Attempt to extract name even if evaluation failed, for error reporting
            student_name = "Unknown"
            try:
                # Use the same patterns as evaluate_essay for consistency
                name_patterns = [ r"^\s*Student Name:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})", r"^\s*Name:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})", r"^\s*Student:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})", r"^\s*Author:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})", r"^\s*By:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})" ]
                first_lines = "\n".join(essay_content.split('\n')[:5])
                for pattern in name_patterns:
                    name_match = re.search(pattern, first_lines, re.IGNORECASE | re.MULTILINE)
                    if name_match:
                        student_name = name_match.group(1).strip()
                        break
                if student_name == "Unknown":
                   first_line = essay_content.split('\n')[0].strip()
                   if re.fullmatch(r"[A-Za-z'\-]+(?: [A-Za-z'\-]+){0,3}", first_line):
                       second_line = essay_content.split('\n')[1].strip() if len(essay_content.split('\n')) > 1 else ""
                       if not re.match(r"^(?:Student|Name|Date|Course|Professor|Assignment)", second_line, re.IGNORECASE):
                           student_name = first_line
            except Exception as name_extract_err:
                logger.warning(f"Could not extract student name from failed essay {essay_num}: {name_extract_err}")
                student_name = f"Failed_Essay_{essay_num}"

            # Create a placeholder error result
            results.append({
                "student_name": student_name,
                "overall_score": 0,
                "criteria": [{"name": "Processing Error", "score": 0, "max_score": 10, "feedback": f"Failed to evaluate: {str(e)}"}],
                "suggestions": ["Evaluation failed due to a processing error. Please check the essay content or API key/limits."],
                "highlighted_passages": [],
                "error": True
            })

    logger.info(f"Finished processing. Generated {len(results)} evaluation results.")
    return results

async def evaluate_essay(essay_text: str, rubric_text: str | None, api_key: str) -> dict:
    """Evaluate a single essay using the Gemini API with retry logic."""
    if not api_key:
        logger.error("API key is missing for evaluation.")
        raise ValueError("API key is required for evaluation.")

    genai.configure(api_key=api_key)
    # Consider making the model name configurable or using a more advanced model if needed
    model_name = 'gemini-1.5-flash' # Updated model name
    logger.info(f"Using Gemini model: {model_name}")
    model = genai.GenerativeModel(model_name)

    rubric = rubric_text if rubric_text and rubric_text.strip() else DEFAULT_RUBRIC
    logger.debug(f"Using rubric:\n{rubric[:300]}...")

    # --- Rubric Parsing ---
    # Fifth attempt: Regex specifically targeting format like "1. Name (X marks):"
    # Captures Name (Group 1) and Score (Group 2)
    criteria_pattern = r"^\s*(?:\d+\.\s*)?(.*?)\s*\((\d+)\s+marks?\)\s*:?$"
    logger.debug(f"Attempting to parse rubric with pattern for '(X marks)': {criteria_pattern}")
    logger.debug(f"Rubric Text for Parsing:\n---\n{rubric}\n---")

    criteria_names = []
    criteria_max_scores = []
    parsed_successfully = False
    try:
        # Iterate line by line for more control and better logging
        lines = rubric.strip().split('\n')
        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line: continue # Skip empty lines

            match = re.match(criteria_pattern, line)
            if match:
                # Group 1: Name, Group 2: Max Score
                name = match.group(1).strip()
                max_score_str = match.group(2)
                try:
                    max_score = int(max_score_str)
                    # Basic check for empty name
                    if not name:
                        logger.warning(f"Parsed criterion on line {line_num+1} has empty name. Line: '{line}'. Skipping.")
                        continue
                    criteria_names.append(name)
                    criteria_max_scores.append(max_score)
                    logger.info(f"Parsed Criterion: Name='{name}', Max Score={max_score} from line: '{line}'")
                    parsed_successfully = True # Mark as successful if at least one criterion is parsed
                except ValueError:
                    logger.warning(f"Could not convert extracted max score '{max_score_str}' to integer on line {line_num+1}: '{line}'. Skipping criterion.")
            else:
                 # Log lines that *don't* match if they look like they might be criteria
                 if re.match(r"^\s*\d+\.", line) or '(' in line and ')' in line:
                     logger.debug(f"Line {line_num+1} did not match expected '(X marks)' pattern: '{line}'")

        if not parsed_successfully:
             logger.warning("No criteria lines were successfully parsed using the '(X marks)' pattern.")
             # Trigger fallback explicitly
             raise ValueError("Failed to parse any criteria using the '(X marks)' pattern.")

    except Exception as parse_err:
        logger.error(f"Error during rubric parsing: {parse_err}. Falling back to default structure.", exc_info=True)
        # Fallback logic
        criteria_names = [] # Clear any partially parsed data
        criteria_max_scores = []
        logger.warning("Falling back to default structure: Estimating criteria count based on lines, assuming 10 points max per criterion.")
        num_lines = len(rubric.strip().split('\n'))
        # Estimate criteria count based on lines, capped at a reasonable number
        criteria_count_fallback = max(1, num_lines // 4) # Heuristic: ~4 lines per criterion
        criteria_count_fallback = min(criteria_count_fallback, 8) # Cap fallback
        criteria_names = [f"Criterion {i+1}" for i in range(criteria_count_fallback)]
        criteria_max_scores = [10] * criteria_count_fallback

    max_score_total = sum(criteria_max_scores) if criteria_max_scores else 50 # Default total if parsing fails
    criteria_count = len(criteria_names)

    # --- Student Name Extraction ---
    student_name = "Unknown"
    # Expanded list of patterns to catch more variations
    name_patterns = [
        r"^\s*Student Name:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})",
        r"^\s*Name:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})",
        r"^\s*Student:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})",
        r"^\s*Author:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})",
        r"^\s*By:\s+([A-Za-z]+(?: [A-Za-z'\-]+){0,3})"
    ]
    # Check the first few lines for efficiency
    first_lines = "\n".join(essay_text.split('\n')[:5])
    for pattern in name_patterns:
        # Use IGNORECASE for flexibility
        name_match = re.search(pattern, first_lines, re.IGNORECASE | re.MULTILINE)
        if name_match:
            student_name = name_match.group(1).strip()
            logger.info(f"Extracted student name: {student_name}")
            break

    # Fallback: If no pattern matches, check if the very first line looks like a name
    if student_name == "Unknown":
        first_line = essay_text.split('\n')[0].strip()
        # Check if the first line looks like a typical name format and isn't too long
        if re.fullmatch(r"[A-Za-z'\-]+(?: [A-Za-z'\-]+){0,3}", first_line) and len(first_line) < 30:
             # Add a check: ensure the *next* line doesn't start with common header keywords
             second_line = essay_text.split('\n')[1].strip() if len(essay_text.split('\n')) > 1 else ""
             if not re.match(r"^(?:Student|Name|Date|Course|Professor|Assignment|Class|ID)", second_line, re.IGNORECASE):
                 student_name = first_line
                 logger.info(f"Extracted student name from first line: {student_name}")

    # --- Prompt Construction ---
    # Carefully craft the prompt for the AI
    prompt = f"""
    Please act as an academic evaluator. Evaluate the following essay based STRICTLY on the provided rubric.

    **Evaluation Task:**
    1. Read the essay carefully.
    2. Use ONLY the criteria and scoring scales defined in the RUBRIC section below.
    3. Score each criterion numerically based on its specified maximum score (e.g., 0-{criteria_max_scores[0] if criteria_max_scores else 10}).
    4. Provide concise, specific feedback for EACH criterion, explaining the score given. **Include a brief 'Mini-Lesson' within the feedback for each criterion**, explaining the underlying principle or offering a general tip related to that criterion (e.g., for 'Thesis', explain what makes a strong thesis).
    5. Calculate the `overall_score` as the simple sum of the individual criteria scores.
    6. Provide 3-5 overall `suggestions` for improvement, focusing on the most impactful areas based on the rubric.
    7. Identify **5-7** specific `highlighted_passages` from the essay text that exemplify areas needing improvement or demonstrating strengths related to the rubric. For each passage:
        * Quote the exact text (`text`, keep under 120 chars).
        * Briefly explain the `issue` or `strength` according to the rubric criteria.
        * Offer a concrete `suggestion` for fixing it (if an issue) or explain why it's effective (if a strength).
        * Optionally provide a short `example_revision` (if an issue).
    8. Output the evaluation ONLY in the following JSON format. Ensure the JSON is valid. Do not include ```json markers or any text outside the JSON structure.

    **RUBRIC:**
    {rubric}

    **Essay:**
    {essay_text}


**JSON Output Format:**
{{
    "student_name": "{student_name}",
    "overall_score": number (Sum of criteria scores, max {max_score_total}),
    "criteria": [
        {{
            "name": "{criteria_names[0] if criteria_names else 'Criterion 1'}",
            "score": number (0-{criteria_max_scores[0] if criteria_max_scores else 10}),
            "max_score": {criteria_max_scores[0] if criteria_max_scores else 10},
            "feedback": "Specific feedback for Criterion 1 based on the essay.",
            "mini_lesson": "Brief explanation/tip related to Criterion 1."
        }},
        // ... Repeat for ALL {criteria_count} criteria from the rubric ({criteria_names[-1] if criteria_names else 'Criterion N'})
        {{
            "name": "{criteria_names[-1] if criteria_count > 0 else 'Criterion N'}",
            "score": number (0-{criteria_max_scores[-1] if criteria_count > 0 else 10}),
            "max_score": {criteria_max_scores[-1] if criteria_count > 0 else 10},
            "feedback": "Specific feedback for Criterion {criteria_count}.",
            "mini_lesson": "Brief explanation/tip related to Criterion {criteria_count}."
        }}
    ],
    "suggestions": [
        "Overall suggestion 1.",
        "Overall suggestion 2.",
        "Overall suggestion 3."
        // ... up to 5 suggestions
    ],
    "highlighted_passages": [
        {{
            "text": "Exact phrase from essay...",
            "issue": "Specific problem (e.g., unclear topic sentence, weak evidence) OR Strength (e.g., strong transition).",
            "suggestion": "How to improve this specific phrase/sentence OR Why this is effective.",
            "example_revision": "Optional: Rewritten example (if issue)."
        }}
        // ... Repeat for 5-7 passages
    ]
}}
"""

    # --- API Call with Retry Logic ---
    max_retries = 3
    base_delay = 2.0 # Initial delay in seconds

    for attempt in range(max_retries):
        logger.info(f"Attempt {attempt + 1}/{max_retries} to call Gemini API for student: {student_name}")
        try:
            # Make the API call asynchronously
            response = await model.generate_content_async(prompt)
            raw_response_text = response.text
            logger.debug(f"Raw API response (first 500 chars): {raw_response_text[:500]}")

            # Clean potential markdown formatting around the JSON
            cleaned_response = re.sub(r'^```json\s*|\s*```$', '', raw_response_text, flags=re.MULTILINE | re.DOTALL).strip()

            # Attempt to parse the JSON response
            try:
                result = json.loads(cleaned_response)
                logger.info("Successfully parsed JSON response from API.")
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON parsing failed: {json_err}. Raw response snippet: {cleaned_response[:500]}...")
                # Attempt a simple fix for trailing commas before giving up
                fixed_json_str = re.sub(r',\s*([\}\]])', r'\1', cleaned_response) # Remove trailing commas before } or ]
                try:
                    result = json.loads(fixed_json_str)
                    logger.info("JSON parsed successfully after simple fix (trailing comma).")
                except json.JSONDecodeError:
                    logger.error("JSON parsing failed even after simple fix. Raising error.")
                    # If parsing fails even after fix, raise a specific error for this attempt
                    raise ValueError(f"Failed to parse JSON response from API: {json_err}")

            # --- Response Validation and Sanitization ---
            logger.info("Validating and sanitizing evaluation result structure.")
            # Ensure essential keys exist, using extracted name as default
            result.setdefault("student_name", student_name)
            result.setdefault("overall_score", 0)
            result.setdefault("criteria", [])
            result.setdefault("suggestions", [])
            result.setdefault("highlighted_passages", [])

            # Validate 'criteria' structure, prioritizing AI's response structure
            validated_criteria = []
            api_criteria_raw = result.get("criteria", [])
            expected_criteria_lookup = {name.strip().lower(): max_score for name, max_score in zip(criteria_names, criteria_max_scores)}

            if isinstance(api_criteria_raw, list):
                logger.info(f"Processing {len(api_criteria_raw)} criteria items returned by API.")
                for i, api_item in enumerate(api_criteria_raw):
                    if not isinstance(api_item, dict):
                        logger.warning(f"Skipping invalid criteria item #{i} from API (not a dictionary).")
                        continue

                    # Get name and feedback directly from AI response
                    ai_name = str(api_item.get("name", f"Unnamed Criterion {i+1}")).strip()
                    ai_feedback = api_item.get("feedback", "No feedback provided.")
                    ai_score_raw = api_item.get("score", 0)

                    # Try to find the corresponding max_score from the parsed rubric
                    ai_name_lower = ai_name.lower()
                    expected_max = 10 # Default max score
                    if ai_name_lower in expected_criteria_lookup:
                        expected_max = expected_criteria_lookup[ai_name_lower]
                        logger.debug(f"Matched AI criterion '{ai_name}' to expected max score: {expected_max}")
                    else:
                        # Attempt partial matching or log if no match found
                        found_partial = False
                        for expected_name_lower, max_s in expected_criteria_lookup.items():
                             # Simple substring check (can be improved)
                             if expected_name_lower in ai_name_lower or ai_name_lower in expected_name_lower:
                                 expected_max = max_s
                                 logger.warning(f"Partially matched AI criterion '{ai_name}' to expected '{expected_name_lower}' (Max Score: {expected_max}). Using this max score.")
                                 found_partial = True
                                 break
                        if not found_partial:
                             logger.warning(f"Could not confidently match AI criterion '{ai_name}' to any expected criterion name. Using default max score {expected_max}.")


                    # Sanitize score
                    try:
                        score_val = float(ai_score_raw)
                        # Clamp score between 0 and the determined max_score
                        sanitized_score = max(0.0, min(score_val, float(expected_max)))
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid score format for AI criterion '{ai_name}'. API value: '{ai_score_raw}'. Setting score to 0.")
                        sanitized_score = 0.0

                    # Append the validated criterion using AI's name and feedback
                    validated_criteria.append({
                        "name": ai_name, # Use the name from the AI response
                        "score": sanitized_score,
                        "max_score": expected_max, # Use the matched or default max score
                        "feedback": ai_feedback # Use the feedback from the AI response
                    })
            else:
                # Handle cases where API 'criteria' isn't a list or is missing
                logger.error("API response 'criteria' field was missing, not a list, or malformed. Cannot process criteria.")
                # Optionally, create placeholders based on expected criteria if needed for structure
                # validated_criteria = [{"name": name, "score": 0, "max_score": max_s, "feedback": "Error: AI criteria data missing/malformed."} for name, max_s in zip(criteria_names, criteria_max_scores)]
                # For now, just leave it empty if the API response is bad

            result["criteria"] = validated_criteria
            logger.info(f"Final processed criteria count: {len(validated_criteria)}")

            # --- Score Recalculation & Final Validation --- (Keep this part as is)
            # Recalculate overall score based on sanitized criteria scores for consistency
            calculated_score = sum(c.get('score', 0.0) for c in result["criteria"])
            api_overall = result.get("overall_score")

            # Compare calculated score with API's score, log discrepancy if significant
            if isinstance(api_overall, (int, float)):
                if abs(api_overall - calculated_score) > 0.1: # Allow small floating point differences
                    logger.warning(f"API overall score ({api_overall}) differs significantly from calculated sum ({calculated_score:.2f}) based on processed criteria. Trusting calculated sum for consistency.")
                    result["overall_score"] = calculated_score
                else:
                    # If scores are close, trust the API's value (might handle rounding differently)
                    logger.debug(f"API overall score ({api_overall}) and calculated score ({calculated_score:.2f}) match or are close. Using API score.")
                    result["overall_score"] = api_overall
            else:
                # If API score is missing or invalid, use the calculated sum
                logger.warning(f"API overall score missing or invalid ('{api_overall}'). Using calculated sum ({calculated_score:.2f}).")
                result["overall_score"] = calculated_score

            # Ensure the final overall score is within the valid range (0 to total max score)
            final_max_score = sum(c.get('max_score', 10.0) for c in result["criteria"])
            result["overall_score"] = max(0.0, min(result["overall_score"], final_max_score))

            # Sanitize suggestions (ensure they are strings)
            result["suggestions"] = [str(s) for s in result.get("suggestions", []) if isinstance(s, (str, int, float))]

            # Sanitize highlighted passages (ensure structure and limit length)
            validated_passages = []
            for p in result.get("highlighted_passages", []):
                if isinstance(p, dict):
                    p.setdefault("text", "")
                    p.setdefault("issue", "")
                    p.setdefault("suggestion", "")
                    p.setdefault("example_revision", "")
                    # Truncate text to avoid overly long passages
                    p["text"] = p["text"][:150]
                    validated_passages.append(p)
            # Limit the number of passages
            result["highlighted_passages"] = validated_passages[:7] # Limit to max 7

            logger.info(f"Evaluation validated for student: {student_name}. Final Score: {result['overall_score']:.1f}/{final_max_score:.1f}")
            # If successful, return the validated result and exit the function
            return result

        except genai.types.generation_types.BlockedPromptException as bpe:
            # Handle specific case where the prompt/content is blocked
            logger.error(f"API call blocked due to safety settings or prompt issues for student {student_name}: {bpe}")
            # Raise a user-friendly error immediately, no retry needed
            raise ValueError(f"Evaluation failed: The prompt or essay content was blocked by safety filters. Please review the content.") from bpe

        except Exception as e:
            # Handle other errors (network, API issues, parsing errors raised above, etc.)
            error_str = str(e).lower()
            logger.error(f"Error during API call or processing (Attempt {attempt + 1}): {error_str}", exc_info=True)

            # Check if it's a rate limit error (common codes/messages)
            is_rate_limit = "429" in error_str or "rate limit" in error_str or "quota exceeded" in error_str or "resource exhausted" in error_str

            if is_rate_limit and attempt < max_retries - 1:
                # If rate limited and retries remain, wait with exponential backoff + jitter
                delay = (base_delay * (2 ** attempt)) + random.uniform(0.5, 1.5)
                logger.warning(f"Rate limit detected. Retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)
                continue # Go to the next iteration of the loop

            elif is_rate_limit:
                # If rate limited and no retries left, return a specific error dictionary
                logger.error(f"Rate limit error persisted after {max_retries} attempts. Failing evaluation for {student_name}.")
                return {
                    "student_name": student_name,
                    "overall_score": 0,
                    "max_score_total": max_score_total, # Provide context
                    "criteria": [{"name": "API Error", "score": 0, "max_score": max_score_total, "feedback": "Evaluation failed due to API rate limits after multiple retries."}],
                    "suggestions": ["Could not evaluate due to rate limits. Try again later or with fewer concurrent requests."],
                    "highlighted_passages": [],
                    "error": True,
                    "error_type": "rate_limit" # Specific error type
                }

            else: # Handle non-rate-limit errors
                if attempt < max_retries - 1:
                    # If other error and retries remain, wait a short fixed time + jitter
                    await asyncio.sleep(1.0 + random.uniform(0, 0.5))
                    continue # Go to the next iteration
                else:
                    # If other error and no retries left, raise the exception to be caught by evaluate_essays
                    logger.error(f"Non-rate-limit error persisted after {max_retries} attempts. Failing evaluation for {student_name}.")
                    raise ValueError(f"Failed to evaluate essay after {max_retries} attempts due to API/processing error: {str(e)}") from e

    # FIX: Removed the redundant error logging and raise statement that were here.
    # The logic within the loop should handle all exit scenarios (return on success/rate limit failure, raise on other persistent errors).
    # If this point is reached, it indicates a flaw in the loop's logic, but adding a raise here hides that.

# PDF Report Generation Class
class PDFReport:
    """Generate a PDF report from evaluation data using BaseDocTemplate."""
    # Define color constants for styling
    HEADER_COLOR = colors.HexColor('#1a365d') # Dark Blue
    ACCENT_COLOR = colors.HexColor('#3b82f6') # Medium Blue
    LIGHT_BG = colors.HexColor('#f3f4f6')    # Light Gray BG
    SUCCESS_COLOR = colors.HexColor('#10b981') # Green
    WARNING_COLOR = colors.HexColor('#f59e0b') # Amber
    DANGER_COLOR = colors.HexColor('#ef4444')  # Red
    TEAL_COLOR = colors.HexColor('#14b8a6')    # Teal
    HIGHLIGHT_COLOR = colors.HexColor('#fef9c3')# Light Yellow Highlight
    TEXT_COLOR = colors.HexColor('#1f2937')    # Dark Gray Text
    FONT_NAME = 'Helvetica'
    BOLD_FONT = 'Helvetica-Bold'

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()
        # Attributes for header/footer customization if needed later
        self.page_num_font = self.FONT_NAME
        self.page_num_size = 8

    def _create_custom_styles(self):
        """Create custom ParagraphStyle objects for the report."""
        self.styles.add(ParagraphStyle(name='Base', fontName=self.FONT_NAME, fontSize=10, textColor=self.TEXT_COLOR, leading=14))
        self.styles.add(ParagraphStyle(name='MainTitle', parent=self.styles['h1'], fontName=self.BOLD_FONT, fontSize=20, spaceAfter=10, alignment=TA_CENTER, textColor=self.HEADER_COLOR))
        self.styles.add(ParagraphStyle(name='StudentTitle', parent=self.styles['h2'], fontName=self.FONT_NAME, fontSize=14, spaceAfter=6, alignment=TA_CENTER, textColor=self.ACCENT_COLOR))
        self.styles.add(ParagraphStyle(name='ScoreTitle', parent=self.styles['h3'], fontName=self.BOLD_FONT, fontSize=12, spaceAfter=18, alignment=TA_CENTER)) # Adjusted space
        self.styles.add(ParagraphStyle(name='SectionTitle', parent=self.styles['h2'], fontName=self.BOLD_FONT, fontSize=14, spaceAfter=10, textColor=self.HEADER_COLOR, borderPadding=5, borderColor=self.LIGHT_BG, borderWidth=1, backColor=self.LIGHT_BG, borderRadius=5))
        self.styles.add(ParagraphStyle(name='TableHeader', parent=self.styles['Base'], fontName=self.BOLD_FONT, alignment=TA_CENTER, textColor=colors.white))
        self.styles.add(ParagraphStyle(name='TableCell', parent=self.styles['Base'], alignment=TA_LEFT, leading=12))
        self.styles.add(ParagraphStyle(name='TableCellBold', parent=self.styles['TableCell'], fontName=self.BOLD_FONT))
        self.styles.add(ParagraphStyle(name='TableCellCenter', parent=self.styles['TableCell'], alignment=TA_CENTER))
        self.styles.add(ParagraphStyle(name='FeedbackCell', parent=self.styles['TableCell'], fontSize=9)) # Smaller font for feedback
        self.styles.add(ParagraphStyle(name='SuggestionItem', parent=self.styles['Base'], leftIndent=15, bulletIndent=0, spaceBefore=5))
        # Styles for highlighted passages
        self.styles.add(ParagraphStyle(name='HighlightBox', parent=self.styles['Base'], fontSize=9, borderPadding=5, borderColor=self.TEAL_COLOR, borderWidth=0.5, borderRadius=3, spaceAfter=5, backColor=colors.HexColor('#f0fdfa'))) # Light teal BG
        self.styles.add(ParagraphStyle(name='HighlightText', parent=self.styles['Base'], fontSize=9, backColor=self.HIGHLIGHT_COLOR, textColor=colors.black)) # Use defined highlight color
        self.styles.add(ParagraphStyle(name='IssueText', parent=self.styles['Base'], fontSize=9, textColor=self.DANGER_COLOR, leftIndent=10, spaceBefore=2))
        self.styles.add(ParagraphStyle(name='SuggestText', parent=self.styles['Base'], fontSize=9, textColor=self.ACCENT_COLOR, leftIndent=10, spaceBefore=2))
        self.styles.add(ParagraphStyle(name='ExampleText', parent=self.styles['Base'], fontSize=9, textColor=self.SUCCESS_COLOR, leftIndent=10, fontName='Helvetica-Oblique', spaceBefore=2))
        # Footer Style
        self.styles.add(ParagraphStyle(name='Footer', parent=self.styles['Base'], alignment=TA_CENTER, fontSize=8, textColor=colors.grey))

    def _get_score_color(self, score, max_score):
        """Determine text color based on score percentage."""
        if max_score == 0: return self.TEXT_COLOR # Avoid division by zero
        percentage = score / max_score
        if percentage >= 0.8: return self.SUCCESS_COLOR
        if percentage >= 0.6: return self.ACCENT_COLOR
        if percentage >= 0.4: return self.WARNING_COLOR
        return self.DANGER_COLOR

    def _header(self, canvas, doc):
        """Draw header on each page."""
        canvas.saveState()
        canvas.setFont(self.FONT_NAME, 9)
        canvas.setFillColor(colors.grey)
        header_y = doc.height + doc.topMargin - 0.5*inch # Position below top margin
        canvas.drawString(doc.leftMargin, header_y, "Essay Evaluation Report")
        page_num_text = f"Page {canvas.getPageNumber()}"
        canvas.drawRightString(doc.width + doc.leftMargin, header_y, page_num_text)
        canvas.restoreState()

    def _footer(self, canvas, doc):
        """Draw footer on each page."""
        canvas.saveState()
        canvas.setFont(self.page_num_font, self.page_num_size)
        canvas.setFillColor(colors.grey)
        footer_y = doc.bottomMargin - 0.5*inch # Position above bottom margin
        footer_text = f"Page {canvas.getPageNumber()} | Generated by AI Essay Grader"
        # Use drawCentredString for automatic centering
        canvas.drawCentredString(doc.leftMargin + doc.width / 2.0, footer_y, footer_text)
        canvas.restoreState()

    def create(self, evaluation: dict) -> BytesIO:
        """Generate the PDF document."""
        pdf_buffer = BytesIO()
        # Use BaseDocTemplate for header/footer support
        doc = BaseDocTemplate(pdf_buffer, pagesize=letter,
                              rightMargin=0.75*inch, leftMargin=0.75*inch,
                              topMargin=1*inch, bottomMargin=1*inch) # Standard margins

        # Define the main frame where content will flow
        main_frame = Frame(doc.leftMargin, doc.bottomMargin,
                           doc.width, doc.height,
                           id='main_frame')

        # Create a PageTemplate using the frame (REMOVED header/footer callbacks)
        main_template = PageTemplate(id='main',
                                     frames=[main_frame])
                                     # onPage=self._header,      # Removed header
                                     # onPageEnd=self._footer)   # Removed footer
        doc.addPageTemplates([main_template])

        elements = [] # List to hold ReportLab flowables
        student_name_for_log = evaluation.get('student_name', 'Unknown')
        logger.info(f"Starting PDF creation (using PageTemplate) for: {student_name_for_log}")

        try:
            # --- Extract data from evaluation dictionary ---
            student_name = evaluation.get("student_name", "Unknown Student")
            criteria = evaluation.get("criteria", [])
            suggestions = evaluation.get("suggestions", [])
            highlighted_passages = evaluation.get("highlighted_passages", [])
            overall_score = evaluation.get("overall_score", 0.0)

            # Calculate max score dynamically from criteria data
            max_score_total = sum(float(c.get("max_score", 10)) for c in criteria)
            # Fallback max score if criteria are missing or malformed
            if max_score_total == 0 and criteria: max_score_total = len(criteria) * 10
            elif not criteria: max_score_total = 10 # Absolute fallback

            score_color = self._get_score_color(overall_score, max_score_total)

            # --- Build PDF Elements ---
            elements.append(Paragraph("Essay Evaluation Report", self.styles['MainTitle']))
            elements.append(Paragraph(f"Student: {student_name}", self.styles['StudentTitle']))
            elements.append(Paragraph(
                f"Overall Score: <font color='{score_color.hexval()}'><b>{overall_score:.1f}</b></font> / {max_score_total:.1f}",
                self.styles['ScoreTitle']
            ))

            # --- Criteria Table ---
            if criteria:
                elements.append(Paragraph("Evaluation Breakdown", self.styles['SectionTitle']))
                elements.append(Spacer(1, 0.15*inch)) # Space before table

                # Table Header Row (using Paragraphs for styling)
                table_data = [
                    [Paragraph('Criterion', self.styles['TableHeader']),
                     Paragraph('Score', self.styles['TableHeader']),
                     Paragraph('Feedback', self.styles['TableHeader'])]
                ]

                # Table Style Definition
                table_style = TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), self.HEADER_COLOR), # Header row background
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),      # Header text color
                    ('FONTNAME', (0,0), (-1,0), self.BOLD_FONT),     # Header font
                    ('ALIGN', (0,0), (-1,0), 'CENTER'),              # Header alignment
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),               # Vertical alignment for all cells
                    ('ALIGN', (1,1), (1,-1), 'CENTER'),              # Center align score column
                    ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey), # Grid lines
                    ('LEFTPADDING', (0,0), (-1,-1), 6),              # Padding
                    ('RIGHTPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.white]), # Alternating row colors
                ])

                # Populate table rows
                for i, crit in enumerate(criteria):
                    name = crit.get("name", f"Criterion {i+1}")
                    score = float(crit.get("score", 0))
                    max_score = float(crit.get("max_score", 10))
                    if max_score == 0: max_score = 10 # Avoid division by zero in color calc
                    feedback_text = crit.get("feedback", "N/A")
                    mini_lesson_text = crit.get("mini_lesson") # Get the new field
                    crit_score_color = self._get_score_color(score, max_score)

                    # Combine feedback and mini-lesson if available
                    full_feedback = feedback_text
                    if mini_lesson_text and isinstance(mini_lesson_text, str) and mini_lesson_text.strip():
                        full_feedback += f"<br/><br/><i>Mini-Lesson:</i> {mini_lesson_text}"

                    table_data.append([
                        Paragraph(name, self.styles['TableCellBold']), # Criterion name (bold)
                        Paragraph(f"<font color='{crit_score_color.hexval()}'>{score:.1f}</font> / {max_score:.1f}", self.styles['TableCellCenter']), # Score (colored, centered)
                        Paragraph(full_feedback, self.styles['FeedbackCell']) # Combined feedback (smaller font)
                    ])

                # Define column widths (adjust as needed)
                col_widths = [2.0*inch, 0.8*inch, 4.2*inch] # Total = 7 inches (fits within 7.5" width - margins)
                criteria_table = Table(table_data, colWidths=col_widths, style=table_style, repeatRows=1) # Repeat header row on page break
                elements.append(criteria_table)
                elements.append(Spacer(1, 0.3*inch)) # Space after table
            else:
                elements.append(Paragraph("No evaluation criteria data available.", self.styles['Base']))
                elements.append(Spacer(1, 0.3*inch))

            # --- Highlighted Passages ---
            if highlighted_passages:
                elements.append(Paragraph("Areas for Improvement / Strengths", self.styles['SectionTitle'])) # Updated title
                elements.append(Spacer(1, 0.15*inch))

                for i, passage in enumerate(highlighted_passages, 1):
                    if not isinstance(passage, dict): continue # Skip if not a dict

                    text = passage.get("text", "N/A").replace('\n', ' ') # Ensure single line
                    issue = passage.get("issue", "N/A")
                    suggestion = passage.get("suggestion", "N/A")
                    example = passage.get("example_revision", "") # Optional example

                    # Build content for the passage box using Paragraphs
                    passage_elements = [
                        Paragraph(f"<b>Passage {i}:</b> <font name='Courier' size='9'><backColor='{self.HIGHLIGHT_COLOR.hexval()}'> {text} </backColor></font>", self.styles['Base']), # Highlighted text
                        Paragraph(f"<b>Issue/Strength:</b> {issue}", self.styles['IssueText']), # Use IssueText style (red)
                        Paragraph(f"<b>Suggestion/Rationale:</b> {suggestion}", self.styles['SuggestText']), # Use SuggestText style (blue)
                    ]
                    if example:
                        passage_elements.append(Paragraph(f"<b>Example Revision:</b> {example}", self.styles['ExampleText'])) # Use ExampleText style (green, italic)

                    # Put passage elements into a Table to create a bordered box
                    box_width = doc.width # Use full frame width
                    box_table = Table([[passage_elements]], colWidths=[box_width], style=TableStyle([
                        ('BOX', (0,0), (-1,-1), 0.5, self.TEAL_COLOR), # Border color
                        ('LEFTPADDING', (0,0), (-1,-1), 10),
                        ('RIGHTPADDING', (0,0), (-1,-1), 10),
                        ('TOPPADDING', (0,0), (-1,-1), 8),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')) # Very light background inside box
                    ]))
                    elements.append(box_table)
                    elements.append(Spacer(1, 0.15*inch)) # Space between boxes
                elements.append(Spacer(1, 0.15*inch)) # Extra space after the last box

            # --- General Suggestions ---
            if suggestions:
                elements.append(Paragraph("General Suggestions", self.styles['SectionTitle']))
                elements.append(Spacer(1, 0.15*inch))
                for sug in suggestions:
                    # Use bullet points for suggestions
                    elements.append(Paragraph(str(sug), self.styles['SuggestionItem'], bulletText=f'\u2022')) # Unicode bullet
                elements.append(Spacer(1, 0.3*inch)) # Space after suggestions

            # --- Build the PDF ---
            if not elements:
                # Handle case where absolutely no content was generated
                logger.warning(f"No content elements generated for PDF report: {student_name_for_log}. PDF will be minimal.")
                elements.append(Paragraph("No content available for this report.", self.styles['Base']))

            doc.build(elements)

            # Check if the buffer actually contains data
            pdf_buffer.seek(0)
            pdf_content = pdf_buffer.getvalue()
            pdf_size = len(pdf_content)

            if pdf_size > 0:
                logger.info(f"PDF created successfully (using PageTemplate) for {student_name_for_log}. Size: {pdf_size} bytes.")
                pdf_buffer.seek(0) # Rewind buffer before returning
                return pdf_buffer
            else:
                # This case should be rare if doc.build ran without error, but handle defensively
                logger.error(f"PDF generation (using PageTemplate) resulted in an empty buffer for {student_name_for_log} despite attempting to build content.")
                return self._generate_minimal_error_pdf(evaluation, "Empty buffer after build")

        except Exception as e:
            logger.error(f"Critical error during PDF generation (using PageTemplate) for {evaluation.get('student_name', 'Unknown')}: {e}", exc_info=True)
            # Generate a fallback error PDF
            return self._generate_minimal_error_pdf(evaluation, str(e))

    def _generate_minimal_error_pdf(self, evaluation: dict, error_msg: str) -> BytesIO:
        """Creates a simple PDF indicating an error occurred during generation."""
        # Import SimpleDocTemplate locally for this fallback case
        from reportlab.platypus import SimpleDocTemplate
        pdf_buffer_err = BytesIO()
        try:
            doc_err = SimpleDocTemplate(pdf_buffer_err, pagesize=letter)
            error_elements = [
                Paragraph("Error Generating Report", self.styles['MainTitle']), # Use existing styles
                Spacer(1, 0.5*inch),
                Paragraph(f"An unexpected error occurred while generating the PDF report for student: '{evaluation.get('student_name', 'Unknown')}'.", self.styles['Base']),
                Spacer(1, 0.2*inch),
                Paragraph(f"Error details: {error_msg}", self.styles['Base']),
                Spacer(1, 0.2*inch),
                Paragraph("Please check the server logs for more information or try again.", self.styles['Base'])
            ]
            doc_err.build(error_elements)
            pdf_buffer_err.seek(0)
            logger.info("Generated minimal error PDF.")
        except Exception as build_err:
            # If even the error PDF fails, log and return empty buffer
            logger.error(f"Failed even to build the minimal error PDF: {build_err}", exc_info=True)
            return BytesIO() # Return empty buffer
        return pdf_buffer_err

# Rubric Management Functions
def get_rubric_dir():
    """Returns the path to the rubrics directory."""
    return "rubrics"

def get_saved_rubrics():
    """Lists saved rubrics with ID, name, and preview."""
    rubrics = []
    rubrics_dir = get_rubric_dir()
    if not os.path.exists(rubrics_dir):
        return [] # Return empty list if directory doesn't exist

    for filename in os.listdir(rubrics_dir):
        if filename.endswith(".txt"):
            rubric_id = filename[:-4] # Use filename without extension as ID
            filepath = os.path.join(rubrics_dir, filename)
            try:
                with open(filepath, "r", encoding='utf-8') as f:
                    content = f.read()
                # Attempt to parse name from the first non-empty line
                lines = content.strip().split('\n')
                first_non_empty_line = next((line.strip() for line in lines if line.strip()), None)
                # Use first line as name if it's relatively short and doesn't look like criteria
                if first_non_empty_line and len(first_non_empty_line) < 80 and not re.match(r"^\s*\d+\.", first_non_empty_line):
                    name = first_non_empty_line
                else:
                    name = f"Rubric {rubric_id[:8]}" # Fallback name

                # Generate preview
                preview = content[:150].replace('\n', ' ') + ('...' if len(content) > 150 else '')
                rubrics.append({ "id": rubric_id, "name": name, "preview": preview })
            except Exception as e:
                logger.error(f"Error reading rubric file {filename}: {e}")
                continue # Skip this file

    rubrics.sort(key=lambda x: x['name'].lower()) # Sort alphabetically by name
    logger.info(f"Found {len(rubrics)} saved rubrics.")
    return rubrics

def save_rubric(content: str, name: Optional[str] = None, rubric_id: Optional[str] = None) -> str:
    """Saves rubric content to a file, optionally prepending a name."""
    if not rubric_id:
        rubric_id = str(uuid.uuid4()) # Generate new ID if not provided

    rubrics_dir = get_rubric_dir()
    filepath = os.path.join(rubrics_dir, f"{rubric_id}.txt")

    # Check if name is provided and if it should be prepended
    content_to_save = content.strip()
    lines = content_to_save.split('\n')
    first_line_content = lines[0].strip() if lines else ""

    # Prepend name if provided AND it's different from the first line of the content
    if name and name.strip() != first_line_content:
        content_to_save = f"{name.strip()}\n\n{content_to_save}"
        logger.info(f"Prepending provided name '{name}' to rubric content for ID {rubric_id}.")

    try:
        with open(filepath, "w", encoding='utf-8') as f:
            f.write(content_to_save)
        logger.info(f"Rubric '{name or rubric_id}' saved successfully to {filepath}.")
        return rubric_id
    except Exception as e:
        logger.error(f"Error saving rubric {rubric_id}: {e}")
        raise IOError(f"Could not save rubric file: {e}")

def get_rubric_by_id(rubric_id: str) -> tuple[str, Optional[str]]:
    """Retrieves rubric content and optionally a name from the first line."""
    rubrics_dir = get_rubric_dir()
    # Sanitize rubric_id to prevent directory traversal (though UUIDs are generally safe)
    if not re.match(r'^[\w-]+$', rubric_id):
         logger.error(f"Invalid rubric ID format requested: {rubric_id}")
         raise ValueError(f"Invalid rubric ID format.")

    filepath = os.path.join(rubrics_dir, f"{rubric_id}.txt")

    try:
        with open(filepath, "r", encoding='utf-8') as f:
            content = f.read()

        lines = content.strip().split('\n')
        potential_name = lines[0].strip() if lines else None
        actual_content = content # Default to full content

        # Check if the first line looks like a distinct name/title
        # Conditions: not empty, relatively short, doesn't start like a numbered criterion
        is_likely_name = potential_name and len(potential_name) < 80 and not re.match(r"^\s*\d+\.", potential_name)

        # Check if there's content *after* the potential name line (and maybe a blank line)
        has_subsequent_content = False
        if len(lines) > 1:
            if lines[1].strip() == "" and len(lines) > 2: # Name, blank line, content
                has_subsequent_content = True
                actual_content = "\n".join(lines[2:])
            elif lines[1].strip() != "": # Name, content (no blank line)
                 has_subsequent_content = True
                 actual_content = "\n".join(lines[1:])

        if is_likely_name and has_subsequent_content:
            name = potential_name
            logger.info(f"Found rubric '{rubric_id}' with name '{name}'.")
            return actual_content.strip(), name
        else:
            # If first line isn't distinct or there's no content after it, treat whole file as content
            logger.info(f"Found rubric '{rubric_id}', no distinct name parsed/used from first line.")
            return content.strip(), None # Return full content, no name

    except FileNotFoundError:
        logger.warning(f"Rubric file not found for ID: {rubric_id}")
        raise ValueError(f"Rubric with ID {rubric_id} not found")
    except Exception as e:
        logger.error(f"Error reading rubric {rubric_id}: {e}")
        raise IOError(f"Could not read rubric file: {e}")

def delete_rubric(rubric_id: str) -> bool:
    """Deletes a rubric file by ID."""
    rubrics_dir = get_rubric_dir()
    # Sanitize rubric_id
    if not re.match(r'^[\w-]+$', rubric_id):
         logger.error(f"Invalid rubric ID format for deletion: {rubric_id}")
         return False

    filepath = os.path.join(rubrics_dir, f"{rubric_id}.txt")
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Deleted rubric file: {filepath}")
            return True
        else:
            logger.warning(f"Attempted to delete non-existent rubric: {rubric_id}")
            # Return False here, let endpoint return 404
            return False
    except Exception as e:
        logger.error(f"Error deleting rubric {rubric_id}: {e}")
        # Return False here, let endpoint return 500
        return False


# API Endpoints
@app.post("/verify_api_key/", tags=["API Key"])
async def verify_api_key(api_key: str = Form(...)):
    """Verifies if the provided Google Generative AI key is valid."""
    if not api_key or len(api_key) < 20: # Basic sanity check
        logger.warning("API key verification failed: Key is too short or empty.")
        raise HTTPException(status_code=400, detail="API key is too short or appears invalid.")

    logger.info(f"Verifying API key (showing first 5 chars): {api_key[:5]}...")
    try:
        genai.configure(api_key=api_key)
        # List models as a simple way to check authentication and basic access
        models = list(genai.list_models())
        # Check if any model supports the necessary method (more robust check)
        if any('generateContent' in m.supported_generation_methods for m in models):
            logger.info(f"API key verification successful. Found {len(models)} models.")
            return {"status": "success", "message": "API key is valid and can generate content."}
        else:
            # Key might be valid but lack permissions or suitable models
            logger.warning("API key is valid but no models supporting 'generateContent' found.")
            raise HTTPException(status_code=400, detail="API key is valid, but no suitable generative models found for evaluation.")
    except Exception as e:
        # Catch broad exceptions which usually indicate invalid key or connection issues
        logger.error(f"API key verification failed: {str(e)}")
        # Provide a generic error to the user
        raise HTTPException(status_code=400, detail=f"Invalid API key or connection error. Please check the key and try again.")

@app.post("/evaluate/", tags=["Evaluation"])
async def evaluate_essay_endpoint(
    essay: UploadFile = File(...), # Use File for explicit upload handling
    api_key: str = Form(...),
    rubric_text: Optional[str] = Form(None),
    rubric_id: Optional[str] = Form(None),
    rubric_file: Optional[UploadFile] = File(None) # Use File for optional rubric upload
):
    """
    Evaluates one or more essays from an uploaded file using a specified or default rubric.
    Returns evaluation status and session ID for downloading reports.
    """
    logger.info(f"Received evaluation request for file: {essay.filename} (Type: {essay.content_type}, Size: {essay.size})")
    if rubric_file:
        logger.info(f"Rubric file provided: {rubric_file.filename} (Type: {rubric_file.content_type}, Size: {rubric_file.size})")

    # --- Input Validation ---
    if not essay.filename or essay.size == 0:
        logger.warning("Evaluation failed: Empty essay file uploaded.")
        raise HTTPException(status_code=400, detail="Cannot process an empty essay file.")
    # Check type based on content_type OR file extension for more flexibility
    is_allowed_type = essay.content_type in ALLOWED_TYPES
    is_allowed_extension = any(essay.filename.lower().endswith(ext) for ext in ['.pdf', '.txt', '.docx']) if essay.filename else False
    if not (is_allowed_type or is_allowed_extension):
        logger.warning(f"Evaluation failed: Invalid file type '{essay.content_type}' or extension for file '{essay.filename}'.")
        allowed_ext_str = ", ".join(['.pdf', '.txt', '.docx'])
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_TYPES)} or extensions: {allowed_ext_str}")

    # --- Determine Effective Rubric ---
    effective_rubric_text = ""
    rubric_source = "Default" # Track where the rubric came from

    # Priority 1: Rubric File
    if rubric_file:
        if not rubric_file.filename or rubric_file.size == 0:
            logger.warning("Uploaded rubric file is empty. Ignoring.")
        # Allow txt and pdf for rubric files
        elif not any(rubric_file.filename.lower().endswith(ext) for ext in ['.txt', '.pdf']):
             logger.warning(f"Invalid rubric file extension '{rubric_file.filename}'. Ignoring. Only .txt and .pdf allowed.")
        else:
            try:
                # Ensure correct content_type for extract_text based on extension
                filename_lower = rubric_file.filename.lower()
                if filename_lower.endswith('.txt'): rubric_file.content_type = 'text/plain'
                elif filename_lower.endswith('.pdf'): rubric_file.content_type = 'application/pdf'

                rubric_content_from_file = await extract_text(rubric_file)
                if rubric_content_from_file and rubric_content_from_file.strip():
                    effective_rubric_text = rubric_content_from_file
                    rubric_source = f"Uploaded File: {rubric_file.filename}"
                    logger.info(f"Using rubric from uploaded file: {rubric_file.filename}")
                else:
                    logger.warning(f"Extracted text from uploaded rubric file '{rubric_file.filename}' is empty. Ignoring.")
            except ValueError as e: # Catch extraction errors
                logger.warning(f"Error extracting text from uploaded rubric file '{rubric_file.filename}': {e}. Ignoring.")
            except Exception as e: # Catch unexpected errors
                logger.error(f"Unexpected error processing uploaded rubric file '{rubric_file.filename}': {e}. Ignoring.", exc_info=True)

    # Priority 2: Rubric Text (if file wasn't used/failed)
    if not effective_rubric_text and rubric_text and rubric_text.strip():
        effective_rubric_text = rubric_text
        rubric_source = "Direct Text"
        logger.info("Using rubric provided directly in the request (uploaded file not used or failed).")

    # Priority 3: Rubric ID (if file/text weren't used/failed)
    elif not effective_rubric_text and rubric_id:
        try:
            content, name = get_rubric_by_id(rubric_id) # Retrieve content and name
            effective_rubric_text = content
            rubric_source = f"Saved Rubric ID: {rubric_id}" + (f" (Name: {name})" if name else "")
            logger.info(f"Using saved rubric: {rubric_source} (uploaded file/direct text not used or failed).")
        except ValueError as e: # Rubric ID not found
            logger.warning(f"Could not find rubric with ID {rubric_id}. Falling back.")
            # Don't set default here yet, let the fallback handle it
        except IOError as e: # Error reading file
            logger.error(f"Error reading rubric {rubric_id}: {e}. Falling back.")
            # Don't set default here yet

    # Priority 4: Default Rubric (if none of the above worked)
    if not effective_rubric_text:
        effective_rubric_text = DEFAULT_RUBRIC
        rubric_source = "Default (No valid custom rubric provided/found)"
        logger.info("No valid custom rubric provided or found, using default rubric.")

    # --- Process Essay and Evaluate ---
    try:
        # Adjust content type based on extension if necessary before extraction
        # NOTE: Setting essay.content_type manually is generally not needed or possible,
        # as it's usually read-only and set by the framework based on upload headers/extension.
        # The extract_text function handles type detection internally.
        essay_filename_lower = essay.filename.lower() if essay.filename else ""
        if essay_filename_lower.endswith(".txt"): pass # essay.content_type = "text/plain" # Read-only attribute
        elif essay_filename_lower.endswith(".docx"): pass # essay.content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" # Read-only attribute
        elif essay_filename_lower.endswith(".pdf"): pass # essay.content_type = "application/pdf" # Read-only attribute

        essay_text_content = await extract_text(essay)
        if not essay_text_content.strip():
            logger.warning(f"Evaluation failed: Extracted text from '{essay.filename}' is empty.")
            raise HTTPException(status_code=400, detail=f"The uploaded file '{essay.filename}' contains no readable text.")

        logger.info(f"Passing rubric to evaluate_essays (source: {rubric_source}). Preview:\n{effective_rubric_text[:300]}...")
        evaluations = await evaluate_essays(essay_text_content, effective_rubric_text or None, api_key)

        if not evaluations:
            logger.warning("Evaluation process returned no results (potentially after splitting).")
            # This could happen if splitting resulted in only empty/short segments
            raise HTTPException(status_code=400, detail="Evaluation failed: No valid essay content found in the document after processing.")

        # --- Store Results and Prepare Response ---
        session_id = str(uuid.uuid4()) # Unique ID for this evaluation batch
        evaluation_storage[session_id] = {} # Initialize storage for this session

        if len(evaluations) == 1:
            # Handle single essay result
            logger.info(f"Single essay detected/processed. Storing result for session {session_id}.")
            evaluation = evaluations[0]

            # Calculate max score for summary (handle potential errors)
            try:
                 max_score = sum(float(c.get("max_score", 10)) for c in evaluation.get("criteria", []))
                 if max_score == 0: max_score = 50 # Fallback if criteria missing/malformed
            except:
                 max_score = 50 # Broad fallback

            student_name = evaluation.get("student_name", "Unknown")
            # Create a safe filename (replace non-alphanumeric characters)
            safe_name = re.sub(r'[^\w\-]+', '_', student_name)
            filename = f"{safe_name}_Evaluation_Report.pdf"

            # Store the evaluation data under the session ID and filename
            evaluation_storage[session_id][filename] = evaluation
            logger.info(f"Stored single evaluation '{filename}' under session ID: {session_id}")

            return {
                "evaluation_status": "single",
                "session_id": session_id,
                "filename": filename, # Filename for direct download
                "student_name": student_name,
                "overall_score": evaluation.get('overall_score', 0.0),
                "max_score": max_score,
                "error": evaluation.get("error", False) # Indicate if processing failed for this one
            }
        else:
            # Handle multiple essay results
            logger.info(f"Multiple ({len(evaluations)}) essays detected/processed. Storing results for session {session_id}.")
            multi_results_summary = []
            session_storage_entry = {} # Temporary dict to build session data

            for i, evaluation in enumerate(evaluations):
                student_name = evaluation.get("student_name", f"Essay_{i+1}")
                safe_name = re.sub(r'[^\w\-]+', '_', student_name)
                # Ensure unique filenames even if names are the same
                filename = f"{safe_name}_Evaluation_{i+1}.pdf"

                # Calculate max score for summary
                try:
                    max_score = sum(float(c.get("max_score", 10)) for c in evaluation.get("criteria", []))
                    if max_score == 0: max_score = 50
                except:
                    max_score = 50

                # Add evaluation to the session storage
                session_storage_entry[filename] = evaluation
                # Add summary info to the list returned to the client
                multi_results_summary.append({
                    "id": i, # Index for reference
                    "filename": filename,
                    "student_name": student_name,
                    "overall_score": evaluation.get("overall_score", 0.0),
                    "max_score": max_score,
                    "status": "Error" if evaluation.get("error") else "Completed"
                })

            evaluation_storage[session_id] = session_storage_entry # Store all results for the session
            logger.info(f"Returning summary for {len(evaluations)} essays. Session ID: {session_id}")
            return {
                "evaluation_status": "multiple",
                "session_id": session_id,
                "count": len(evaluations),
                "results": multi_results_summary # List of summaries for the frontend
            }

    # --- Error Handling ---
    except ValueError as e:
        # Catch specific ValueErrors from text extraction or evaluation logic
        logger.error(f"ValueError during evaluation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as he:
        # Re-raise HTTPExceptions directly (e.g., from input validation)
        raise he
    except Exception as e:
        # Catch unexpected server errors
        logger.error(f"Unexpected server error during evaluation: {str(e)}", exc_info=True)
        traceback.print_exc() # Print full traceback for debugging
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred: {str(e)}")

@app.get("/download-report/{session_id}/{filename}", tags=["Download"])
async def download_single_report(session_id: str, filename: str):
    """Downloads a single generated PDF report by session ID and filename."""
    logger.info(f"Request received to download report: Session='{session_id}', Filename='{filename}'")

    # Validate session and filename existence
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
        # Generate PDF on-demand
        pdf_report_generator = PDFReport()
        pdf_buffer = pdf_report_generator.create(evaluation)
        pdf_content = pdf_buffer.getvalue()

        if not pdf_content:
            # Handle case where PDF generation failed silently (returned empty buffer)
            logger.error(f"PDF generation resulted in an empty buffer for '{filename}' (Session: {session_id}).")
            raise HTTPException(status_code=500, detail="Failed to generate the PDF report for this essay (empty result).")

        logger.info(f"Successfully generated PDF for '{filename}'. Sending response.")
        # Return PDF as a downloadable file
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                # Suggest filename to browser, ensure it's accessible by CORS
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )
    except Exception as e:
        logger.error(f"Error generating single PDF report for download ('{filename}', Session: {session_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error occurred while generating the PDF report: {str(e)}")

@app.post("/generate-all-zip/", tags=["Download"])
async def generate_all_zip(data: dict = Body(...)):
    """Generates a ZIP archive containing all PDF reports for a given session ID."""
    session_id = data.get("session_id")
    if not session_id:
        logger.warning("ZIP generation request failed: Missing 'session_id' in request body.")
        raise HTTPException(status_code=400, detail="Missing 'session_id' in request body.")

    logger.info(f"Request received to generate ZIP archive for session: '{session_id}'")

    # Validate session existence
    if session_id not in evaluation_storage:
        logger.warning(f"ZIP generation failed: Session ID '{session_id}' not found.")
        raise HTTPException(status_code=404, detail="Evaluation session not found or expired.")

    session_data = evaluation_storage[session_id]
    if not session_data:
        logger.warning(f"ZIP generation failed: Session '{session_id}' contains no evaluation data.")
        raise HTTPException(status_code=404, detail="No evaluation reports found for this session to include in ZIP.")

    zip_buffer = BytesIO() # Create an in-memory buffer for the ZIP file
    pdf_report_generator = PDFReport() # Reuse the PDF generator
    generated_files_count = 0
    failed_files_count = 0

    try:
        # Create ZIP file in the buffer
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Iterate through stored evaluations for the session
            for filename, evaluation in session_data.items():
                logger.debug(f"Generating PDF for '{filename}' to include in ZIP (Session: {session_id})")
                try:
                    # Generate each PDF
                    pdf_buffer = pdf_report_generator.create(evaluation)
                    pdf_content = pdf_buffer.getvalue()
                    if pdf_content:
                        # Add the generated PDF content to the ZIP archive
                        zip_file.writestr(filename, pdf_content)
                        generated_files_count += 1
                        logger.debug(f"Added '{filename}' ({len(pdf_content)} bytes) to ZIP.")
                    else:
                        # Log if PDF generation failed for a specific file
                        logger.warning(f"Skipping '{filename}' in ZIP: PDF generation resulted in empty content.")
                        failed_files_count += 1
                except Exception as e:
                    # Log errors during individual PDF generation within the loop
                    logger.error(f"Error generating PDF for '{filename}' during ZIP creation: {e}", exc_info=True)
                    failed_files_count += 1

        # After processing all files, check if any PDFs were successfully added
        if generated_files_count == 0:
            logger.error(f"ZIP generation failed: Could not generate any valid PDF reports for session '{session_id}'.")
            raise HTTPException(status_code=500, detail="Failed to generate any valid PDF reports for the ZIP archive.")

        zip_buffer.seek(0) # Rewind the buffer to the beginning
        zip_content = zip_buffer.getvalue()
        logger.info(f"ZIP archive generated for session '{session_id}'. Contains {generated_files_count} reports ({failed_files_count} failed). Size: {len(zip_content)} bytes.")

        # Return the ZIP file as a response
        return Response(
            content=zip_content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=Evaluation_Reports_{session_id[:8]}.zip",
                # Add custom headers for client-side info (optional)
                "X-Files-Generated": str(generated_files_count),
                "X-Files-Failed": str(failed_files_count),
                "Access-Control-Expose-Headers": "Content-Disposition, X-Files-Generated, X-Files-Failed"
            }
        )
    except Exception as e:
        # Catch errors during ZIP creation process itself
        logger.error(f"Critical error during ZIP archive generation for session '{session_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error occurred while generating the ZIP archive: {str(e)}")

# --- Rubric Management Endpoints ---

@app.get("/rubrics/", tags=["Rubrics"])
async def list_rubrics():
    """Lists all saved rubrics."""
    logger.info("Request received to list saved rubrics.")
    try:
        rubrics = get_saved_rubrics()
        return {"rubrics": rubrics}
    except Exception as e:
        logger.error(f"Error retrieving saved rubrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error retrieving rubrics: {str(e)}")

@app.get("/rubrics/{rubric_id}", tags=["Rubrics"])
async def get_rubric(rubric_id: str):
    """Retrieves the content and name of a specific rubric by ID."""
    logger.info(f"Request received to get rubric with ID: {rubric_id}")
    try:
        content, name = get_rubric_by_id(rubric_id)
        return {"id": rubric_id, "name": name, "content": content}
    except ValueError as e: # Rubric not found or invalid ID format
        logger.warning(f"Rubric retrieval failed: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except IOError as e: # File reading error
        logger.error(f"Error reading rubric {rubric_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting rubric {rubric_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {str(e)}")

@app.post("/rubrics/", tags=["Rubrics"], status_code=201)
async def create_rubric(content: str = Form(...), name: Optional[str] = Form(None)):
    """Creates and saves a new rubric."""
    logger.info(f"Request received to create new rubric. Name: '{name if name else 'None'}'")
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="Rubric content cannot be empty.")
    if name and len(name) > 100: # Limit name length
        raise HTTPException(status_code=400, detail="Rubric name cannot exceed 100 characters.")

    try:
        # Save the rubric, potentially prepending the name
        rubric_id = save_rubric(content, name)
        # Retrieve the saved rubric to confirm and get final name/content
        saved_content, saved_name = get_rubric_by_id(rubric_id)
        return {"id": rubric_id, "name": saved_name or name, "message": "Rubric saved successfully"}
    except IOError as e: # Catch file saving errors
        raise HTTPException(status_code=500, detail=f"Failed to save rubric: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating rubric: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error creating rubric: {str(e)}")

@app.put("/rubrics/{rubric_id}", tags=["Rubrics"])
async def update_rubric(rubric_id: str, content: str = Form(...), name: Optional[str] = Form(None)):
    """Updates an existing rubric by ID."""
    logger.info(f"Request received to update rubric ID: {rubric_id}. New Name: '{name if name else 'None'}'")
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="Rubric content cannot be empty.")
    if name and len(name) > 100:
        raise HTTPException(status_code=400, detail="Rubric name cannot exceed 100 characters.")

    try:
        # Check if rubric exists first (get_rubric_by_id raises ValueError if not found)
        get_rubric_by_id(rubric_id)
        # Save the updated content/name using the existing ID
        save_rubric(content, name, rubric_id)
        # Retrieve again to return the updated state
        updated_content, updated_name = get_rubric_by_id(rubric_id)
        return {"id": rubric_id, "name": updated_name or name, "message": "Rubric updated successfully"}
    except ValueError: # Rubric not found
        logger.warning(f"Update failed: Rubric not found: {rubric_id}")
        raise HTTPException(status_code=404, detail=f"Rubric with ID {rubric_id} not found")
    except IOError as e: # File saving error
        raise HTTPException(status_code=500, detail=f"Failed to update rubric: {str(e)}")
    except Exception as e:
        logger.error(f"Error updating rubric {rubric_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error updating rubric: {str(e)}")

@app.delete("/rubrics/{rubric_id}", tags=["Rubrics"], status_code=204)
async def remove_rubric(rubric_id: str):
    """Deletes a rubric by ID."""
    logger.info(f"Request received to delete rubric ID: {rubric_id}")
    deleted = delete_rubric(rubric_id)
    if deleted:
        # Return No Content on success
        return Response(status_code=204)
    else:
        # Check if the file actually existed to distinguish 404 from 500
        filepath = os.path.join(get_rubric_dir(), f"{rubric_id}.txt") # Assumes sanitize happens in delete_rubric
        if not os.path.exists(filepath) and re.match(r'^[\w-]+$', rubric_id): # Check existence only if ID format was valid
             logger.warning(f"Deletion failed: Rubric not found: {rubric_id}")
             raise HTTPException(status_code=404, detail=f"Rubric with ID {rubric_id} not found")
        else:
             # If file exists but deletion failed, or ID was invalid
             logger.error(f"Deletion failed for rubric {rubric_id}. Check permissions or ID format.")
             raise HTTPException(status_code=500, detail="Failed to delete rubric due to a server error or invalid ID.")

@app.get("/default-rubric/", tags=["Rubrics"])
async def get_default_rubric():
    """Returns the hardcoded default rubric."""
    logger.info("Request received for default rubric.")
    return {"name": "Default Standard Rubric", "content": DEFAULT_RUBRIC}

@app.post("/generate-rubric/", tags=["Rubrics"])
async def generate_rubric(
    subject: str = Form(...),
    level: str = Form(...),
    criteria_count: int = Form(5),
    api_key: str = Form(...) # Requires API key for generation
):
    """Generates a new rubric using the AI based on provided parameters."""
    logger.info(f"Request received to generate rubric: Subject='{subject}', Level='{level}', Criteria={criteria_count}")

    # Validation
    if not api_key: raise HTTPException(status_code=400, detail="API key is required for rubric generation.")
    if not subject or not level: raise HTTPException(status_code=400, detail="Subject and level are required.")
    # Clamp criteria count to a reasonable range
    if not (3 <= criteria_count <= 10):
        logger.warning(f"Invalid criteria count ({criteria_count}) requested. Clamping to range [3, 10].")
        criteria_count = max(3, min(criteria_count, 10))

    try:
        genai.configure(api_key=api_key)
        # Use a capable model for generation
        model_name = 'gemini-1.5-flash' # Or another suitable model
        model = genai.GenerativeModel(model_name)
        logger.info(f"Using model {model.model_name} for rubric generation.")

        # Construct a detailed prompt for the AI
        prompt = f"""
    Generate an academic essay evaluation rubric tailored for the following specifications:
    - Subject: {subject}
    - Educational Level: {level} (e.g., High School, Undergraduate, Graduate)
    - Number of Criteria: {criteria_count}
    - Scoring Scale per Criterion: 0-10 points

    Instructions for the rubric structure:
    1. Start with a clear title line, incorporating the subject and level. Example: "{subject} Essay Rubric ({level})"
    2. List exactly {criteria_count} numbered criteria relevant to essay writing in the specified subject and level.
    3. For each criterion:
       - State the criterion name clearly (e.g., "Thesis Statement & Argument", "Evidence & Analysis", "Organization & Structure", "Style & Mechanics").
       - Indicate the scoring scale: (0-10).
       - Provide 3-4 concise bullet points describing the key elements assessed under that criterion, appropriate for the specified educational level. Use clear and actionable language.
    4. Ensure the overall tone is constructive and academic.
    5. Do not add any introductory paragraphs, concluding summaries, or explanations outside the rubric structure itself. Output only the rubric title and the numbered criteria list.

    Example Format Snippet (Content should be specific to the request):
    [Generated Title Line]

    1. Criterion Name One (0-10):
       - Bullet point descriptor 1 (clear, concise).
       - Bullet point descriptor 2.
       - Bullet point descriptor 3.

    2. Criterion Name Two (0-10):
       - Bullet point descriptor 1.
       - Bullet point descriptor 2.
       - Bullet point descriptor 3.
       - Bullet point descriptor 4.

    [... continue for all {criteria_count} criteria ...]
    """
        # Make the API call
        response = await model.generate_content_async(prompt)
        generated_text = response.text.strip()
        logger.info(f"AI generated rubric content (first 200 chars): {generated_text[:200]}...")

        # Basic validation of the output
        num_numbered_lines = len(re.findall(r"^\s*\d+\.", generated_text, re.MULTILINE))
        if abs(num_numbered_lines - criteria_count) > 1: # Allow slight deviation
            logger.warning(f"Generated rubric might not have the expected number of criteria ({num_numbered_lines} found vs {criteria_count} requested).")

        # Extract potential name from first line
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
async def upload_rubric_file(file: UploadFile = File(...)):
    """Uploads a rubric file (.txt or .pdf) and extracts its text content."""
    logger.info(f"Request received to upload rubric file: {file.filename} (Type: {file.content_type}, Size: {file.size})")

    # Validation
    if not file.filename or file.size == 0:
        raise HTTPException(status_code=400, detail="Cannot process an empty file.")

    filename_lower = file.filename.lower()
    # Allow only .txt and .pdf extensions
    if not (filename_lower.endswith('.txt') or filename_lower.endswith('.pdf')):
        logger.warning(f"Rubric upload failed: Invalid file extension for '{file.filename}'. Only .txt and .pdf allowed.")
        raise HTTPException(status_code=400, detail="Invalid file type. Only .txt and .pdf files are supported for rubric upload.")

    try:
        # Adjust content_type for extract_text if needed
        if filename_lower.endswith('.txt'): file.content_type = 'text/plain'
        elif filename_lower.endswith('.pdf'): file.content_type = 'application/pdf'

        # Extract text using the common function
        extracted_text = await extract_text(file)
        if not extracted_text.strip():
            logger.warning(f"Rubric upload: Extracted text from '{file.filename}' is empty.")
            raise HTTPException(status_code=400, detail=f"The uploaded file '{file.filename}' contains no readable text.")

        logger.info(f"Successfully extracted text from uploaded rubric file: {file.filename}")
        # Return the extracted text and original filename
        return {"text": extracted_text, "filename": file.filename}

    except ValueError as e: # Catch errors from extract_text
        logger.error(f"Error extracting text from uploaded rubric file '{file.filename}': {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as he: # Re-raise validation errors
        raise he
    except Exception as e: # Catch unexpected errors
        logger.error(f"Unexpected server error during rubric file upload '{file.filename}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error processing rubric file: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "AI Essay Grader Backend is running"}

# --- Main execution ---
if __name__ == "__main__":
    import uvicorn
    # Get host/port/reload settings from environment variables or use defaults
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1") # Default to localhost
    reload_flag = os.environ.get("RELOAD", "false").lower() == "true" # Enable reload via env var

    logger.info(f"Starting Uvicorn server on {host}:{port} | Reload: {reload_flag}")
    # Run the FastAPI app using uvicorn
    # Note: "main:app" refers to the 'app' instance in the 'main.py' file
    uvicorn.run("main:app", host=host, port=port, reload=reload_flag)
