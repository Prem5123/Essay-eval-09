import asyncio
import json
import logging
import os
import random
import re
import traceback
import uuid
import zipfile
from io import BytesIO
from typing import List, Optional, Dict # Added Dict

import google.generativeai as genai
import pdfplumber
from dotenv import load_dotenv
from docx import Document
from fastapi import (Body, FastAPI, File, Form, HTTPException, Response,
                     UploadFile)
from fastapi.middleware.cors import CORSMiddleware
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate,
                              Paragraph, Spacer, Table, TableStyle)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Corrected: Use __name__

# Load environment variables
load_dotenv()

# Create uploads and rubrics directories if they don't exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("rubrics", exist_ok=True)

# Initialize FastAPI app
app = FastAPI()

# Get allowed origins from environment or use defaults
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,https://essay-evaluator-mu.vercel.app")
origins = [origin.strip() for origin in allowed_origins.split(",") if origin.strip()]

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"], # Use ["*"] if no origins specified or handle as needed
    allow_credentials=True,
    allow_methods=["*"],  # Corrected: Allow specific methods or "*" for all standard methods
    allow_headers=["*"]   # Corrected: Allow specific headers or "*" for all standard headers
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
   - Consideration of counterarguments (if applicable)
4. Writing Style & Clarity (0-10):
   - Clear, concise prose
   - Appropriate academic tone
   - Varied sentence structure
5. Grammar & Mechanics (0-10):
   - Correct grammar, spelling, and punctuation
   - Proper citation format (if applicable)
   - Appropriate word choice
