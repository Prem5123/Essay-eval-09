# [source: 1]
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
# Added Dict, Any, Union, Literal
from typing import Any, Dict, List, Literal, Optional, Union
# [source: 2]
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate,
                              Paragraph, Spacer, Table, TableStyle)

# [source: 1]
import google.generativeai as genai
import pdfplumber
from docx import Document
from dotenv import load_dotenv
# Added Depends, Body
from fastapi import (Body, Depends, FastAPI, File, Form, HTTPException,
                     Response, UploadFile)
from fastapi.middleware.cors import CORSMiddleware
# Added Field, field_validator, ValidationError, HttpUrl
from pydantic import (BaseModel, Field, HttpUrl, ValidationError,
                      field_validator)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch


# --- Pydantic Models ---

# [source: 2]
class CriterionEvaluation(BaseModel):
    """Model for a single criterion evaluation within the rubric."""
    name: str
    score: float
    max_score: float
    feedback: str

class HighlightedPassage(BaseModel):
    """Model for a highlighted passage with feedback."""
    text: str
    issue: str
    # [source: 3]
    suggestion: str
    example_revision: Optional[str] = None

# [source: 3]
class EssayEvaluation(BaseModel):
    """Model for the complete evaluation result of a single essay."""
    student_name: str = "Unknown Student"
    overall_score: float
    criteria: List[CriterionEvaluation]
    suggestions: List[str]
    highlighted_passages: List[HighlightedPassage]
    # Alias to match Gemini output
    mini_lessons: List[str] = Field(..., alias="Mini Lessons")
    error: Optional[str] = None # To indicate processing errors

    @field_validator('overall_score')
    @classmethod
    def check_overall_score_consistency(cls, v: float, info: Any):
        # [source: 4]
        """Recalculate and potentially warn if overall score differs from sum of criteria."""
        if 'criteria' in info.data:
            calculated_score = sum(c.score for c in info.data['criteria'])
            if abs(v - calculated_score) > 0.1:
                # Log warning or decide to override 'v' with 'calculated_score'
                # [source: 5]
                logger.warning(f"Provided overall_score ({v}) differs significantly from calculated criteria sum ({calculated_score}) for student '{info.data.get('student_name', 'N/A')}'.")
                # [source: 6]
                logger.warning("Using calculated score.")
                return calculated_score # Override with calculated score
        return v # Return original or calculated score

    @field_validator('criteria')
    @classmethod
    def check_criteria_scores(cls, v: List[CriterionEvaluation]):
        """Ensure individual criteria scores are within bounds."""
        for criterion in v:
            if not (0 <= criterion.score <= criterion.max_score):
                # [source: 7]
                logger.warning(f"Criterion '{criterion.name}' score ({criterion.score}) is outside the allowed range (0-{criterion.max_score}). Clamping score.")
                # Clamp score
                criterion.score = max(0.0, min(criterion.score, criterion.max_score))
        return v

# [source: 7]
# Model for the form data in the main evaluation endpoint
class EvaluationRequestForm(BaseModel):
    rubric_text: Optional[str] = None
    rubric_id: Optional[str] = None
    include_criteria: bool = True
    include_suggestions: bool = True
    # [source: 8]
    include_highlights: bool = True
    include_mini_lessons: bool = True
    api_key: Optional[str] = None
    # --- NEW: Added generosity parameter ---
    # Allows specifying strictness ('strict', 'standard', 'generous')
    generosity: Literal['strict', 'standard', 'generous'] = 'standard' # Default to standard

# --- Configuration & Setup ---

# [source: 8]
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
allowed_origins_str = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,https://essay-evaluator-mu.vercel.app")
origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Allowed file types
ALLOWED_TYPES = { # [source: 9]
    'application/pdf',
    'text/plain',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

# [source: 9]
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

# [source: 10]
# In-memory storage for multi-essay PDF generation (Session ID -> Filename -> Evaluation Data)
# Using Union to allow for error dict structure as well, though ideally Error model is used
evaluation_storage: Dict[str, Dict[str, Union[EssayEvaluation, Dict[str, Any]]]] = {}


# --- Essay Processing Functions ---

async def extract_text(file: UploadFile) -> str:
    """Extract text from uploaded files (PDF, TXT, DOCX).""" # [source: 11]
    logger.info(f"Extracting text from file: '{file.filename}' (Type: {file.content_type})") # [source: 11]
    content = await file.read()
    if not content:
        logger.warning(f"File '{file.filename}' is empty.")
        raise ValueError(f"Cannot read an empty file: '{file.filename}'.")

    filename = file.filename.lower() if file.filename else ""
    content_type = file.content_type

    try:
        if content_type == 'text/plain' or filename.endswith('.txt'):
            try:
                return content.decode('utf-8') # [source: 12]
            except UnicodeDecodeError:
                logger.warning(f"UTF-8 decoding failed for '{file.filename}', trying latin-1.") # [source: 12]
                return content.decode('latin-1') # Fallback encoding
        elif content_type == 'application/pdf' or filename.endswith('.pdf'):
            with pdfplumber.open(BytesIO(content)) as pdf:
                text = '\n'.join([(page.extract_text() or '') for page in pdf.pages]) # [source: 13]
            if not text.strip():
                 logger.warning(f"Extracted empty text from PDF: '{file.filename}'. May be image-based.") # [source: 13]
            return text # [source: 14]
        elif content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or filename.endswith('.docx'): # [source: 14]
            with BytesIO(content) as doc_file:
                try:
                    doc = Document(doc_file)
                    text = '\n'.join([para.text for para in doc.paragraphs]) # [source: 15]
                    return text
                except Exception as docx_err:
                    logger.error(f"Error parsing DOCX file '{file.filename}': {docx_err}") # [source: 15]
                    raise ValueError(f"Failed to parse DOCX file '{file.filename}'.")
        else: # [source: 16]
            logger.warning(f"Unsupported file format received: {content_type} for file '{filename}'") # [source: 16]
            raise ValueError(f"Unsupported file format: {content_type}")
    except Exception as e:
        logger.error(f"Error extracting text from '{file.filename}': {str(e)}\n{traceback.format_exc()}") # [source: 16]
        raise ValueError(f"Failed to extract text from '{file.filename}'. Ensure the file is not corrupted or password-protected.") # [source: 17]


# [source: 17]
def split_essays(text: str) -> List[str]:
    """Split text into multiple essays based on student name patterns or paragraph breaks."""
    logger.info("Attempting to split text into multiple essays.")
    # Enhanced patterns
    patterns = [
        r"^\s*(?:student\s+)?name\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
        r"^\s*student\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
    ]

    all_matches = []
    for pattern in patterns:
        matches = list(re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE))
        all_matches.extend([(m.start(), m.group(1).strip()) for m in matches]) # [source: 18]

    all_matches.sort(key=lambda x: x[0])

    essays = []
    last_pos = 0

    if not all_matches:
        logger.info("No name patterns found. Trying to split by significant whitespace.")
        chunks = re.split(r'\n{4,}', text.strip())
        potential_essays = [chunk.strip() for chunk in chunks if len(chunk.strip()) > 300]
        if len(potential_essays) > 1:
            logger.info(f"Split into {len(potential_essays)} potential essays based on whitespace.") # [source: 19]
            return potential_essays
        else:
            logger.info("Could not split by whitespace or only one chunk found.") # [source: 19]
            logger.info("Treating as a single essay.") # [source: 20]
            return [text.strip()] if text.strip() else []

    logger.info(f"Found {len(all_matches)} potential essay start points based on name patterns.") # [source: 20]
    for i, (start_pos, name) in enumerate(all_matches):
        segment = text[last_pos:start_pos].strip()
        # Add segment *before* the name match if it's substantial and not the first part (or first part is long)
        if segment and len(segment) > 100:
            if i == 0 and len(segment) > 300: # Heuristic for intro section # [source: 21]
                  essays.append(segment)
            elif i > 0:
                  essays.append(segment) # Belongs to the previous student # [source: 21]

        # Determine the end position for the current essay
        essay_content = "" # [source: 22]
        if i == len(all_matches) - 1:
            essay_content = text[start_pos:].strip() # From current match to end # [source: 22]
        else:
            next_start_pos = all_matches[i + 1][0]
            essay_content = text[start_pos:next_start_pos].strip() # From current match to next match # [source: 22]

        if essay_content and len(essay_content) > 200:
            essays.append(essay_content) # [source: 23]

        last_pos = start_pos if i == len(all_matches) - 1 else all_matches[i+1][0] # Update last_pos carefully # [source: 23]


    # Filter out empty strings and very short segments again
    final_essays = [essay for essay in essays if len(re.sub(r'\s+', '', essay)) > 250]

    if not final_essays:
         logger.warning("Splitting logic resulted in no valid essay content.") # [source: 23]
         logger.warning("Returning original text if non-empty.") # [source: 24]
         original_stripped = text.strip()
         return [original_stripped] if len(original_stripped) > 250 else []

    logger.info(f"Final count after splitting and filtering: {len(final_essays)} essays.") # [source: 24]
    return final_essays