"""

# In-memory storage for multi-essay PDF generation
evaluation_storage: Dict[str, Dict[str, dict]] = {}


# --- Essay Processing Functions ---

async def extract_text(file: UploadFile) -> str:
    """Extract text from uploaded files (PDF, TXT, DOCX)."""
    logger.info(f"Extracting text from file: '{file.filename}' (Type: {file.content_type})")
    content = await file.read()
    if not content:
        logger.warning(f"File '{file.filename}' is empty.")
        # Consider returning empty string or raising a specific error type if needed
        # For now, raising ValueError as before.
        raise ValueError(f"Cannot read an empty file: '{file.filename}'.")

    filename = file.filename.lower() if file.filename else ""
    content_type = file.content_type

    try:
        if content_type == 'text/plain' or filename.endswith('.txt'):
            try:
                return content.decode('utf-8')
            except UnicodeDecodeError:
                logger.warning(f"UTF-8 decoding failed for '{file.filename}', trying latin-1.")
                return content.decode('latin-1') # Fallback encoding
        elif content_type == 'application/pdf' or filename.endswith('.pdf'):
            with pdfplumber.open(BytesIO(content)) as pdf:
                # Ensure page.extract_text() doesn't return None
                text = '\n'.join([(page.extract_text() or '') for page in pdf.pages])
            if not text.strip():
                 logger.warning(f"Extracted empty text from PDF: '{file.filename}'. May be image-based.")
            return text
        elif content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or filename.endswith('.docx'):
            with BytesIO(content) as doc_file:
                try:
                    doc = Document(doc_file)
                    text = '\n'.join([para.text for para in doc.paragraphs])
                    return text
                except Exception as docx_err: # Catch potential docx specific errors
                    logger.error(f"Error parsing DOCX file '{file.filename}': {docx_err}")
                    raise ValueError(f"Failed to parse DOCX file '{file.filename}'.")
        else:
            # Log the unsupported type before raising error
            logger.warning(f"Unsupported file format received: {content_type} for file '{filename}'")
            raise ValueError(f"Unsupported file format: {content_type}")
    except Exception as e:
        # Log the full traceback for better debugging
        logger.error(f"Error extracting text from '{file.filename}': {str(e)}\n{traceback.format_exc()}")
        # Re-raise a more specific error or keep ValueError
        raise ValueError(f"Failed to extract text from '{file.filename}'. Ensure the file is not corrupted or password-protected.")


def split_essays(text: str) -> List[str]:
    """Split text into multiple essays based on student name patterns or paragraph breaks."""
    logger.info("Attempting to split text into multiple essays.")
    
    # Enhanced patterns to handle variations in spacing and optional titles
    patterns = [
        r"^\s*(?:student\s+)?name\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$", # More flexible name matching
        r"^\s*student\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
        # Add more patterns if specific headers are common (e.g., Course:, ID:)
    ]
    
    all_matches = []
    for pattern in patterns:
        # Use re.IGNORECASE for case-insensitivity
        matches = list(re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE))
        all_matches.extend([(m.start(), m.group(1).strip()) for m in matches]) # Store start index and name

    # Sort matches by their starting position
    all_matches.sort(key=lambda x: x[0])

    essays = []
    last_pos = 0

    if not all_matches:
        logger.info("No name patterns found. Trying to split by significant whitespace.")
        # Split by 4 or more newlines, potentially indicating essay breaks
        chunks = re.split(r'\n{4,}', text.strip())
        # Filter out very short chunks that are unlikely to be essays
        potential_essays = [chunk.strip() for chunk in chunks if len(chunk.strip()) > 300] # Increased threshold
        if len(potential_essays) > 1:
            logger.info(f"Split into {len(potential_essays)} potential essays based on whitespace.")
            return potential_essays
        else:
            logger.info("Could not split by whitespace or only one chunk found. Treating as a single essay.")
            return [text.strip()] # Return the original text as one essay

    # If name patterns were found, split based on them
    logger.info(f"Found {len(all_matches)} potential essay start points based on name patterns.")
    for i, (start_pos, name) in enumerate(all_matches):
        # Extract the segment before the current match
        segment = text[last_pos:start_pos].strip()
        if segment and len(segment) > 100: # Avoid adding empty or very short segments
             # If it's the first segment and long enough, or any subsequent segment
             if i == 0 and len(segment) > 300: # Heuristic: first part might be instructions
                 essays.append(segment)
             elif i > 0:
                 # Associate the previous segment with the previous name if possible
                 # This logic needs refinement - currently assumes segment before match belongs to previous student
                 essays.append(segment) # This might need adjustment based on actual file structure

        # Determine the end position for the current essay
        if i == len(all_matches) - 1:
            # Last match, take text until the end
            essay_content = text[start_pos:].strip()
        else:
            # Take text from current match start to next match start
            next_start_pos = all_matches[i + 1][0]
            essay_content = text[start_pos:next_start_pos].strip()

        if len(essay_content) > 200: # Ensure the essay content itself is substantial
            essays.append(essay_content)
            
        last_pos = start_pos # This might need to be the *end* of the current essay segment

    # Refined filtering: ensure essays aren't just headers
    final_essays = [essay for essay in essays if len(re.sub(r'\s+', '', essay)) > 250] # Count non-whitespace chars

    if not final_essays: # Fallback if filtering removed everything
         logger.warning("Splitting by name removed all content, returning original text as single essay.")
         return [text.strip()]
         
    logger.info(f"Final count after splitting and filtering: {len(final_essays)} essays.")
    return final_essays


async def evaluate_essays(
    essay_text: str,
    rubric_text: Optional[str],
    api_key: str,
    include_criteria: bool,
    include_suggestions: bool,
    include_highlights: bool,
    include_mini_lessons: bool
) -> List[dict]:
    """Evaluate multiple essays if detected, handling potential errors for each."""
    essays = split_essays(essay_text)
    logger.info(f"Attempting to evaluate {len(essays)} detected essay(s).")

    if not essays:
        logger.warning("Splitting resulted in zero essays.")
        return []
        
    if len(essays) == 1 and not essays[0].strip():
        logger.warning("Input contains only whitespace after potential splitting.")
        return []

    results = []
    # Implement rate limiting / delays between API calls
    base_delay = 1.5  # Base delay in seconds
    max_delay_increment = 1.0 # Random additional delay up to this value

    tasks = []
    for i, essay_content in enumerate(essays):
        if not essay_content or not essay_content.strip():
            logger.warning(f"Skipping empty essay chunk at index {i}.")
            continue
        
        # Create a coroutine for each evaluation
        task = evaluate_single_essay_with_error_handling(
            essay_content=essay_content,
            rubric_text=rubric_text,
            api_key=api_key,
            include_criteria=include_criteria,
            include_suggestions=include_suggestions,
            include_highlights=include_highlights,
            include_mini_lessons=include_mini_lessons,
            essay_index=i,
            delay=(base_delay + random.uniform(0, max_delay_increment)) if i > 0 else 0 # Delay only after the first
        )
        tasks.append(task)

    # Run evaluations concurrently (or sequentially with delays handled internally)
    evaluation_results = await asyncio.gather(*tasks)
    
    # Filter out None results if any error occurred where None was returned by handler
    results = [res for res in evaluation_results if res is not None]

    logger.info(f"Finished evaluating {len(results)} essays out of {len(essays)} detected.")
    return results

async def evaluate_single_essay_with_error_handling(
    essay_content: str,
    rubric_text: Optional[str],
    api_key: str,
    include_criteria: bool,
    include_suggestions: bool,
    include_highlights: bool,
    include_mini_lessons: bool,
    essay_index: int,
    delay: float
) -> Optional[dict]:
    """Helper to evaluate one essay and capture errors, includes delay."""
    if delay > 0:
        await asyncio.sleep(delay)
        
    try:
        logger.info(f"Starting evaluation for essay index {essay_index}...")
        evaluation = await evaluate_essay(essay_content, rubric_text, api_key)
        
        # Store the configuration used for this evaluation for PDF generation
        evaluation["config"] = {
            "include_criteria": include_criteria,
            "include_suggestions": include_suggestions,
            "include_highlights": include_highlights,
            "include_mini_lessons": include_mini_lessons
        }
        logger.info(f"Successfully evaluated essay index {essay_index}.")
        return evaluation
        
    except Exception as e:
        logger.error(f"Error processing essay index {essay_index}: {str(e)}\n{traceback.format_exc()}")
        # Try to find student name even in case of failure
        student_name = "Unknown"
        try:
             # Limit search to first few lines for performance/relevance
            first_lines = "\n".join(essay_content.split('\n')[:10])
            name_patterns = [
                r"^\s*(?:student\s+)?name\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
                r"^\s*student\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$"
            ]
            for pattern in name_patterns:
                 name_match = re.search(pattern, first_lines, re.IGNORECASE | re.MULTILINE)
                 if name_match:
                      student_name = name_match.group(1).strip()
                      break
        except Exception as name_ex:
            logger.error(f"Could not extract student name during error handling: {name_ex}")
            
        # Return a structured error response
        return {
            "student_name": student_name if student_name != "Unknown" else f"Failed_Essay_{essay_index+1}",
            "overall_score": 0,
            "criteria": [{"name": "Processing Error", "score": 0, "max_score": 0, "feedback": f"Evaluation failed: {str(e)}"}],
            "suggestions": ["The AI evaluation could not be completed due to an error."],
            "highlighted_passages": [],
            "Mini Lessons": [], # Keep structure consistent
            "error": True, # Flag indicating failure
            "config": { # Still include config
                "include_criteria": include_criteria,
                "include_suggestions": include_suggestions,
                "include_highlights": include_highlights,
                "include_mini_lessons": include_mini_lessons
            }
        }

async def evaluate_essay(essay_text: str, rubric_text: Optional[str], api_key: str) -> dict:
    """Evaluate a single essay using the Gemini API."""
    if not api_key:
        logger.error("Gemini API key is missing.")
        raise ValueError("API key not configured.")

    genai.configure(api_key=api_key)
    # Consider making the model configurable (e.g., via env var)
    # Use a newer recommended model if available and suitable, like 'gemini-1.5-flash'
    model = genai.GenerativeModel('gemini-1.5-flash-latest') # Using 1.5 Flash

    rubric = rubric_text if rubric_text and rubric_text.strip() else DEFAULT_RUBRIC

    # Robust Rubric Parsing (handle variations)
    criteria_matches = re.findall(
        r"^\s*(?:\d+\.?\s*)?([A-Za-z &/'\-]+?)\s*\(\s*(\d+)\s*-?\s*(\d+)\s*\)\s*:",
        rubric,
        re.MULTILINE | re.IGNORECASE
    )
    if not criteria_matches:
         # Fallback if primary pattern fails - maybe just look for (0-10) etc.
         criteria_matches = re.findall(r"^\s*(.*?)\s*\(\s*(\d+)\s*-?\s*(\d+)\s*\)\s*:", rubric, re.MULTILINE)

    if criteria_matches:
        # Expecting (name, min_score, max_score)
        criteria_details = [(match[0].strip(), int(match[2])) for match in criteria_matches]
        criteria_names = [name for name, _ in criteria_details]
        criteria_max_scores = [max_score for _, max_score in criteria_details]
    else:
        logger.warning("Could not parse criteria from rubric. Using default structure.")
        # Fallback to a default structure if parsing fails
        criteria_names = [f"Criterion {i+1}" for i in range(5)]
        criteria_max_scores = [10] * 5

    max_score_total = sum(criteria_max_scores)

    # --- Student Name Extraction (Improved) ---
    student_name = "Unknown Student"
     # Search in the first ~15 lines for common patterns
    first_lines = "\n".join(essay_text.split('\n')[:15])
    name_patterns = [
        r"^\s*(?:student\s+)?name\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$", # Flexible name
        r"^\s*student\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
        # Add other common patterns if needed, e.g., Author:
        r"^\s*author\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
    ]
    for pattern in name_patterns:
        name_match = re.search(pattern, first_lines, re.IGNORECASE | re.MULTILINE)
        if name_match:
            potential_name = name_match.group(1).strip()
            # Basic check to avoid grabbing placeholder text
            if potential_name.lower() not in ["student name", "name", "enter name here"]:
                 student_name = potential_name
                 logger.info(f"Extracted student name: {student_name}")
                 break # Stop after first successful match
    if student_name == "Unknown Student":
        logger.warning("Could not automatically extract student name from essay header.")


    # --- Construct the Prompt ---
    # Dynamically create the criteria JSON structure string based on parsed rubric
    criteria_json_string = ",\n".join([
        f'  {{"name": "{name}", "score": number (0-{max_score}), "max_score": {max_score}, "feedback": "Specific feedback for {name}."}}'
        for name, max_score in zip(criteria_names, criteria_max_scores)
    ]) if criteria_names else ""

    prompt = f"""