async def evaluate_essays(
    essay_text: str,
    rubric_text: Optional[str],
    api_key: str,
    generosity: Literal['strict', 'standard', 'generous'], # --- Pass generosity ---
    # Config flags are now passed down but not explicitly used here
    # as they are handled by the PDF generation based on the model content
) -> List[Union[EssayEvaluation, Dict[str, Any]]]: # Return list of models or error dicts # [source: 25]
    """Evaluate multiple essays if detected, handling potential errors for each."""
    essays = split_essays(essay_text) # [source: 25]
    logger.info(f"Attempting to evaluate {len(essays)} detected essay(s).")

    if not essays:
        logger.warning("Splitting resulted in zero essays.")
        return []

    results: List[Union[EssayEvaluation, Dict[str, Any]]] = []
    base_delay = 1.5
    max_delay_increment = 1.0

    tasks = []
    for i, essay_content in enumerate(essays):
        if not essay_content or not essay_content.strip(): # [source: 26]
            logger.warning(f"Skipping empty essay chunk at index {i}.") # [source: 26]
            continue

        task = evaluate_single_essay_with_error_handling(
            essay_content=essay_content,
            rubric_text=rubric_text,
            api_key=api_key,
            essay_index=i,
            generosity=generosity, # --- Pass generosity ---
            delay=(base_delay + random.uniform(0, max_delay_increment)) if i > 0 else 0 # [source: 27]
        )
        tasks.append(task)

    evaluation_results = await asyncio.gather(*tasks) # [source: 27]

    # Keep all results, including error dicts, for comprehensive reporting
    results = [res for res in evaluation_results if res is not None] # Filter out potential None returns if gather has issues

    logger.info(f"Finished evaluating.") # [source: 27]
    logger.info(f"Got {len(results)} results (including potential errors) out of {len(essays)} detected essays.") # [source: 28]
    return results


async def evaluate_single_essay_with_error_handling(
    essay_content: str,
    rubric_text: Optional[str],
    api_key: str,
    essay_index: int,
    generosity: Literal['strict', 'standard', 'generous'], # --- Receive generosity ---
    delay: float
) -> Union[EssayEvaluation, Dict[str, Any]]: # Return model or error dict
    """Helper to evaluate one essay and capture errors, includes delay."""
    if delay > 0:
        await asyncio.sleep(delay)

    student_name = "Unknown Student"
    try:
        logger.info(f"Starting evaluation for essay index {essay_index}...") # [source: 29]
        # Extract name early for potential error reporting
        first_lines = "\n".join(essay_content.split('\n')[:15])
        name_patterns = [
             r"^\s*(?:student\s+)?name\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
             r"^\s*student\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
             r"^\s*author\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
        ]
        for pattern in name_patterns: # [source: 30]
             name_match = re.search(pattern, first_lines, re.IGNORECASE | re.MULTILINE) # [source: 31]
             if name_match:
                  potential_name = name_match.group(1).strip()
                  if potential_name.lower() not in ["student name", "name", "enter name here", "author"]:
                       student_name = potential_name
                       logger.info(f"Extracted student name for essay {essay_index}: {student_name}") # [source: 32]
                       break
        if student_name == "Unknown Student":
             logger.warning(f"Could not extract student name for essay {essay_index}.") # [source: 32]

        # Perform the core evaluation
        evaluation = await evaluate_essay(essay_content, rubric_text, api_key, student_name, generosity) # --- Pass generosity ---
        logger.info(f"Successfully evaluated essay index {essay_index} for '{evaluation.student_name}'.") # [source: 33]
        return evaluation

    except (ValueError, ValidationError, Exception) as e:
        # Catch specific errors from evaluate_essay or Pydantic validation, plus general exceptions
        error_message = f"Evaluation failed: {str(e)}"
        logger.error(f"Error processing essay index {essay_index} for '{student_name}': {error_message}\n{traceback.format_exc()}") # [source: 33]

        # Return a consistent error structure (dictionary, not the Pydantic model)
        return { # [source: 34]
            "student_name": student_name if student_name != "Unknown Student" else f"Failed_Essay_{essay_index+1}",
            "overall_score": 0,
            "criteria": [{"name": "Processing Error", "score": 0, "max_score": 0, "feedback": error_message}],
            "suggestions": ["The AI evaluation could not be completed due to an error."],
            "highlighted_passages": [],
            "Mini Lessons": [], # Keep structure consistent # [source: 35]
            "error": error_message, # Flag indicating failure with message
            "is_error_object": True # Explicit flag to differentiate from successful EssayEvaluation model
        }


async def evaluate_essay(
    essay_text: str,
    rubric_text: Optional[str],
    api_key: str,
    extracted_student_name: str, # Pass the already extracted name
    generosity: Literal['strict', 'standard', 'generous'] # --- Receive generosity ---
    ) -> EssayEvaluation:
    """Evaluate a single essay using the Gemini API and parse into EssayEvaluation model.""" # [source: 36]
    if not api_key:
        logger.error("Gemini API key is missing.") # [source: 36]
        raise ValueError("API key not configured.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash-latest') # Or consider gemini-1.5-pro for potentially higher quality # [source: 36]

    rubric = rubric_text if rubric_text and rubric_text.strip() else DEFAULT_RUBRIC

    # Parse rubric to dynamically generate parts of the prompt if needed (mainly for criteria structure example)
    criteria_matches = re.findall(
        r"^\s*(?:\d+\.?\s*)?([A-Za-z &/'\-]+?)\s*\(\s*(\d+)\s*-?\s*(\d+)\s*\)\s*:", # [source: 37]
        rubric,
        re.MULTILINE | re.IGNORECASE # [source: 38]
    )
    criteria_details = []
    if criteria_matches:
        criteria_details = [(match[0].strip(), int(match[2])) for match in criteria_matches] # (name, max_score) # [source: 38]
    else:
        logger.warning("Could not parse criteria details (name, max_score) from rubric. Using default structure assumption in prompt.") # [source: 38]
        # Use a generic placeholder if parsing fails
        criteria_details = [("Parsed Criterion 1", 10), ("Parsed Criterion 2", 10), ("Parsed Criterion 3", 10), ("Parsed Criterion 4", 10), ("Parsed Criterion 5", 10)] # [source: 39]

    # Construct the example JSON structure string for the prompt
    criteria_json_examples = ",\n".join([
        f'    {{"name": "{name}", "score": number (0-{max_score}), "max_score": {max_score}, "feedback": "Specific feedback for {name}."}}'
        for name, max_score in criteria_details
    ]) if criteria_details else ""

    # --- NEW: Define generosity instructions ---
    generosity_instruction = ""
    if generosity == 'strict':
        generosity_instruction = """
- **Evaluation Stance**: Apply the rubric criteria with strict adherence. Focus on identifying areas needing improvement and maintain rigorous scoring. Highlight specific errors and inconsistencies clearly. Feedback should be direct and critical where necessary."""
        temperature = 0.1 # Lower for stricter adherence
    elif generosity == 'generous':
        generosity_instruction = """
- **Evaluation Stance**: Apply the rubric criteria with understanding and flexibility. Focus on identifying strengths and potential. Frame feedback constructively and offer encouragement. Be slightly more lenient in scoring, particularly where effort or good ideas are evident but execution is imperfect."""
        temperature = 0.4 # Slightly higher for more creative/generous feedback
    else: # standard (default)
        generosity_instruction = """
- **Evaluation Stance**: Apply the rubric criteria fairly and objectively. Provide balanced feedback addressing both strengths and weaknesses. Score accurately based on the defined standards."""
        temperature = 0.2 # Default temperature

    # --- Construct the Prompt ---
    prompt = f"""
Analyze the following student essay based *strictly* on the provided rubric criteria, adjusting your evaluation strictness based on the 'Evaluation Stance'.
**RUBRIC:**
{rubric}

**ESSAY TEXT:**
{essay_text}

---
**EVALUATION TASK:**
Provide a detailed evaluation in JSON format. Follow the structure defined in the `EssayEvaluation` schema below precisely.
**JSON OUTPUT STRUCTURE (Adhere to this Pydantic-like schema):**
{{
  "student_name": "{extracted_student_name}", // Use the extracted name provided
  "overall_score": number, // REQUIRED: Calculated sum of scores from criteria below
  "criteria": [ // REQUIRED: Array based on RUBRIC
    // Example for one criterion (repeat for ALL criteria from RUBRIC):
{criteria_json_examples if criteria_json_examples else '    {"name": "Criterion Name from Rubric", "score": number (0-max), "max_score": number (max score for this), "feedback": "Specific feedback..."}'}
    // Ensure score is within the max_score. Feedback must be specific.
  ],
  "suggestions": [ // REQUIRED: List of strings
    "Provide 2-3 specific, actionable suggestions for overall improvement.",
    "Focus on the most impactful areas for the student."
  ],
  "highlighted_passages": [ // REQUIRED: List of objects
    // Identify 3-5 specific sentences or short passages illustrating key strengths or weaknesses, adjusted by Evaluation Stance.
    {{ // Structure for each highlight:
      "text": "Exact short text snippet from the essay...", // REQUIRED
      "issue": "Brief description (e.g., 'Awkward phrasing', 'Needs evidence', 'Strong point')", // REQUIRED
      "suggestion": "How to improve this specific text.", // REQUIRED
      "example_revision": "Optional: Show a revised version." // OPTIONAL
    }}
    // Add more highlights following the same structure.
  ],
  "Mini Lessons": [ // REQUIRED: List of strings (use this exact key "Mini Lessons")
      // Provide 2-3 "Mini Lessons": actionable tips/concepts based on evaluation.
      // Each lesson should be detailed (50+ words), relevant, use simple language, maybe an analogy.
      "Example Mini Lesson: Explain the importance of clear topic sentences..."
  ]
}}

**IMPORTANT INSTRUCTIONS:**
{generosity_instruction} # --- Insert generosity instruction ---
- Output ONLY the valid JSON object conforming to the structure above.
- Do NOT include markdown formatting (```json ... ```) or any text outside the JSON structure.
- Ensure all required fields are present.
- Calculate `overall_score` accurately by summing the scores given in the `criteria` array.
- Base all feedback, suggestions, highlights, and mini-lessons directly on the provided ESSAY TEXT and RUBRIC.
- If the essay text is extremely short, nonsensical, or completely off-topic, reflect this in the feedback and assign low scores (possibly 0).
  Provide minimal suggestions/highlights/lessons if appropriate.
"""

    max_retries = 3
    last_error = None

    safety_settings = {
        genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    }

    generation_config = genai.types.GenerationConfig(
        temperature=temperature, # --- Use dynamic temperature based on generosity ---
        response_mime_type="application/json", # Request JSON directly
        # response_schema=EssayEvaluation # Providing schema helps model adhere, but validation happens separately too # [source: 54]
    )

    for attempt in range(max_retries):
        try:
            logger.info(f"Sending request to Gemini API for '{extracted_student_name}' (Attempt {attempt + 1}/{max_retries}, Generosity: {generosity})...") # [source: 54]
            response = await model.generate_content_async(
                prompt,
                generation_config=generation_config, # [source: 55]
                safety_settings=safety_settings
            )

            if not response.candidates:
                block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else 'Unknown' # [source: 55]
                finish_reason = response.candidates[0].finish_reason if response.candidates else 'Unknown'
                logger.error(f"Gemini API call failed for '{extracted_student_name}': No candidates returned.") # [source: 56]
                logger.error(f"Block Reason: {block_reason}, Finish Reason: {finish_reason}") # [source: 57]
                # Check safety ratings if needed: response.candidates[0].safety_ratings
                raise ValueError(f"API response blocked or empty. Reason: {block_reason}/{finish_reason}") # [source: 57]

            response_text = response.text # The response should be JSON text now # [source: 57]

            # --- Parse and Validate using Pydantic ---
            logger.info(f"Attempting to parse API response for '{extracted_student_name}' using Pydantic model.") # [source: 58]
            # Clean potential markdown, although less likely with response_mime_type="application/json"
            cleaned_response = re.sub(r'^```json\s*|\s*```$', '', response_text.strip(), flags=re.MULTILINE | re.DOTALL).strip() # [source: 58]

            # Load the string into a dictionary first for inspection if needed
            raw_result_dict = {} # Initialize
            try:
                raw_result_dict = json.loads(cleaned_response) # [source: 59]
            except json.JSONDecodeError as json_err:
                 logger.error(f"Failed to decode JSON response on attempt {attempt + 1} for '{extracted_student_name}': {json_err}") # [source: 59]
                 logger.debug(f"Raw response causing JSON error:\n---\n{cleaned_response[:1000]}...\n---")
                 last_error = json_err # [source: 60]
                 continue # Retry

            # Now parse the dictionary using the Pydantic model
            validated_evaluation = EssayEvaluation.model_validate(raw_result_dict) # [source: 60]

            # Ensure student name consistency (use extracted if API didn't or used placeholder)
            if validated_evaluation.student_name in ["Unknown Student", "Student Name", ""] and extracted_student_name != "Unknown Student": # [source: 61]
                 logger.info(f"Overriding model student name ('{validated_evaluation.student_name}') with extracted name ('{extracted_student_name}').") # [source: 61]
                 validated_evaluation.student_name = extracted_student_name
            elif not validated_evaluation.student_name: # Handle case where model has empty string # [source: 61]
                 validated_evaluation.student_name = extracted_student_name if extracted_student_name != "Unknown Student" else f"Student_{uuid.uuid4().hex[:6]}" # Assign a fallback # [source: 62]

            logger.info(f"Successfully parsed and validated API response for student: {validated_evaluation.student_name}") # [source: 62]
            return validated_evaluation # Success

        except ValidationError as pydantic_err:
            logger.error(f"Pydantic validation failed on attempt {attempt + 1} for '{extracted_student_name}': {pydantic_err}") # [source: 62]
            logger.debug(f"Data causing validation error:\n---\n{raw_result_dict}\n---")
            last_error = pydantic_err # Store the validation error # [source: 63]
            # Optionally: Log specific errors: pydantic_err.errors()
        except ValueError as ve: # Catch ValueErrors raised earlier (e.g., API blocked) # [source: 63]
             logger.error(f"ValueError during API call or processing for '{extracted_student_name}' on attempt {attempt+1}: {ve}", exc_info=True)
             last_error = ve
        except Exception as e:
            logger.error(f"Unexpected error during API call/parsing for '{extracted_student_name}' on attempt {attempt + 1}: {str(e)}\n{traceback.format_exc()}") # [source: 64]
            last_error = e

        # Exponential backoff before retrying
        if attempt < max_retries - 1:
            wait_time = (2 ** attempt) * 1.5 + random.uniform(0, 1) # Increased base backoff # [source: 64]
            logger.info(f"Retrying evaluation for '{extracted_student_name}' in {wait_time:.2f} seconds...") # [source: 65]
            await asyncio.sleep(wait_time)

    # If all retries fail
    logger.error(f"Failed to evaluate essay for '{extracted_student_name}' after {max_retries} attempts.") # [source: 65]
    raise ValueError(f"Failed to get valid evaluation for '{extracted_student_name}' after {max_retries} attempts. Last error: {str(last_error)}") # [source: 66]



# --- PDF Report Generation Class ---

# [source: 66]
class PDFReport:
    # Color and Font definitions (as before)
    HEADER_COLOR = colors.HexColor('#4c1d95')
    ACCENT_COLOR = colors.HexColor('#7c3aed')
    LIGHT_BG = colors.HexColor('#f0e7ff')
    SUCCESS_COLOR = colors.HexColor('#059669')
    WARNING_COLOR = colors.HexColor('#d97706')
    DANGER_COLOR = colors.HexColor('#dc2626')
    TEAL_COLOR = colors.HexColor('#0d9488')
    HIGHLIGHT_COLOR = colors.HexColor('#fef08a')
    TEXT_COLOR = colors.HexColor('#1e293b')
    FONT_NAME = 'Helvetica'
    BOLD_FONT = 'Helvetica-Bold'

    def __init__(self):
        self.styles = getSampleStyleSheet() # [source: 67]
        self._create_custom_styles()
        self.student_name: str = "Unknown Student" # Added type hint # [source: 67]

    def _create_custom_styles(self):
        # Base style
        self.styles.add(ParagraphStyle(name='Base', parent=self.styles['Normal'], fontName=self.FONT_NAME, fontSize=10, textColor=self.TEXT_COLOR, leading=14))
        self.styles.add(ParagraphStyle(name='MainTitle', parent=self.styles['h1'], fontName=self.BOLD_FONT, fontSize=24, spaceAfter=12, alignment=TA_CENTER, textColor=self.ACCENT_COLOR))
        self.styles.add(ParagraphStyle(name='StudentTitle', parent=self.styles['h2'], fontName=self.FONT_NAME, fontSize=14, spaceAfter=6, alignment=TA_CENTER, textColor=self.HEADER_COLOR))
        self.styles.add(ParagraphStyle(name='ScoreTitle', parent=self.styles['h3'], fontName=self.BOLD_FONT, fontSize=12, spaceAfter=18, alignment=TA_CENTER, textColor=self.TEXT_COLOR))
        self.styles.add(ParagraphStyle(name='SectionTitle', parent=self.styles['h3'], fontName=self.BOLD_FONT, fontSize=14, spaceBefore=12, spaceAfter=8, textColor=self.HEADER_COLOR)) # [source: 68]
        # Table Styles
        self.styles.add(ParagraphStyle(name='TableHeader', fontName=self.BOLD_FONT, alignment=TA_CENTER, textColor=colors.white))
        self.styles.add(ParagraphStyle(name='TableCell', parent=self.styles['Base'], alignment=TA_LEFT, leading=12))
        self.styles.add(ParagraphStyle(name='TableCellBold', parent=self.styles['TableCell'], fontName=self.BOLD_FONT))
        self.styles.add(ParagraphStyle(name='TableCellCenter', parent=self.styles['TableCell'], alignment=TA_CENTER))
        self.styles.add(ParagraphStyle(name='FeedbackCell', parent=self.styles['TableCell'], fontSize=9))
        # List Item Styles
        self.styles.add(ParagraphStyle(name='SuggestionItem', parent=self.styles['Base'], leftIndent=18, bulletIndent=0, spaceBefore=3, bulletFontName=self.BOLD_FONT, bulletFontSize=10, bulletColor=self.ACCENT_COLOR))
        self.styles.add(ParagraphStyle(name='MiniLessonItem', parent=self.styles['Base'], leftIndent=18, bulletIndent=0, spaceBefore=3, bulletFontName=self.BOLD_FONT, bulletFontSize=10, bulletColor=self.TEAL_COLOR)) # [source: 69]
        # Highlight Styles
        self.styles.add(ParagraphStyle(name='HighlightText', parent=self.styles['Base'], backColor=self.HIGHLIGHT_COLOR, borderPadding=(2, 4))) # Added vertical padding
        self.styles.add(ParagraphStyle(name='HighlightIssue', parent=self.styles['Base'], leftIndent=10, textColor=self.DANGER_COLOR, fontName=self.BOLD_FONT, spaceBefore=2))
        self.styles.add(ParagraphStyle(name='HighlightSuggestion', parent=self.styles['Base'], leftIndent=10, textColor=self.SUCCESS_COLOR, spaceBefore=1))
        # Error Message Style
        self.styles.add(ParagraphStyle(name='ErrorText', parent=self.styles['Base'], textColor=self.DANGER_COLOR, fontName=self.BOLD_FONT, alignment=TA_CENTER, spaceBefore=12, fontSize=12))


    def on_page(self, canvas, doc):
        """Adds header and footer elements to each page.""" # [source: 70]
        canvas.saveState()
        # Top Bar
        canvas.setFillColor(self.HEADER_COLOR)
        canvas.rect(doc.leftMargin, doc.height + doc.topMargin - 0.1*inch, doc.width, 0.1*inch, fill=1)
        # Student Name (Top Left)
        canvas.setFont(self.FONT_NAME, 8)
        canvas.setFillColor(self.TEXT_COLOR)
        canvas.drawString(doc.leftMargin + 0.1*inch, doc.height + doc.topMargin - 0.25*inch, f"Student: {self.student_name}")
        # Page Number (Bottom Right) - Adjusted position # [source: 71]
        canvas.drawString(doc.leftMargin + doc.width - 0.5*inch, doc.bottomMargin - 0.25*inch, f"Page {doc.page}")
        canvas.restoreState()

    def _get_score_color(self, score: float, max_score: float) -> colors.Color:
        """Determine color based on score percentage.""" # [source: 71]
        if max_score is None or max_score <= 0: # Handle zero/None max_score # [source: 71]
            return self.TEXT_COLOR
        try: # [source: 72]
             percentage = float(score) / float(max_score)
        except (ValueError, TypeError):
             return self.TEXT_COLOR

        if percentage >= 0.8: return self.SUCCESS_COLOR
        if percentage >= 0.6: return self.ACCENT_COLOR # Changed mid-range color
        if percentage >= 0.4: return self.WARNING_COLOR
        return self.DANGER_COLOR

    def _create_section_title(self, title_text: str, doc_width: float) -> Table: # [source: 73]
         """Creates a styled section title bar."""
         title_para = Paragraph(title_text, self.styles['SectionTitle']) # [source: 73]
         section_table = Table([[title_para]], colWidths=[doc_width])
         section_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), self.LIGHT_BG),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), # [source: 74]
                ('LEFTPADDING', (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
         return section_table # [source: 75]

    def create(self, evaluation_data: Union[EssayEvaluation, Dict[str, Any]], config_flags: Dict[str, bool]) -> BytesIO:
        """Creates the PDF report from EssayEvaluation model or error dict.""" # [source: 75]
        pdf_buffer = BytesIO()
        doc = BaseDocTemplate(pdf_buffer, pagesize=letter,
                              rightMargin=0.75 * inch, leftMargin=0.75 * inch,
                              topMargin=1.0 * inch, bottomMargin=1.0 * inch) # Adjusted margins # [source: 76]
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        template = PageTemplate(id='main', frames=[frame], onPage=self.on_page)
        doc.addPageTemplates([template])
        elements = []

        # --- Handle Error Case ---
        if isinstance(evaluation_data, dict) and evaluation_data.get("is_error_object"): # [source: 77]
            self.student_name = evaluation_data.get("student_name", "Error Report")
            elements.append(Paragraph("Essay Evaluation Report", self.styles['MainTitle']))
            elements.append(Paragraph(f"Student: {self.student_name}", self.styles['StudentTitle']))
            elements.append(Paragraph("Evaluation Failed", self.styles['ScoreTitle']))
            error_msg = evaluation_data.get('error', 'An unknown error occurred during evaluation.')
            elements.append(Paragraph(f"Error Details: {error_msg}", self.styles['ErrorText']))
            logger.warning(f"Generating PDF report for a failed evaluation: {self.student_name}") # [source: 78]
            doc.build(elements)
            pdf_buffer.seek(0)
            return pdf_buffer

        # --- Handle Successful Evaluation (EssayEvaluation model) ---
        if not isinstance(evaluation_data, EssayEvaluation): # [source: 78]
             logger.error(f"Invalid data type passed to PDFReport.create: {type(evaluation_data)}. Expected EssayEvaluation or error dict.") # [source: 79]
             # Create a minimal error PDF
             self.student_name = "Generation Error"
             elements.append(Paragraph("Report Generation Error", self.styles['MainTitle']))
             elements.append(Paragraph("Could not generate report due to invalid input data.", self.styles['ErrorText']))
             doc.build(elements)
             pdf_buffer.seek(0) # [source: 80]
             return pdf_buffer

        # We have a valid EssayEvaluation model
        evaluation = evaluation_data # [source: 80]
        self.student_name = evaluation.student_name # Set for header/footer

        # Calculate max score total from the model data
        max_score_total = sum(c.max_score for c in evaluation.criteria)
        if max_score_total <= 0 and evaluation.criteria: # Fallback if max_scores are zero/missing # [source: 81]
            max_score_total = sum(10 for _ in evaluation.criteria) # Assume 10 if not specified

        # Header
        elements.append(Paragraph("Essay Evaluation Report", self.styles['MainTitle'])) # [source: 81]
        elements.append(Paragraph(f"Student: {self.student_name}", self.styles['StudentTitle']))
        score_color = self._get_score_color(evaluation.overall_score, max_score_total)
        score_text = f"Overall Score: <font color='{score_color.hexval()}'><b>{evaluation.overall_score:.1f}</b></font>"
        if max_score_total > 0:
            score_text += f" / {max_score_total:.1f}" # [source: 82]
        elements.append(Paragraph(score_text, self.styles['ScoreTitle']))

        # Configuration flags (passed in)
        include_criteria = config_flags.get("include_criteria", True) # [source: 82]
        include_highlights = config_flags.get("include_highlights", True)
        include_suggestions = config_flags.get("include_suggestions", True)
        include_mini_lessons = config_flags.get("include_mini_lessons", True)

        # Criteria Breakdown Table
        if include_criteria and evaluation.criteria:
            elements.append(self._create_section_title("Evaluation Breakdown", doc.width)) # [source: 83]
            elements.append(Spacer(1, 0.1 * inch))

            table_data = [[
                Paragraph("Criterion", self.styles['TableHeader']),
                Paragraph("Score", self.styles['TableHeader']),
                Paragraph("Feedback", self.styles['TableHeader'])
            ]] # [source: 84]
            for crit in evaluation.criteria:
                crit_score_color = self._get_score_color(crit.score, crit.max_score) # [source: 84]
                table_data.append([
                    Paragraph(crit.name, self.styles['TableCellBold']),
                    Paragraph(f"<font color='{crit_score_color.hexval()}'>{crit.score:.1f}</font> / {crit.max_score:.1f}", self.styles['TableCellCenter']),
                    Paragraph(crit.feedback.replace("\n", "<br/>"), self.styles['FeedbackCell']) # Handle newlines in feedback # [source: 85]
                ])
            table = Table(table_data, colWidths=[1.8 * inch, 0.7 * inch, 4.0 * inch]) # [source: 85]
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.ACCENT_COLOR),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), # [source: 86]
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), self.BOLD_FONT),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey), # [source: 87]
                ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]), # Alternating rows
                ('LEFTPADDING', (0, 1), (-1, -1), 6),
                ('RIGHTPADDING', (0, 1), (-1, -1), 6),
                ('TOPPADDING', (0, 1), (-1, -1), 4), # [source: 88]
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        # Highlighted Passages
        if include_highlights and evaluation.highlighted_passages: # [source: 88]
            elements.append(self._create_section_title("Highlighted Passages / Examples", doc.width)) # [source: 89]
            elements.append(Spacer(1, 0.1 * inch))
            for i, passage in enumerate(evaluation.highlighted_passages):
                 # Create a table for each passage for better bordering/spacing
                 passage_elements = [
                     Paragraph(f"<b>Passage {i+1}:</b> \"{passage.text}\"", self.styles['HighlightText']), # [source: 90]
                      Paragraph(f"<b>Issue/Note:</b> {passage.issue}", self.styles['HighlightIssue']),
                      Paragraph(f"<b>Suggestion:</b> {passage.suggestion}", self.styles['HighlightSuggestion'])
                 ]
                 if passage.example_revision:
                     passage_elements.append(Paragraph(f"<b>Example Revision:</b> {passage.example_revision}", self.styles['HighlightSuggestion'])) # Reuse style? # [source: 91]
                 highlight_table = Table([ [p] for p in passage_elements ], colWidths=[doc.width - 0.2*inch]) # Inner table slightly narrower # [source: 92]
                 highlight_table.setStyle(TableStyle([
                      ('BOX', (0,0), (-1,-1), 0.5, self.ACCENT_COLOR),
                      ('LEFTPADDING', (0,0), (-1,-1), 8),
                      ('RIGHTPADDING', (0,0), (-1,-1), 8), # [source: 93]
                      ('TOPPADDING', (0,0), (-1,-1), 4),
                      ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                      # ('INNERGRID', (0,0), (-1,-1), 0.25, colors.lightgrey) # Optional inner grid
                 ])) # [source: 94]
                 elements.append(highlight_table)
                 elements.append(Spacer(1, 0.15 * inch))


        # General Suggestions
        if include_suggestions and evaluation.suggestions: # [source: 94]
            elements.append(self._create_section_title("General Suggestions for Improvement", doc.width))
            elements.append(Spacer(1, 0.1 * inch))
            for sug in evaluation.suggestions: # [source: 95]
                if isinstance(sug, str) and sug.strip():
                    elements.append(Paragraph(sug, self.styles['SuggestionItem'], bulletText='•')) # Using standard bullet # [source: 95]
            elements.append(Spacer(1, 0.2 * inch))

        # Mini Lessons
        if include_mini_lessons and evaluation.mini_lessons: # [source: 95]
            elements.append(self._create_section_title("Key Mini-Lessons / Focus Areas", doc.width)) # [source: 96]
            elements.append(Spacer(1, 0.1 * inch))
            for lesson in evaluation.mini_lessons:
                if isinstance(lesson, str) and lesson.strip():
                    # Clean potential prefixes if Gemini adds them
                    clean_lesson = re.sub(r"^\s*(?:Mini-Lesson|Key Lesson|Focus Area)\s*[:\-]\s*", "", lesson, flags=re.IGNORECASE).strip() # [source: 97]
                    elements.append(Paragraph(clean_lesson, self.styles['MiniLessonItem'], bulletText='💡')) # Lightbulb bullet # [source: 97]
            elements.append(Spacer(1, 0.2 * inch))


        # Build the PDF
        try:
            doc.build(elements)
            pdf_buffer.seek(0)
            logger.info(f"Successfully created PDF report for {self.student_name}.") # [source: 98]
            return pdf_buffer
        except Exception as build_err:
             logger.error(f"Error building PDF for {self.student_name}: {build_err}\n{traceback.format_exc()}") # [source: 98]
             # Return a minimal error PDF if build fails
             pdf_buffer = BytesIO()
             doc = BaseDocTemplate(pdf_buffer, pagesize=letter) # [source: 99]
             frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='error_frame')
             template = PageTemplate(id='error_page', frames=[frame])
             doc.addPageTemplates([template])
             error_elements = [
                 Paragraph("PDF Generation Error", self.styles['MainTitle']), # [source: 99]
                 Paragraph(f"Student: {self.student_name}", self.styles['StudentTitle']), # [source: 100]
                 Paragraph(f"An error occurred while building the PDF report: {build_err}", self.styles['ErrorText'])
             ]
             doc.build(error_elements)
             pdf_buffer.seek(0)
             return pdf_buffer