Analyze the following student essay based *strictly* on the provided rubric criteria. Ignore the url that is being included in the essay

**RUBRIC:**
{rubric}


**ESSAY TEXT:**
{essay_text}

---
**EVALUATION TASK:**
Provide a detailed evaluation in JSON format. Follow the structure below precisely.

**JSON OUTPUT STRUCTURE:**
{{
  "student_name": "{student_name}", // Use the extracted name or "Unknown Student"
  "overall_score": number, // Calculated sum of scores from criteria below
  "criteria": [
    // Populate this array based on the RUBRIC provided above.
    // Example for one criterion (repeat for all):
    {criteria_json_string}
    // Ensure score is within the max_score for each criterion.
    // Feedback must be specific to the essay content for that criterion.
  ],
  "suggestions": [
    "Provide 2-3 specific, actionable suggestions for overall improvement based on the evaluation.",
    "Focus on the most impactful areas for the student.",
    "Suggestion 3 (optional)"
  ],
  "highlighted_passages": [
    // Identify 4-5 specific sentences or short passages from the essay illustrating key issues.
    // If no major issues, highlight strengths.
    {{
      "text": "Exact short text snippet from the essay...",
      "issue": "Brief description of the issue (e.g., 'Awkward phrasing', 'Needs evidence', 'Strong point')",
      "suggestion": "How to improve this specific text.",
      "example_revision": "Optional: Show a revised version of the text."
    }},
    // Add 2 or 3 more highlights following the same structure.
  ],
  "Mini Lessons": [
      // Add "Mini Lessons" based on the evaluation.
      // These are specific actionable tips or concepts to improve the student's writing.
      // Each lesson should contain detailed explaination (more than 50 words) and relevant to the essay.
      //quote teext if necessary
      // Use clear, simple language and avoid jargon.
      // Explain with a metaphoer or analogy to make it relatable.

      
  ]
}}