# --- Rubric Management Helper ---

def get_rubric_by_id(rubric_id: str) -> tuple[Optional[str], Optional[str]]: # [source: 100]
    """Loads rubric content and name from a file in the 'rubrics' directory.""" # [source: 101]
    if not re.match(r'^[\w\-]+$', rubric_id):
        logger.warning(f"Invalid rubric_id format attempted: {rubric_id}") # [source: 101]
        return None, None

    filepath = os.path.join("rubrics", f"{rubric_id}.txt")
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            content = f.read()
        lines = content.strip().split('\n', 1)
        # Simple assumption: first non-empty line is name, rest is content # [source: 102]
        rubric_name = None
        rubric_content = None
        if lines:
             first_line = lines[0].strip()
             # Basic check if first line looks like a title (less than 100 chars, doesn't contain typical rubric lines)
             if len(first_line) < 100 and not re.search(r'\(\s*\d+\s*-\s*\d+\s*\)', first_line): # [source: 103]
                  rubric_name = first_line
                  rubric_content = lines[1].strip() if len(lines) > 1 else None
             else: # Assume no separate title line # [source: 103]
                  rubric_name = f"Rubric {rubric_id}" # Default name
                  rubric_content = content.strip() # [source: 104]

        if not rubric_content:
             logger.warning(f"Rubric file '{filepath}' content is effectively empty.") # [source: 104]
             return None, rubric_name # Return name even if content is missing/empty

        logger.info(f"Loaded rubric '{rubric_name}' from ID: {rubric_id}")
        return rubric_content, rubric_name

    except FileNotFoundError:
        logger.warning(f"Rubric file not found for ID: {rubric_id} at path: {filepath}") # [source: 105]
        return None, None
    except Exception as e:
        logger.error(f"Error reading rubric file {filepath}: {e}") # [source: 105]
        return None, None

# --- API Endpoints ---

@app.post("/evaluate/", tags=["Evaluation"], response_model=Dict[str, Any]) # Define a response model later if needed
async def evaluate_essay_endpoint(
    form_data: EvaluationRequestForm = Depends(), # Use Depends for form data model
    essay: UploadFile = File(...), # Essay file is required
    rubric_file: Optional[UploadFile] = File(None) # Optional rubric file upload # [source: 106]
):
    """
    Endpoint to evaluate one or more essays from an uploaded file (DOCX, PDF, TXT). # [source: 106]
    Rubric can be provided via text (form_data.rubric_text), # [source: 107]
    file upload (rubric_file), or ID (form_data.rubric_id). # [source: 107]
    A 'generosity' parameter ('strict', 'standard', 'generous') adjusts evaluation strictness. # [source: 108]
    Uses Google Gemini for evaluation based on the selected rubric. # [source: 108]
    Returns evaluation status and details, including a session ID for downloading reports. # [source: 109]
    """ # [source: 110]
    server_api_key = os.getenv('GEMINI_API_KEY')
    effective_api_key = form_data.api_key or server_api_key

    if not effective_api_key:
        logger.error("API key is not configured on the server and was not provided in the request.")
        raise HTTPException(status_code=500, detail="AI API key is not configured.")

    # --- Determine the Rubric ---
    effective_rubric_text = DEFAULT_RUBRIC
    rubric_source = "default"

    if form_data.rubric_text:
        effective_rubric_text = form_data.rubric_text
        rubric_source = "text input" # [source: 111]
    elif rubric_file:
        try:
            rubric_file_content = await extract_text(rubric_file) # [source: 111]
            if rubric_file_content.strip():
                effective_rubric_text = rubric_file_content
                rubric_source = f"file upload ({rubric_file.filename})"
            else:
                logger.warning(f"Uploaded rubric file '{rubric_file.filename}' extracted empty text. Falling back to default.") # [source: 112]
                 # effective_rubric_text remains DEFAULT_RUBRIC
                rubric_source = "default (uploaded file empty)" # [source: 112]
        except ValueError as e:
             logger.warning(f"Could not extract text from uploaded rubric file: {e}. Falling back to default.") # [source: 112]
             rubric_source = "default (upload extraction failed)" # [source: 113]
    elif form_data.rubric_id:
        loaded_rubric_content, loaded_rubric_name = get_rubric_by_id(form_data.rubric_id) # [source: 113]
        if loaded_rubric_content:
            effective_rubric_text = loaded_rubric_content
            rubric_source = f"ID '{form_data.rubric_id}' ({loaded_rubric_name or 'Unnamed'})"
        else:
            logger.warning(f"Could not load rubric for ID '{form_data.rubric_id}'. Falling back to default.") # [source: 114]
            rubric_source = f"default (ID '{form_data.rubric_id}' not found or invalid)"

    logger.info(f"Using rubric from: {rubric_source}") # [source: 114]
    logger.info(f"Evaluation generosity level: {form_data.generosity}") # Log generosity

    # --- Extract Essay Text ---
    try:
        essay_text_content = await extract_text(essay) # [source: 114]
        if not essay_text_content.strip():
            logger.error(f"Uploaded essay file '{essay.filename}' resulted in empty content.")
            raise HTTPException(status_code=400, detail="Essay file is empty or could not be read.") # [source: 115]
    except ValueError as e:
        logger.error(f"Failed to extract text from essay file '{essay.filename}': {e}") # [source: 115]
        raise HTTPException(status_code=400, detail=f"Error processing essay file: {e}")
    except Exception as e:
        logger.error(f"Unexpected error extracting text from '{essay.filename}': {e}\n{traceback.format_exc()}") # [source: 115]
        raise HTTPException(status_code=500, detail="An unexpected error occurred while reading the essay file.")

    # --- Perform Evaluation(s) ---
    try:
        logger.info(f"Form data: {form_data}") # [source: 115]
        # Pass API key, rubric, and generosity level # [source: 116]
        evaluations: List[Union[EssayEvaluation, Dict[str, Any]]] = await evaluate_essays(
            essay_text=essay_text_content,
            rubric_text=effective_rubric_text,
            api_key=effective_api_key,
            generosity=form_data.generosity # --- Pass generosity ---
        )
    except ValueError as e: # Catch errors from evaluate_essay if retry fails
         logger.error(f"Evaluation failed permanently: {e}") # [source: 116]
         raise HTTPException(status_code=500, detail=f"AI evaluation failed: {e}") # [source: 117]
    except Exception as e: # Catch other unexpected errors in evaluate_essays
         logger.error(f"Unexpected error during evaluation process: {e}\n{traceback.format_exc()}") # [source: 117]
         raise HTTPException(status_code=500, detail="An unexpected error occurred during evaluation.")

    if not evaluations:
        logger.warning(f"Evaluation process returned no results for file '{essay.filename}'. This might be due to empty content after splitting.") # [source: 118]
        # Return a specific response instead of 400/500 if it's just no content found
        return {
             "evaluation_status": "empty",
             "message": "No valid essay content found in the uploaded file after processing.", # [source: 118]
             "session_id": None,
             "results": [] # [source: 119]
        }
        # Or, stick with HTTPException:
        # raise HTTPException(status_code=400, detail="No essays could be evaluated from the provided file. Check file content and splitting logic.") # [source: 119]

    # --- Store Results and Prepare Response ---
    session_id = str(uuid.uuid4())
    session_storage_entry: Dict[str, Union[EssayEvaluation, Dict[str, Any]]] = {}
    results_summary = []
    config_flags = form_data.model_dump(include={'include_criteria', 'include_suggestions', 'include_highlights', 'include_mini_lessons'})

    for i, evaluation_result in enumerate(evaluations): # [source: 119]
        is_error = isinstance(evaluation_result, dict) and evaluation_result.get("is_error_object") # [source: 120]
        student_name = "Evaluation Error"
        overall_score = 0
        max_score = 0
        error_message = None

        if not is_error and isinstance(evaluation_result, EssayEvaluation):
             # Successful evaluation
             student_name = evaluation_result.student_name # [source: 120]
             overall_score = evaluation_result.overall_score # [source: 121]
             # Recalculate max_score here for summary consistency
             max_score = sum(c.max_score for c in evaluation_result.criteria if c.max_score > 0) # [source: 121]
             if max_score <= 0 and evaluation_result.criteria: # Fallback if all max_scores are 0
                  max_score = sum(10 for _ in evaluation_result.criteria) # [source: 122]

        elif is_error:
             # Error dictionary
             student_name = evaluation_result.get("student_name", f"Failed_Essay_{i+1}") # [source: 122]
             error_message = evaluation_result.get("error", "Unknown evaluation error")


        # Generate safe filename
        safe_name = re.sub(r'[^\w\-]+', '_', student_name).strip('_') # [source: 122]
        safe_name = safe_name[:50] # Limit length
        filename = f"{safe_name}_Evaluation_{i+1}.pdf" # [source: 123]

        # Store the full result (model or error dict) with config
        session_storage_entry[filename] = {"data": evaluation_result, "config": config_flags} # [source: 123]

        # Prepare summary entry
        summary_entry = {
            "id": i,
            "filename": filename,
            "student_name": student_name,
            "overall_score": overall_score if not is_error else 0, # [source: 124]
            "max_score": max_score if not is_error else 0,
            "error": error_message # Will be None for successful evaluations
        }
        results_summary.append(summary_entry)


    # Store the session data
    evaluation_storage[session_id] = session_storage_entry # [source: 124]
    logger.info(f"Stored {len(evaluations)} evaluation result(s) under session ID: {session_id}")

    # --- Return Response --- # [source: 125]
    response_payload = {
        "evaluation_status": "multiple" if len(evaluations) > 1 else "single",
        "session_id": session_id,
        "count": len(evaluations),
        "results": results_summary
    }

    # Simplify response if only one result
    if len(evaluations) == 1:
        single_result = results_summary[0] # [source: 125]
        response_payload["filename"] = single_result["filename"]
        response_payload["student_name"] = single_result["student_name"] # [source: 126]
        response_payload["overall_score"] = single_result["overall_score"]
        response_payload["max_score"] = single_result["max_score"]
        response_payload["error"] = single_result["error"]
        # Optionally remove the 'results' list for single mode
        # del response_payload["results"] # [source: 126]
        # del response_payload["count"]


    return response_payload