**IMPORTANT INSTRUCTIONS:**
- Adhere strictly to the JSON format. Do not include markdown formatting (```json ... ```) around the JSON block.
- Ensure all numeric scores are valid numbers.
- Calculate `overall_score` by summing the scores given in the `criteria` array.
- Extract the student name accurately if possible, otherwise use "{student_name}".
- Provide constructive and specific feedback relevant to the essay content.
- Ensure the "Mini Lessons" array contains only the extracted mini-lesson strings.
- If the essay text is extremely short or nonsensical, reflect this in the feedback and assign low scores appropriately.
"""

    max_retries = 3
    last_error = None

    # Configure safety settings to be less restrictive if needed, balancing safety and usability
    safety_settings = {
        genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
        genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
        genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
        genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
        # Adjust thresholds as necessary: BLOCK_ONLY_HIGH, BLOCK_MEDIUM_AND_ABOVE, BLOCK_LOW_AND_ABOVE, BLOCK_NONE
    }

    generation_config = genai.types.GenerationConfig(
         # response_mime_type="application/json", # Request JSON directly if model supports
         temperature=0 # Adjust temperature for creativity vs consistency
    
    )


    for attempt in range(max_retries):
        try:
            logger.info(f"Sending request to Gemini API (Attempt {attempt + 1}/{max_retries})...")
            response = await model.generate_content_async(
                 prompt,
                 generation_config=generation_config,
                 safety_settings=safety_settings
            )

            # Enhanced response cleaning and parsing
            if not response.candidates:
                 # Handle cases where the response might be blocked or empty
                 block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else 'Unknown'
                 logger.error(f"Gemini API call failed: No candidates returned. Block Reason: {block_reason}")
                 # You might want to check response.prompt_feedback for safety issues
                 raise ValueError(f"API response blocked or empty. Reason: {block_reason}")

            response_text = response.text
            # Clean potential markdown code fences
            cleaned_response = re.sub(r'^```json\s*|\s*```$', '', response_text.strip(), flags=re.MULTILINE | re.DOTALL).strip()
            
            # Attempt to parse the JSON
            result = json.loads(cleaned_response)
            logger.info("Successfully parsed Gemini API response.")

            # --- Post-processing and Validation ---
            # Ensure critical keys exist, provide defaults if missing but log warnings
            result.setdefault("student_name", student_name) # Keep extracted name if API didn't provide one
            result.setdefault("overall_score", 0)
            result.setdefault("criteria", [])
            result.setdefault("suggestions", [])
            result.setdefault("highlighted_passages", [])
            result.setdefault("Mini Lessons", []) # Ensure key exists

            # Validate/recalculate overall score (important)
            calculated_score = sum(float(c.get("score", 0)) for c in result["criteria"])
            if "overall_score" not in result or not isinstance(result["overall_score"], (int, float)):
                 logger.warning("API response missing or invalid 'overall_score'. Recalculating.")
                 result["overall_score"] = calculated_score
            elif abs(float(result["overall_score"]) - calculated_score) > 0.1: # Allow for small float differences
                 logger.warning(f"API 'overall_score' ({result['overall_score']}) differs from calculated sum ({calculated_score}). Using calculated sum.")
                 result["overall_score"] = calculated_score
            else:
                # Ensure score is a float for consistency
                 result["overall_score"] = float(result["overall_score"])


            # Validate criteria structure and scores
            validated_criteria = []
            for i, crit in enumerate(result.get("criteria", [])):
                if not isinstance(crit, dict):
                    logger.warning(f"Criterion at index {i} is not a dictionary. Skipping.")
                    continue
                
                default_max = criteria_max_scores[i] if i < len(criteria_max_scores) else 10 # Fallback max score
                max_s = float(crit.get("max_score", default_max))
                score = min(max(float(crit.get("score", 0)), 0.0), max_s) # Clamp score between 0 and max_score
                
                validated_criteria.append({
                    "name": crit.get("name", criteria_names[i] if i < len(criteria_names) else f"Criterion {i+1}"),
                    "score": score,
                    "max_score": max_s,
                    "feedback": crit.get("feedback", "No feedback provided.")
                })
            result["criteria"] = validated_criteria

            # Basic validation for other fields (ensure they are lists)
            if not isinstance(result.get("suggestions"), list): result["suggestions"] = []
            if not isinstance(result.get("highlighted_passages"), list): result["highlighted_passages"] = []
            if not isinstance(result.get("Mini Lessons"), list): result["Mini Lessons"] = []
            
            logger.info(f"Evaluation results processed for student: {result['student_name']}")
            return result # Success

        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to parse JSON response on attempt {attempt + 1}: {json_err}")
            logger.debug(f"Raw response causing JSON error:\n---\n{cleaned_response[:1000]}...\n---")
            last_error = json_err
        except ValueError as ve: # Catch ValueErrors raised earlier (e.g., API blocked)
             logger.error(f"ValueError during API call or processing on attempt {attempt+1}: {ve}")
             last_error = ve
        except Exception as e:
            logger.error(f"Unexpected error during API call/parsing on attempt {attempt + 1}: {str(e)}\n{traceback.format_exc()}")
            last_error = e

        # Exponential backoff before retrying
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt + random.uniform(0, 1)
            logger.info(f"Retrying in {wait_time:.2f} seconds...")
            await asyncio.sleep(wait_time)

    # If all retries fail
    logger.error(f"Failed to evaluate essay after {max_retries} attempts.")
    raise ValueError(f"Failed to get valid evaluation after {max_retries} attempts. Last error: {str(last_error)}")


# --- PDF Report Generation Class ---

class PDFReport:
    # Define Colors (consider making these configurable)
    HEADER_COLOR = colors.HexColor('#4c1d95')  # Indigo
    ACCENT_COLOR = colors.HexColor('#7c3aed')  # Violet
    LIGHT_BG = colors.HexColor('#f0e7ff')     # Light purple
    SUCCESS_COLOR = colors.HexColor('#059669') # Emerald
    WARNING_COLOR = colors.HexColor('#d97706') # Amber
    DANGER_COLOR = colors.HexColor('#dc2626')  # Red
    TEAL_COLOR = colors.HexColor('#0d9488')    # Teal
    HIGHLIGHT_COLOR = colors.HexColor('#fef08a') # Yellow
    TEXT_COLOR = colors.HexColor('#1e293b')    # Slate

    # Define Fonts
    FONT_NAME = 'Helvetica'
    BOLD_FONT = 'Helvetica-Bold'

    def __init__(self):
        """Initialize styles for the PDF report."""
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        """Create custom paragraph and table styles."""
        # Base style
        self.styles.add(ParagraphStyle(
            name='Base',
            parent=self.styles['Normal'],
            fontName=self.FONT_NAME,
            fontSize=10,
            textColor=self.TEXT_COLOR,
            leading=14
        ))
        # Updated MainTitle with larger size and vibrant color
        self.styles.add(ParagraphStyle(
            name='MainTitle',
            parent=self.styles['h1'],
            fontName=self.BOLD_FONT,
            fontSize=24,
            spaceAfter=12,
            alignment=TA_CENTER,
            textColor=self.ACCENT_COLOR
        ))
        self.styles.add(ParagraphStyle(
            name='StudentTitle',
            parent=self.styles['h2'],
            fontName=self.FONT_NAME,
            fontSize=14,
            spaceAfter=6,
            alignment=TA_CENTER,
            textColor=self.HEADER_COLOR
        ))
        self.styles.add(ParagraphStyle(
            name='ScoreTitle',
            parent=self.styles['h3'],
            fontName=self.BOLD_FONT,
            fontSize=12,
            spaceAfter=18,
            alignment=TA_CENTER,
            textColor=self.TEXT_COLOR
        ))
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=self.styles['h3'],
            fontName=self.BOLD_FONT,
            fontSize=14,
            spaceBefore=12,
            spaceAfter=8,
            textColor=self.HEADER_COLOR
        ))
        # Table Styles
        self.styles.add(ParagraphStyle(name='TableHeader', fontName=self.BOLD_FONT, alignment=TA_CENTER, textColor=colors.white))
        self.styles.add(ParagraphStyle(name='TableCell', parent=self.styles['Base'], alignment=TA_LEFT, leading=12))
        self.styles.add(ParagraphStyle(name='TableCellBold', parent=self.styles['TableCell'], fontName=self.BOLD_FONT))
        self.styles.add(ParagraphStyle(name='TableCellCenter', parent=self.styles['TableCell'], alignment=TA_CENTER))
        self.styles.add(ParagraphStyle(name='FeedbackCell', parent=self.styles['TableCell'], fontSize=9))
        # Updated SuggestionItem with colored bullet
        self.styles.add(ParagraphStyle(
            name='SuggestionItem',
            parent=self.styles['Base'],
            leftIndent=18,
            bulletIndent=0,
            spaceBefore=3,
            bulletFontName=self.BOLD_FONT,
            bulletFontSize=10,
            bulletColor=self.ACCENT_COLOR
        ))
        # New MiniLessonItem style with teal bullet
        self.styles.add(ParagraphStyle(
            name='MiniLessonItem',
            parent=self.styles['Base'],
            leftIndent=18,
            bulletIndent=0,
            spaceBefore=3,
            bulletFontName=self.BOLD_FONT,
            bulletFontSize=10,
            bulletColor=self.TEAL_COLOR
        ))
        self.styles.add(ParagraphStyle(
            name='HighlightText',
            parent=self.styles['Base'],
            backColor=self.HIGHLIGHT_COLOR,
            borderPadding=2
        ))
        self.styles.add(ParagraphStyle(
            name='HighlightIssue',
            parent=self.styles['Base'],
            leftIndent=10,
            textColor=self.DANGER_COLOR,
            fontName=self.BOLD_FONT
        ))
        self.styles.add(ParagraphStyle(
            name='HighlightSuggestion',
            parent=self.styles['Base'],
            leftIndent=10,
            textColor=self.SUCCESS_COLOR
        ))

    def on_page(self, canvas, doc):
        canvas.saveState()
        # Draw a colored bar at the top
        canvas.setFillColor(self.HEADER_COLOR)
        canvas.rect(doc.leftMargin, doc.height + doc.topMargin - 0.1*inch, doc.width, 0.1*inch, fill=1)
        # Add student's name on the left
        canvas.setFont(self.FONT_NAME, 8)
        canvas.setFillColor(self.TEXT_COLOR)
        canvas.drawString(doc.leftMargin + 0.1*inch, doc.height + doc.topMargin - 0.25*inch, f"Student: {self.student_name}")
        # Add page number on the right
        canvas.drawString(doc.width + doc.leftMargin - 0.75*inch, doc.bottomMargin - 0.25*inch, f"Page {doc.page}")
        canvas.restoreState()

    def _get_score_color(self, score: float, max_score: float) -> colors.Color:
        """Determine color based on score percentage."""
        if max_score is None or max_score == 0:
            return self.TEXT_COLOR # Avoid division by zero
        try:
             percentage = float(score) / float(max_score)
        except (ValueError, TypeError):
             return self.TEXT_COLOR # Handle invalid score types

        if percentage >= 0.8: return self.SUCCESS_COLOR
        if percentage >= 0.6: return self.ACCENT_COLOR # Or a dedicated 'good' color like Teal
        if percentage >= 0.4: return self.WARNING_COLOR
        return self.DANGER_COLOR

    def create(self, evaluation: dict) -> BytesIO:
        pdf_buffer = BytesIO()
        doc = BaseDocTemplate(pdf_buffer, pagesize=letter,
                              rightMargin=0.75 * inch, leftMargin=0.75 * inch,
                              topMargin=1 * inch, bottomMargin=1 * inch)
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        template = PageTemplate(id='main', frames=[frame], onPage=self.on_page)
        doc.addPageTemplates([template])
        elements = []

        # Extract data and set student name
        self.student_name = evaluation.get("student_name", "Unknown Student")
        overall_score = evaluation.get("overall_score", 0.0)
        criteria = evaluation.get("criteria", [])
        suggestions = evaluation.get("suggestions", [])
        highlighted_passages = evaluation.get("highlighted_passages", [])
        mini_lessons = evaluation.get("Mini Lessons", [])
        config = evaluation.get("config", {
            "include_criteria": True, "include_suggestions": True,
            "include_highlights": True, "include_mini_lessons": True
        })
        max_score_total = sum(float(c.get("max_score", 0)) for c in criteria if isinstance(c, dict) and c.get("max_score") is not None)
        if max_score_total == 0 and criteria:
            max_score_total = len(criteria) * 10

        # Header
        elements.append(Paragraph("Essay Evaluation Report", self.styles['MainTitle']))
        elements.append(Paragraph(f"Student: {self.student_name}", self.styles['StudentTitle']))
        score_color = self._get_score_color(overall_score, max_score_total)
        score_text = f"Overall Score: <font color='{score_color.hexval()}'><b>{overall_score:.1f}</b></font>"
        if max_score_total > 0:
            score_text += f" / {max_score_total:.1f}"
        elements.append(Paragraph(score_text, self.styles['ScoreTitle']))

        # Criteria Breakdown Table
        if config.get("include_criteria", True) and criteria:
            section_title_table = Table([[Paragraph("Evaluation Breakdown", self.styles['SectionTitle'])]], colWidths=[doc.width])
            section_title_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), self.LIGHT_BG),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
            elements.append(section_title_table)
            elements.append(Spacer(1, 0.1 * inch))

            table_data = [[
                Paragraph("Criterion", self.styles['TableHeader']),
                Paragraph("Score", self.styles['TableHeader']),
                Paragraph("Feedback", self.styles['TableHeader'])
            ]]
            for crit in criteria:
                if not isinstance(crit, dict): continue
                name = crit.get("name", "N/A")
                score = float(crit.get("score", 0))
                max_score = float(crit.get("max_score", 10))
                feedback = crit.get("feedback", "N/A").replace("\n", "<br/>")
                crit_score_color = self._get_score_color(score, max_score)
                table_data.append([
                    Paragraph(name, self.styles['TableCellBold']),
                    Paragraph(f"<font color='{crit_score_color.hexval()}'>{score:.1f}</font> / {max_score:.1f}", self.styles['TableCellCenter']),
                    Paragraph(feedback, self.styles['FeedbackCell'])
                ])
            table = Table(table_data, colWidths=[1.8 * inch, 0.7 * inch, 4.0 * inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.ACCENT_COLOR),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), self.BOLD_FONT),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [self.LIGHT_BG, colors.white]),
                ('LEFTPADDING', (0, 1), (-1, -1), 6),
                ('RIGHTPADDING', (0, 1), (-1, -1), 6),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        # Highlighted Passages
        if config.get("include_highlights", True) and highlighted_passages:
            section_title_table = Table([[Paragraph("Highlighted Passages / Areas for Improvement", self.styles['SectionTitle'])]], colWidths=[doc.width])
            section_title_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), self.LIGHT_BG),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
            elements.append(section_title_table)
            elements.append(Spacer(1, 0.1 * inch))
            for i, passage in enumerate(highlighted_passages):
                if not isinstance(passage, dict): continue
                text = passage.get('text', 'N/A')
                issue = passage.get('issue', 'N/A')
                suggestion = passage.get('suggestion', 'N/A')
                highlight_table = Table([
                    [Paragraph(f"\"{text}\"", self.styles['HighlightText'])],
                    [Paragraph(f"<b>Issue:</b> {issue}", self.styles['HighlightIssue'])],
                    [Paragraph(f"<b>Suggestion:</b> {suggestion}", self.styles['HighlightSuggestion'])]
                ], colWidths=[doc.width])
                highlight_table.setStyle(TableStyle([
                    ('BOX', (0,0), (-1,-1), 1, self.ACCENT_COLOR),
                    ('TOPPADDING', (0,0), (-1,-1), 5),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                    ('LEFTPADDING', (0,0), (-1,-1), 10),
                    ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ]))
                elements.append(highlight_table)
                elements.append(Spacer(1, 0.15 * inch))

        # General Suggestions
        if config.get("include_suggestions", True) and suggestions:
            section_title_table = Table([[Paragraph("General Suggestions", self.styles['SectionTitle'])]], colWidths=[doc.width])
            section_title_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), self.LIGHT_BG),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
            elements.append(section_title_table)
            elements.append(Spacer(1, 0.1 * inch))
            for sug in suggestions:
                if isinstance(sug, str) and sug:
                    elements.append(Paragraph(sug, self.styles['SuggestionItem'], bulletText='•'))
            elements.append(Spacer(1, 0.2 * inch))

        # Mini Lessons
        if config.get("include_mini_lessons", True) and mini_lessons:
            section_title_table = Table([[Paragraph("Key Mini-Lessons / Focus Areas", self.styles['SectionTitle'])]], colWidths=[doc.width])
            section_title_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), self.LIGHT_BG),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('LEFTPADDING', (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
            elements.append(section_title_table)
            elements.append(Spacer(1, 0.1 * inch))
            for lesson in mini_lessons:
                if isinstance(lesson, str) and lesson.strip():
                    clean_lesson = re.sub(r"^\s*Mini-Lesson\s*:\s*", "", lesson, flags=re.IGNORECASE).strip()
                    elements.append(Paragraph(clean_lesson, self.styles['MiniLessonItem'], bulletText='💡'))
                elif isinstance(lesson, dict):
                    for key, value in lesson.items():
                        elements.append(Paragraph(f"{key}: {value}", self.styles['Base']))
                        elements.append(Spacer(1, 0.05*inch))
            elements.append(Spacer(1, 0.2 * inch))

        # Build the PDF
        doc.build(elements)
        pdf_buffer.seek(0)
        logger.info(f"Successfully created PDF report for {self.student_name}.")
        return pdf_buffer

# --- Rubric Management Helper ---

def get_rubric_by_id(rubric_id: str) -> tuple[Optional[str], Optional[str]]:
    """Loads rubric content and name from a file in the 'rubrics' directory."""
    if not re.match(r'^[\w\-]+$', rubric_id): # Basic validation for filename safety
        logger.warning(f"Invalid rubric_id format attempted: {rubric_id}")
        return None, None
        
    filepath = os.path.join("rubrics", f"{rubric_id}.txt")
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            content = f.read()
        # Assume first line is the name, rest is content (adjust if format differs)
        lines = content.strip().split('\n', 1)
        rubric_name = lines[0].strip() if len(lines) > 0 else None
        rubric_content = lines[1].strip() if len(lines) > 1 else (lines[0].strip() if len(lines) == 1 else None) # Handle single line files
        
        if not rubric_content:
             logger.warning(f"Rubric file '{filepath}' seems empty or only contains a name.")
             # Decide return value: maybe return name but None content?
             return None, rubric_name # Or return DEFAULT_RUBRIC?

        logger.info(f"Loaded rubric '{rubric_name or 'Unnamed'}' from ID: {rubric_id}")
        return rubric_content, rubric_name

    except FileNotFoundError:
        logger.warning(f"Rubric file not found for ID: {rubric_id} at path: {filepath}")
        return None, None
    except Exception as e:
        logger.error(f"Error reading rubric file {filepath}: {e}")
        return None, None

# --- API Endpoints ---

@app.post("/evaluate/", tags=["Evaluation"])
async def evaluate_essay_endpoint(
    essay: UploadFile = File(...), # Make essay file required
    rubric_text: Optional[str] = Form(None),
    rubric_id: Optional[str] = Form(None),
    rubric_file: Optional[UploadFile] = File(None),
    include_criteria: bool = Form(True),
    include_suggestions: bool = Form(True),
    include_highlights: bool = Form(True),
    include_mini_lessons: bool = Form(True),
    api_key: Optional[str] = Form(None) # Allow API key override via form (use with caution)
):
    """
    Endpoint to evaluate one or more essays from an uploaded file.
    Accepts DOCX, PDF, or TXT files.
    Rubric can be provided as text, file upload, or by ID (referencing stored rubrics).
    Returns evaluation status and details, including a session ID for downloading reports.
    """
    server_api_key = os.getenv('GEMINI_API_KEY')
    effective_api_key = api_key or server_api_key # Prioritize key sent in request

    if not effective_api_key:
        logger.error("API key is not configured on the server and was not provided in the request.")
        raise HTTPException(status_code=500, detail="AI API key is not configured.")

    # --- Determine the Rubric ---
    effective_rubric_text = DEFAULT_RUBRIC # Start with default
    rubric_source = "default"
    
    if rubric_text:
        effective_rubric_text = rubric_text
        rubric_source = "text input"
    elif rubric_file:
        try:
            effective_rubric_text = await extract_text(rubric_file)
            rubric_source = f"file upload ({rubric_file.filename})"
            if not effective_rubric_text.strip():
                 logger.warning(f"Uploaded rubric file '{rubric_file.filename}' extracted empty text. Falling back to default.")
                 effective_rubric_text = DEFAULT_RUBRIC
                 rubric_source = "default (uploaded file empty)"
        except ValueError as e:
             logger.warning(f"Could not extract text from uploaded rubric file: {e}. Falling back to default.")
             effective_rubric_text = DEFAULT_RUBRIC
             rubric_source = "default (upload extraction failed)"
    elif rubric_id:
        loaded_rubric_content, loaded_rubric_name = get_rubric_by_id(rubric_id)
        if loaded_rubric_content:
            effective_rubric_text = loaded_rubric_content
            rubric_source = f"ID '{rubric_id}' ({loaded_rubric_name or 'Unnamed'})"
        else:
            logger.warning(f"Could not load rubric for ID '{rubric_id}'. Falling back to default.")
            # Keep DEFAULT_RUBRIC set earlier
            rubric_source = f"default (ID '{rubric_id}' not found or invalid)"

    logger.info(f"Using rubric from: {rubric_source}")

    # --- Extract Essay Text ---
    try:
        essay_text_content = await extract_text(essay)
        if not essay_text_content.strip():
            logger.error(f"Uploaded essay file '{essay.filename}' resulted in empty content.")
            raise HTTPException(status_code=400, detail="Essay file is empty or could not be read.")
    except ValueError as e:
        logger.error(f"Failed to extract text from essay file '{essay.filename}': {e}")
        raise HTTPException(status_code=400, detail=f"Error processing essay file: {e}")
    except Exception as e: # Catch unexpected errors during extraction
        logger.error(f"Unexpected error extracting text from '{essay.filename}': {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while reading the essay file.")

    # --- Perform Evaluation(s) ---
    try:
        evaluations = await evaluate_essays(
            essay_text=essay_text_content,
            rubric_text=effective_rubric_text,
            api_key=effective_api_key,
            include_criteria=include_criteria,
            include_suggestions=include_suggestions,
            include_highlights=include_highlights,
            include_mini_lessons=include_mini_lessons
        )
    except ValueError as e: # Catch errors from evaluate_essay if retry fails
         logger.error(f"Evaluation failed permanently: {e}")
         raise HTTPException(status_code=500, detail=f"AI evaluation failed: {e}")
    except Exception as e: # Catch other unexpected errors in evaluate_essays
         logger.error(f"Unexpected error during evaluation process: {e}\n{traceback.format_exc()}")
         raise HTTPException(status_code=500, detail="An unexpected error occurred during evaluation.")


    if not evaluations:
        logger.warning(f"Evaluation process returned no results for file '{essay.filename}'.")
        raise HTTPException(status_code=400, detail="No essays could be evaluated from the provided file. Check file content and splitting logic.")

    # --- Store Results and Prepare Response ---
    session_id = str(uuid.uuid4())
    session_storage_entry = {}
    results_summary = []
    
    # Generate safe filenames and prepare summary
    for i, evaluation in enumerate(evaluations):
        student_name = evaluation.get("student_name", f"Unknown_{i+1}")
        # Sanitize name for filename: remove unsafe characters, limit length
        safe_name = re.sub(r'[^\w\-]+', '_', student_name).strip('_')
        safe_name = safe_name[:50] # Limit length
        filename = f"{safe_name}_Evaluation_{i+1}.pdf"
        
        session_storage_entry[filename] = evaluation
        
        # Calculate max score for summary (handle potential errors in evaluation structure)
        max_score = 0
        try:
             # Ensure criteria is a list of dicts
             if isinstance(evaluation.get("criteria"), list):
                 max_score = sum(float(c.get("max_score", 0)) for c in evaluation["criteria"] if isinstance(c, dict))
        except Exception:
             logger.warning(f"Could not calculate max_score for summary of '{student_name}'.")


        results_summary.append({
            "id": i, # Simple index
            "filename": filename,
            "student_name": student_name,
            "overall_score": evaluation.get("overall_score", 0), # Default to 0 if missing
            "max_score": max_score,
            "error": evaluation.get("error", False) # Include error flag in summary
        })

    evaluation_storage[session_id] = session_storage_entry
    logger.info(f"Stored {len(evaluations)} evaluation(s) under session ID: {session_id}")

    # --- Return Response based on single/multiple essays ---
    if len(evaluations) == 1:
        single_result = results_summary[0]
        return {
            "evaluation_status": "single",
            "session_id": session_id,
            "filename": single_result["filename"],
            "student_name": single_result["student_name"],
            "overall_score": single_result["overall_score"],
            "max_score": single_result["max_score"],
            "error": single_result["error"]
        }
    else:
        return {
            "evaluation_status": "multiple",
            "session_id": session_id,
            "count": len(evaluations),
            "results": results_summary # Contains details for each evaluated essay
        }


@app.get("/download-report/{session_id}/{filename}", tags=["Download"])
async def download_single_report(session_id: str, filename: str):
    """Downloads a previously generated PDF evaluation report."""
    logger.info(f"Request received for session '{session_id}', filename '{filename}'")
    
    # Validate inputs
    if not re.match(r'^[\w\-]+\.pdf$', filename, re.IGNORECASE):
         logger.warning(f"Invalid filename format requested: {filename}")
         raise HTTPException(status_code=400, detail="Invalid filename format.")
         
    if session_id not in evaluation_storage:
        logger.warning(f"Session ID not found: {session_id}")
        raise HTTPException(status_code=404, detail="Evaluation session not found or expired.")
        
    if filename not in evaluation_storage[session_id]:
        logger.warning(f"Filename '{filename}' not found within session '{session_id}'")
        raise HTTPException(status_code=404, detail="Specific report file not found in this session.")

    evaluation_data = evaluation_storage[session_id][filename]

    # Check if the evaluation itself was an error case
    if evaluation_data.get("error"):
        logger.info(f"Attempting to download report for a failed evaluation: {filename}")
        # Optionally generate a simple PDF indicating the error, or return 404/500
        # For now, let's try generating the report which should show the error details
        # raise HTTPException(status_code=500, detail="The original evaluation for this report failed.")

    try:
        pdf_generator = PDFReport()
        pdf_buffer = pdf_generator.create(evaluation_data)
        
        # Clean up the specific entry after successful generation? Optional.
        # Consider TTL for session_id cleanup later.
        # del evaluation_storage[session_id][filename] # Be careful with concurrency if you do this
        
        logger.info(f"Sending PDF report: {filename}")
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"" # Ensure filename is quoted
            }
        )
    except RuntimeError as pdf_err: # Catch PDF generation errors
         logger.error(f"Failed to generate PDF report for {filename}: {pdf_err}")
         raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {pdf_err}")
    except Exception as e:
         logger.error(f"Unexpected error during PDF download for {filename}: {e}\n{traceback.format_exc()}")
         raise HTTPException(status_code=500, detail="An unexpected error occurred while generating the report.")

# --- Add other endpoints here (e.g., for rubric management) ---
# Example: List available rubrics
@app.get("/rubrics/", tags=["Rubrics"])
async def list_rubrics():
    """Lists the available rubrics stored on the server."""
    rubric_files = {}
    try:
        for filename in os.listdir("rubrics"):
            if filename.endswith(".txt"):
                rubric_id = filename[:-4] # Remove .txt extension
                _, name = get_rubric_by_id(rubric_id)
                rubric_files[rubric_id] = name if name else rubric_id # Use ID if name is missing
        return rubric_files
    except FileNotFoundError:
        logger.warning("Rubrics directory not found when listing.")
        return {}
    except Exception as e:
        logger.error(f"Error listing rubrics: {e}")
        raise HTTPException(status_code=500, detail="Could not list available rubrics.")

# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    # Fetch host/port from environment variables or use defaults
    host = os.getenv("HOST", "0.0.0.0")  # Changed default to "0.0.0.0"
    port = int(os.getenv("PORT", "8000"))  # Use $PORT if available, else 8000
    reload = os.getenv("RELOAD", "false").lower() == "true"  # Disable reload by default for production

    print(f"Starting server on {host}:{port} (Reload: {reload})")
    print(f"Allowed Origins: {origins if origins else '*'}")

    uvicorn.run("main:app", host=host, port=port, reload=reload)