@app.get("/download-report/{session_id}/{filename}", tags=["Download"])
async def download_single_report(session_id: str, filename: str):
    """Downloads a previously generated PDF evaluation report by session ID and filename.""" # [source: 126]
    logger.info(f"Download request received for session '{session_id}', filename '{filename}'") # [source: 127]

    # Basic Input Validation
    if not re.match(r'^[\w\-]+\.pdf$', filename, re.IGNORECASE):
         logger.warning(f"Invalid filename format requested: {filename}") # [source: 127]
         raise HTTPException(status_code=400, detail="Invalid filename format.")

    if not re.match(r'^[a-fA-F0-9\-]+$', session_id):
        logger.warning(f"Invalid session ID format requested: {session_id}") # [source: 127]
        raise HTTPException(status_code=400, detail="Invalid session ID format.")

    # Check storage
    session_data = evaluation_storage.get(session_id)
    if not session_data:
        logger.warning(f"Session ID not found: {session_id}") # [source: 128]
        raise HTTPException(status_code=404, detail="Evaluation session not found or expired.")

    report_info = session_data.get(filename)
    if not report_info:
        logger.warning(f"Filename '{filename}' not found within session '{session_id}'") # [source: 128]
        raise HTTPException(status_code=404, detail="Specific report file not found in this session.")

    evaluation_result_data = report_info.get("data")
    config_flags = report_info.get("config", {}) # Get config used for this specific eval

    if evaluation_result_data is None:
        logger.error(f"Missing 'data' key for report '{filename}' in session '{session_id}'") # [source: 129]
        raise HTTPException(status_code=500, detail="Internal error: Evaluation data missing.")

    # --- Generate PDF ---
    try:
        pdf_generator = PDFReport() # [source: 129]
        # Pass both the evaluation data (model or dict) and the config flags
        pdf_buffer = pdf_generator.create(evaluation_result_data, config_flags)

        # Optional: Clean up the specific entry after successful generation? # [source: 129]
        # Consider a separate cleanup mechanism (e.g., TTL) instead of deleting immediately. # [source: 130]
        # del evaluation_storage[session_id][filename] # [source: 131]
        # if not evaluation_storage[session_id]: # Delete session if empty
        #     del evaluation_storage[session_id]

        logger.info(f"Sending PDF report: {filename}") # [source: 131]
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                # Ensure filename is quoted, handle potential quotes within filename? Unlikely with sanitization. # [source: 132]
                "Content-Disposition": f"attachment; filename=\"{filename}\""
            }
        )
    except Exception as e:
         # Catch potential errors during PDF generation (though .create() now tries to handle them)
         logger.error(f"Unexpected error during PDF generation/download for {filename}: {e}\n{traceback.format_exc()}") # [source: 132]
         raise HTTPException(status_code=500, detail="An unexpected error occurred while generating the report.") # [source: 133]


# --- Rubric Management Endpoints ---

@app.get("/rubrics/", tags=["Rubrics"], response_model=Dict[str, str]) # [source: 133]
async def list_rubrics():
    """Lists the available rubrics (ID and Name) stored on the server."""
    rubrics_dir = "rubrics"
    rubric_files = {}
    try:
        if not os.path.isdir(rubrics_dir):
             logger.warning(f"Rubrics directory '{rubrics_dir}' not found.")
             return {} # Return empty dict if directory doesn't exist # [source: 134]

        for filename in os.listdir(rubrics_dir):
            if filename.endswith(".txt"): # [source: 134]
                rubric_id = filename[:-4] # Remove .txt extension
                _, name = get_rubric_by_id(rubric_id) # Reuse helper to get name
                # Use ID as fallback name if helper returns None for name # [source: 135]
                rubric_files[rubric_id] = name if name else rubric_id
        return rubric_files
    except Exception as e:
        logger.error(f"Error listing rubrics: {e}") # [source: 135]
        raise HTTPException(status_code=500, detail="Could not list available rubrics.")

@app.get("/rubrics/{rubric_id}", tags=["Rubrics"], response_model=Dict[str, Optional[str]])
async def get_rubric_details(rubric_id: str):
    """Gets the content and name of a specific rubric by its ID."""
    content, name = get_rubric_by_id(rubric_id) # [source: 135]
    if content is None and name is None: # Check if get_rubric_by_id indicated not found # [source: 136]
        raise HTTPException(status_code=404, detail=f"Rubric with ID '{rubric_id}' not found.")
    return {"id": rubric_id, "name": name, "content": content} # [source: 136]

@app.get("/default-rubric/", tags=["Rubrics"], response_model=Dict[str, str])
async def get_default_rubric():
    """Returns the default rubric text."""
    return {"name": "Default Academic Rubric", "content": DEFAULT_RUBRIC} # [source: 136]

# TODO: Add endpoints for creating, updating, deleting, generating rubrics if needed.


# --- Main Execution --- # [source: 137]
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1") # Default to localhost for local dev
    port = int(os.getenv("PORT", 8000))
    # Simple way to check for reload flag (e.g., set RELOAD=true in env)
    reload = os.getenv("RELOAD", "false").lower() in ["true", "1", "yes"] # [source: 137]

    log_level = "info" # Or get from env var

    print(f"--- Starting Essay Evaluator API ---")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reloading: {'Enabled' if reload else 'Disabled'}") # [source: 138]
    print(f"Allowed Origins: {origins if origins else '*'}")
    print(f"Log Level: {log_level}")
    print(f"------------------------------------")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level.lower() # Ensure lowercase for uvicorn
    )