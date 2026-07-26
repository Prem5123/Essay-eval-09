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
from typing import Any, Dict, List, Literal, Optional, Union, Awaitable, cast, Coroutine
from itertools import islice
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle # type: ignore
from google import genai # type: ignore
from google.genai import types # type: ignore
import pdfplumber # type: ignore
from docx import Document # type: ignore
from dotenv import load_dotenv # type: ignore
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Response, UploadFile # type: ignore
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from pydantic import BaseModel, Field, HttpUrl, ValidationError, field_validator # type: ignore
from reportlab.lib import colors # type: ignore
from reportlab.lib.enums import TA_CENTER, TA_LEFT # type: ignore
from reportlab.lib.pagesizes import letter # type: ignore
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet # type: ignore
from reportlab.lib.units import inch # type: ignore

# --- Pydantic Models ---

class CriterionEvaluation(BaseModel):
    name: str
    score: float
    max_score: float
    feedback: str

class HighlightedPassage(BaseModel):
    text: str
    issue: str
    suggestion: str
    example_revision: Optional[str] = None

class EssayEvaluation(BaseModel):
    student_name: str = "Unknown Student"
    overall_score: float
    criteria: List[CriterionEvaluation]
    suggestions: List[str]
    highlighted_passages: List[HighlightedPassage]
    mini_lessons: List[str] = Field(..., alias="Mini Lessons")
    essay_text: str = "" # Stores the original essay text for annotated reports
    error: Optional[str] = None

    @field_validator('overall_score')
    @classmethod
    def check_overall_score_consistency(cls, v: float, info: Any):
        if 'criteria' in info.data:
            calculated_score = sum(c.score for c in info.data['criteria'])
            if abs(v - calculated_score) > 0.1:
                logger.warning(f"Provided overall_score ({v}) differs from calculated criteria sum ({calculated_score}) for student '{info.data.get('student_name', 'N/A')}'.")
                return calculated_score
        return v

    @field_validator('criteria')
    @classmethod
    def check_criteria_scores(cls, v: List[CriterionEvaluation]):
        for criterion in v:
            if not (0 <= criterion.score <= criterion.max_score):
                logger.warning(f"Criterion '{criterion.name}' score ({criterion.score}) out of range (0-{criterion.max_score}). Clamping score.")
                criterion.score = max(0.0, min(criterion.score, criterion.max_score))
        return v

class EvaluationRequestForm(BaseModel):
    rubric_text: Optional[str] = None
    rubric_id: Optional[str] = None
    include_criteria: bool = True
    include_suggestions: bool = True
    include_highlights: bool = True
    include_mini_lessons: bool = True
    api_key: Optional[str] = None
    generosity: Literal['strict', 'standard', 'generous'] = 'standard'
    paper_mode: Literal['organization', 'general'] = 'organization'
    pdf_report_preset: Literal['classic', 'academic', 'supportive', 'minimalist'] = 'classic'

# --- Configuration & Setup ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

os.makedirs("uploads", exist_ok=True)
os.makedirs("rubrics", exist_ok=True)

app = FastAPI()

allowed_origins_str = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,https://essay-evaluator-mu.vercel.app")
origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

ALLOWED_TYPES = {
    'application/pdf',
    'text/plain',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
}

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

evaluation_storage: Dict[str, Any] = {}
STORAGE_FILE = "evaluation_storage.json"

def save_storage():
    """Persists the evaluation_storage to a JSON file."""
    try:
        serializable_storage = {}
        for session_id, session_data in evaluation_storage.items():
            serializable_session = {}
            for filename, file_data in session_data.items():
                data = file_data.get("data")
                config = file_data.get("config")
                # Handle Pydantic models
                if isinstance(data, EssayEvaluation):
                    data = data.model_dump(by_alias=True)
                serializable_session[filename] = {"data": data, "config": config}
            serializable_storage[session_id] = serializable_session
        
        with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(serializable_storage, f, indent=2)
        logger.info(f"Storage persisted to {STORAGE_FILE}")
    except Exception as e:
        logger.error(f"Failed to save storage: {e}")

def load_storage():
    """Loads evaluation_storage from the JSON file."""
    global evaluation_storage
    if not os.path.exists(STORAGE_FILE):
        return
    
    try:
        with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        
        reconstructed_storage = {}
        for session_id, session_data in loaded_data.items():
            reconstructed_session = {}
            for filename, file_data in session_data.items():
                data = file_data.get("data")
                config = file_data.get("config")
                
                # Check if data looks like an EssayEvaluation (has 'criteria' list)
                # and is not an error object
                if isinstance(data, dict) and not data.get("is_error_object") and "criteria" in data:
                    try:
                        data = EssayEvaluation.model_validate(data)
                    except ValidationError as ve:
                        logger.warning(f"Failed to reconstruct EssayEvaluation for {filename}: {ve}")
                
                reconstructed_session[filename] = {"data": data, "config": config}
            reconstructed_storage[session_id] = reconstructed_session
            
        evaluation_storage = reconstructed_storage
        logger.info(f"Loaded storage from {STORAGE_FILE} with {len(evaluation_storage)} sessions.")
    except Exception as e:
        logger.error(f"Failed to load storage: {e}")

# Load storage on startup
load_storage()

# --- Essay Processing Functions ---

async def extract_text(file: UploadFile) -> str:
    logger.info(f"Extracting text from file: '{file.filename}' (Type: {file.content_type})")
    content: bytes = await file.read()
    if not content:
        logger.warning(f"File '{file.filename}' is empty.")
        raise ValueError(f"Cannot read an empty file: '{file.filename}'.")

    filename = file.filename.lower() if file.filename else ""
    content_type = file.content_type

    try:
        if content_type == 'text/plain' or filename.endswith('.txt'):
            try:
                return content.decode('utf-8')
            except UnicodeDecodeError:
                logger.warning(f"UTF-8 decoding failed for '{file.filename}', trying latin-1.")
                return content.decode('latin-1')
        elif content_type == 'application/pdf' or filename.endswith('.pdf'):
            with pdfplumber.open(BytesIO(content)) as pdf:
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
                except Exception as docx_err:
                    logger.error(f"Error parsing DOCX file '{file.filename}': {docx_err}")
                    raise ValueError(f"Failed to parse DOCX file '{file.filename}'.")
        else:
            logger.warning(f"Unsupported file format received: {content_type} for file '{filename}'")
            raise ValueError(f"Unsupported file format: {content_type}")
    except Exception as e:
        logger.error(f"Error extracting text from '{file.filename}': {str(e)}\n{traceback.format_exc()}")
        raise ValueError(f"Failed to extract text from '{file.filename}'. Ensure the file is not corrupted or password-protected.")

# --- Helper functions for strict environment slicing ---
def safe_slice_str(s: str, end: Optional[int] = None, start: int = 0) -> str:
    if end is None:
         return s[start:] # type: ignore
    return s[start:end]  # type: ignore

def safe_slice_list(l: List[Any], end: Optional[int] = None, start: int = 0) -> List[Any]:
    if end is None:
        return l[start:] # type: ignore
    return l[start:end]  # type: ignore

def extract_author_name(text: str) -> str:
    """Extract author name(s) from academic papers (LaTeX, IEEE, ACM, generic)."""
    # Check first ~40 lines where author info typically appears
    all_lines: List[str] = text.split('\n')
    header_lines_list: List[str] = safe_slice_list(all_lines, 40) # type: ignore
    header_lines = "\n".join(header_lines_list)

    # 1) LaTeX \author{...} blocks (handles multiline)
    latex_match = re.search(
        r'\\author\s*\{([^}]+)\}',
        safe_slice_str(text, 3000),  # search deeper for LaTeX commands
        re.DOTALL
    )
    if latex_match:
        raw = latex_match.group(1)
        # Strip LaTeX commands like \textbf{}, \textsuperscript{}, \inst{}, \thanks{}
        cleaned = re.sub(r'\\(?:textbf|textsuperscript|inst|thanks|affiliation|email|orcidID|and)\s*\{[^}]*\}', '', raw)
        cleaned = re.sub(r'\\\\', ',', cleaned)  # line breaks → commas
        cleaned = re.sub(r'\\and\b', ',', cleaned)  # \and → comma
        cleaned = re.sub(r'\\[a-zA-Z]+', '', cleaned)  # remaining commands
        cleaned = re.sub(r'[{}\\]', '', cleaned)  # braces
        # Extract names (sequences of capitalized words)
        names = [n.strip() for n in re.split(r'[,;\n]+', cleaned) if n.strip()]
        valid_names = [n for n in names if re.match(r'^[A-Z][a-z]', n) and len(n) > 2]
        if valid_names:
            author = ", ".join(safe_slice_list(valid_names, 4))  # cap at 4 authors # type: ignore
            if len(valid_names) > 4:
                author += " et al."
            logger.info(f"Extracted author(s) from LaTeX: {author}")
            return author

    # 2) Explicit "Author(s):" / "By:" header lines
    explicit_patterns = [
        r"^\s*(?:authors?|written\s+by|by)\s*[:—\-]\s*(.+)$",
    ]
    for pattern in explicit_patterns:
        m = re.search(pattern, header_lines, re.IGNORECASE | re.MULTILINE)
        if m:
            name = m.group(1).strip().rstrip('.')
            if name.lower() not in ['author', 'authors', 'name', ''] and len(name) > 2:
                logger.info(f"Extracted author from explicit header: {name}")
                return safe_slice_str(name, 120)  # reasonable length cap # type: ignore

    # 3) Name-like line near the top (line 2-6): a line that looks like
    #    one or more proper names and nothing else (no digits, no long text)
    lines = text.strip().split('\n')

    # Use islice to avoid direct list slicing complaints in strict environments
    for line in islice(lines, 1, 6):  # lines 2-6 (index 1 to 5)
        stripped = line.strip()
        if not stripped or len(stripped) > 100:
            continue
        # Looks like names: 2-6 capitalized words, possibly with commas
        if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}(?:\s*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})*$', stripped):
            if stripped.lower() not in ['abstract', 'introduction', 'references', 'acknowledgments']:
                logger.info(f"Extracted author from byline: {stripped}")
                return stripped

    logger.warning("Could not extract author name from paper.")
    return "Unknown Author"

def split_essays(text: str, paper_mode: str = 'organization') -> List[str]:
    if paper_mode == 'general':
        logger.info("General paper mode: treating entire document as single paper (no splitting).")
        stripped = text.strip()
        return [stripped] if stripped else []

    logger.info("Organization mode: attempting to split text into multiple essays.")
    patterns = [
        r"^\s*(?:student\s+)?name\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
        r"^\s*student\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
    ]

    all_matches: List[tuple[int, str]] = []
    for pattern in patterns:
        matches = list(re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE))
        all_matches.extend([(m.start(), m.group(1).strip()) for m in matches])

    all_matches.sort(key=lambda x: x[0])

    essays = []
    last_pos = 0

    if not all_matches:
        logger.info("No name patterns found. Trying to split by significant whitespace.")
        chunks = re.split(r'\n{4,}', text.strip())
        potential_essays = [chunk.strip() for chunk in chunks if len(chunk.strip()) > 300]
        if len(potential_essays) > 1:
            logger.info(f"Split into {len(potential_essays)} potential essays based on whitespace.")
            return potential_essays
        else:
            logger.info("Could not split by whitespace or only one chunk found.")
            logger.info("Treating as a single essay.")
            return [text.strip()] if text.strip() else []

    logger.info(f"Found {len(all_matches)} potential essay start points based on name patterns.")
    for i, (start_pos, name) in enumerate(all_matches):
        segment = text[last_pos:start_pos].strip()
        if segment and len(segment) > 100:
            if i == 0 and len(segment) > 300:
                essays.append(segment)
            elif i > 0:
                essays.append(segment)
        essay_content = ""
        if i == len(all_matches) - 1:
            essay_content = safe_slice_str(text, start=start_pos).strip()
            last_pos = start_pos
        else:
            next_match = all_matches[i + 1]
            next_start_pos = next_match[0]
            essay_content = safe_slice_str(text, start=start_pos, end=next_start_pos).strip()
            last_pos = next_start_pos
        
        if essay_content and len(essay_content) > 200:
            essays.append(essay_content)

    final_essays = [essay for essay in essays if len(re.sub(r'\s+', '', essay)) > 250]
    if not final_essays:
        logger.warning("Splitting logic resulted in no valid essay content.")
        logger.warning("Returning original text if non-empty.")
        original_stripped = text.strip()
        return [original_stripped] if len(original_stripped) > 250 else []
    logger.info(f"Final count after splitting and filtering: {len(final_essays)} essays.")
    return final_essays

async def evaluate_essays(
    essay_text: str,
    rubric_text: Optional[str],
    api_key: str,
    generosity: Literal['strict', 'standard', 'generous'],
    paper_mode: Literal['organization', 'general'] = 'organization',
    pdf_report_preset: str = 'classic'
) -> List[Union[EssayEvaluation, Dict[str, Any]]]:
    essays = split_essays(essay_text, paper_mode=paper_mode)
    logger.info(f"Attempting to evaluate {len(essays)} detected essay(s).")

    if not essays:
        logger.warning("Splitting resulted in zero essays.")
        return []

    results: List[Union[EssayEvaluation, Dict[str, Any]]] = []
    base_delay = 1.5
    max_delay_increment = 1.0

    tasks: List[Awaitable[Union[EssayEvaluation, Dict[str, Any]]]] = []
    for i, essay_content in enumerate(essays):
        if not essay_content or not essay_content.strip():
            logger.warning(f"Skipping empty essay chunk at index {i}.")
            continue
        task = asyncio.create_task(cast(Coroutine[Any, Any, Union[EssayEvaluation, Dict[str, Any]]], evaluate_single_essay_with_error_handling(
            essay_content=essay_content,
            rubric_text=rubric_text,
            api_key=api_key,
            essay_index=i,
            generosity=generosity,
            paper_mode=paper_mode,
            pdf_report_preset=pdf_report_preset,
            delay=(base_delay + random.uniform(0, max_delay_increment)) if i > 0 else 0
        )))
        tasks.append(task)

    evaluation_results = await asyncio.gather(*tasks)
    results = [res for res in evaluation_results if res is not None]
    logger.info(f"Finished evaluating. Got {len(results)} results (including potential errors) out of {len(essays)} detected essays.")
    return results

async def evaluate_single_essay_with_error_handling(
    essay_content: str,
    rubric_text: Optional[str],
    api_key: str,
    essay_index: int,
    generosity: Literal['strict', 'standard', 'generous'],
    paper_mode: Literal['organization', 'general'] = 'organization',
    pdf_report_preset: str = 'classic',
    delay: float = 0,
) -> Union[EssayEvaluation, Dict[str, Any]]:
    if delay > 0:
        await asyncio.sleep(delay)

    extracted_name = "Unknown Student"
    try:
        logger.info(f"Starting evaluation for essay index {essay_index} (mode: {paper_mode})...")

        if paper_mode == 'general':
            # --- General Paper mode: use robust author extraction ---
            extracted_name = extract_author_name(essay_content)
        else:
            # --- Organization mode: student name from header lines ---
            first_lines = "\n".join(essay_content.split('\n')[:15])
            name_patterns = [
                r"^\s*(?:student\s+)?name\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
                r"^\s*student\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
                r"^\s*author\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
            ]
            for pattern in name_patterns:
                name_match = re.search(pattern, first_lines, re.IGNORECASE | re.MULTILINE)
                if name_match:
                    potential_name = name_match.group(1).strip()
                    if potential_name.lower() not in ["student name", "name", "enter name here", "author"]:
                        extracted_name = potential_name
                        logger.info(f"Extracted student name for essay {essay_index}: {extracted_name}")
                        break

        if extracted_name in ["Unknown Student", "Unknown Author"]:
            logger.warning(f"Could not extract name for essay {essay_index} (mode: {paper_mode}).")

        evaluation = await evaluate_essay(essay_content, rubric_text, api_key, extracted_name, generosity, paper_mode, pdf_report_preset)
        evaluation.essay_text = essay_content # Populate the text for super report
        logger.info(f"Successfully evaluated essay index {essay_index} for '{evaluation.student_name}'.")
        return evaluation

    except (ValueError, ValidationError, Exception) as e:
        error_message = f"Evaluation failed: {str(e)}"
        logger.error(f"Error processing essay index {essay_index} for '{extracted_name}': {error_message}\n{traceback.format_exc()}")
        fallback_name = extracted_name if extracted_name not in ["Unknown Student", "Unknown Author"] else f"Failed_Essay_{essay_index+1}"
        return {
            "student_name": fallback_name,
            "overall_score": 0,
            "criteria": [{"name": "Processing Error", "score": 0, "max_score": 0, "feedback": error_message}],
            "suggestions": ["The AI evaluation could not be completed due to an error."],
            "highlighted_passages": [],
            "Mini Lessons": [],
            "error": error_message,
            "is_error_object": True
        }

async def evaluate_essay(
    essay_text: str,
    rubric_text: Optional[str],
    api_key: str,
    extracted_student_name: str,
    generosity: Literal['strict', 'standard', 'generous'],
    paper_mode: Literal['organization', 'general'] = 'organization',
    pdf_report_preset: str = 'classic'
) -> EssayEvaluation:
    if not api_key:
        logger.error("Gemini API key is missing.")
        raise ValueError("API key not configured.")

    # --- New google-genai SDK: Client-based initialization ---
    client = genai.Client(api_key=api_key)
    MODEL_NAME = "gemini-3.5-flash"

    rubric = rubric_text if rubric_text and rubric_text.strip() else DEFAULT_RUBRIC

    criteria_matches = re.findall(
        r"^\s*(?:\d+\.?\s*)?([A-Za-z &/'\-]+?)\s*\(\s*(\d+)\s*-?\s*(\d+)\s*\)\s*:",
        rubric,
        re.MULTILINE | re.IGNORECASE
    )
    criteria_details = []
    if criteria_matches:
        criteria_details = [(match[0].strip(), int(match[2])) for match in criteria_matches]
    else:
        logger.warning("Could not parse criteria details from rubric. Using default structure assumption in prompt.")
        criteria_details = [("Parsed Criterion 1", 10), ("Parsed Criterion 2", 10), ("Parsed Criterion 3", 10), ("Parsed Criterion 4", 10), ("Parsed Criterion 5", 10)]

    criteria_json_examples = ",\n".join([
        f'    {{"name": "{name}", "score": number (0-{max_score}), "max_score": {max_score}, "feedback": "Specific feedback for {name}."}}'
        for name, max_score in criteria_details
    ]) if criteria_details else ""

    generosity_instruction = ""
    if generosity == 'strict':
        generosity_instruction = """
- **Evaluation Stance**: Apply the rubric criteria with strict adherence. Focus on identifying areas needing improvement and maintain rigorous scoring. Highlight specific errors and inconsistencies clearly. Feedback should be direct and critical where necessary."""
        temperature = 0.1
    elif generosity == 'generous':
        generosity_instruction = """
- **Evaluation Stance**: Apply the rubric criteria with understanding and flexibility. Focus on identifying strengths and potential. Frame feedback constructively and offer encouragement. Be slightly more lenient in scoring, particularly where effort or good ideas are evident but execution is imperfect."""
        temperature = 0.4
    else:
        generosity_instruction = """
- **Evaluation Stance**: Apply the rubric criteria fairly and objectively. Provide balanced feedback addressing both strengths and weaknesses. Score accurately based on the defined standards."""
        temperature = 0.2

    # --- Mode-aware prompt ---
    if paper_mode == 'general':
        doc_label = "academic paper / research article"
        name_label = "Author(s)"
        name_field_comment = "// Author name(s) extracted from the paper"
        suggestions_hint = "Provide 3-5 specific suggestions for improving the paper's clarity, methodology, or argumentation."
        if pdf_report_preset == 'super_annotated':
             highlights_hint = "Identify at least 15-20 specific passages illustrating key strengths or areas for improvement. Be granular and exhaustive."
        else:
             highlights_hint = "Identify 3-5 specific passages illustrating key strengths or areas for improvement in the paper."
        mini_lessons_hint = "Provide 2-3 key insights or takeaways about academic writing, research methodology, or argumentation quality based on this paper."
        short_text_note = "If the paper text is extremely short, appears to be only an abstract, or is incomplete, note this and evaluate only what is available."
    else:
        doc_label = "student essay"
        name_label = "Student Name"
        name_field_comment = "// Use the extracted name provided"
        suggestions_hint = "Provide 3-5 specific, actionable suggestions for overall improvement. Focus on the most impactful areas for the student."
        if pdf_report_preset == 'super_annotated':
             highlights_hint = "Identify at least 15-20 specific sentences or short passages. We need dense annotation. Find distinct opportunities for improvement (grammar, style, clarity, word choice) as well as strengths."
        else:
             highlights_hint = "Identify 3-5 specific sentences or short passages illustrating key strengths or weaknesses, adjusted by Evaluation Stance."
        mini_lessons_hint = "Provide 2-3 'Mini Lessons': actionable tips/concepts based on evaluation. Each lesson should be detailed (50+ words), relevant, use simple language, maybe an analogy."
        short_text_note = "If the essay text is extremely short, nonsensical, or completely off-topic, reflect this in the feedback and assign low scores (possibly 0). Provide minimal suggestions/highlights/lessons if appropriate."

    prompt = f"""
Analyze the following {doc_label} based *strictly* on the provided rubric criteria, adjusting your evaluation strictness based on the 'Evaluation Stance'.
**RUBRIC:**
{rubric}

**{doc_label.upper()} TEXT:**
{essay_text}

---
**EVALUATION TASK:**
Provide a detailed evaluation in JSON format. Follow the structure defined below precisely.
**JSON OUTPUT STRUCTURE:**
{{
  "student_name": "{extracted_student_name}", {name_field_comment}
  "overall_score": number, // REQUIRED: Calculated sum of scores from criteria below
  "criteria": [ // REQUIRED: Array based on RUBRIC
{criteria_json_examples if criteria_json_examples else '    {"name": "Criterion Name from Rubric", "score": number (0-max), "max_score": number (max score for this), "feedback": "Specific feedback..."}'}
  ],
  "suggestions": [ // REQUIRED: List of strings
    "{suggestions_hint}"
  ],
  "highlighted_passages": [ // REQUIRED: List of objects
    // {highlights_hint}
    {{ // Structure for each highlight:
      "text": "Exact short text snippet from the {doc_label}...", // REQUIRED
      "issue": "Brief description (e.g., 'Awkward phrasing', 'Needs evidence', 'Strong point')", // REQUIRED
      "suggestion": "How to improve this specific text.", // REQUIRED
      "example_revision": "Optional: Show a revised version." // OPTIONAL
    }}
  ],
  "Mini Lessons": [ // REQUIRED: List of strings (use this exact key "Mini Lessons")
      // {mini_lessons_hint}
      "Example: Explain a key concept relevant to this {doc_label}..."
  ]
}}

**IMPORTANT INSTRUCTIONS:**
{generosity_instruction}
- Output ONLY the valid JSON object conforming to the structure above.
- Do NOT include markdown formatting (```json ... ```) or any text outside the JSON structure.
- Ensure all required fields are present.
- Calculate `overall_score` accurately by summing the scores given in the `criteria` array.
- Base all feedback, suggestions, highlights, and mini-lessons directly on the provided TEXT and RUBRIC.
- **ANNOTATION DENSITY**: The user wants a "Super Report" full of annotations. Please be very thorough in identifying highlighting passages. Aim for 15-20+ distinct points if possible, covering both major and minor issues.
- {short_text_note}
"""

    max_retries = 3
    last_error = None

    # --- New SDK: Safety settings as list of SafetySetting objects ---
    safety_settings = [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
    ]

    # --- New SDK: Unified GenerateContentConfig ---
    generation_config = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json",
        safety_settings=safety_settings,
    )

    for attempt in range(max_retries):
        try:
            logger.info(f"Sending request to Gemini API ({MODEL_NAME}) for '{extracted_student_name}' (Attempt {attempt + 1}/{max_retries}, Generosity: {generosity})...")

            # New SDK uses synchronous client.models.generate_content;
            # wrap in asyncio.to_thread to keep the endpoint non-blocking
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=MODEL_NAME,
                contents=prompt,
                config=generation_config,
            )

            if not response.candidates:
                block_reason = getattr(response, 'prompt_feedback', None)
                logger.error(f"Gemini API call failed for '{extracted_student_name}': No candidates returned.")
                logger.error(f"Prompt feedback: {block_reason}")
                raise ValueError(f"API response blocked or empty. Feedback: {block_reason}")

            response_text = response.text

            logger.info(f"Attempting to parse API response for '{extracted_student_name}' using Pydantic model.")
            cleaned_response = re.sub(r'^```json\s*|\s*```$', '', response_text.strip(), flags=re.MULTILINE | re.DOTALL).strip()

            try:
                raw_result_dict = json.loads(cleaned_response)
            except json.JSONDecodeError as json_err:
                logger.error(f"Failed to decode JSON response on attempt {attempt + 1} for '{extracted_student_name}': {json_err}")
                logger.debug(f"Raw response causing JSON error:\n---\n{cleaned_response[:1000]}...\n---")
                last_error = json_err
                continue

            validated_evaluation = EssayEvaluation.model_validate(raw_result_dict)

            if validated_evaluation.student_name in ["Unknown Student", "Student Name", ""] and extracted_student_name != "Unknown Student":
                logger.info(f"Overriding model student name ('{validated_evaluation.student_name}') with extracted name ('{extracted_student_name}').")
                validated_evaluation.student_name = extracted_student_name
            elif not validated_evaluation.student_name:
                validated_evaluation.student_name = extracted_student_name if extracted_student_name != "Unknown Student" else f"Student_{uuid.uuid4().hex[:6]}"

            logger.info(f"Successfully parsed and validated API response for student: {validated_evaluation.student_name}")
            return validated_evaluation

        except ValidationError as pydantic_err:
            logger.error(f"Pydantic validation failed on attempt {attempt + 1} for '{extracted_student_name}': {pydantic_err}")
            logger.debug(f"Data causing validation error:\n---\n{raw_result_dict}\n---")
            last_error = pydantic_err
        except ValueError as ve:
            logger.error(f"ValueError during API call or processing for '{extracted_student_name}' on attempt {attempt + 1}: {ve}", exc_info=True)
            last_error = ve
        except Exception as e:
            logger.error(f"Unexpected error during API call/parsing for '{extracted_student_name}' on attempt {attempt + 1}: {str(e)}\n{traceback.format_exc()}")
            last_error = e

        if attempt < max_retries - 1:
            wait_time = (2 ** attempt) * 1.5 + random.uniform(0, 1)
            logger.info(f"Retrying evaluation for '{extracted_student_name}' in {wait_time:.2f} seconds...")
            await asyncio.sleep(wait_time)

    logger.error(f"Failed to evaluate essay for '{extracted_student_name}' after {max_retries} attempts.")
    raise ValueError(f"Failed to get valid evaluation for '{extracted_student_name}' after {max_retries} attempts. Last error: {str(last_error)}")

# --- PDF Report Generation Class ---

class PDFReport:
    HEADER_COLOR = colors.HexColor('#4c1d95')
    ACCENT_COLOR = colors.HexColor('#7c3aed')
    LIGHT_BG = colors.HexColor('#f0e7ff')
    SUCCESS_COLOR = colors.HexColor('#059669')
    WARNING_COLOR = colors.HexColor('#d97706')
    DANGER_COLOR = colors.HexColor('#dc2626')
    TEAL_COLOR = colors.HexColor('#0d9488')
    TEAL_COLOR = colors.HexColor('#0d9488')
    HIGHLIGHT_COLOR = colors.HexColor('#fef08a')
    HIGHLIGHT_GOOD = colors.HexColor('#bbf7d0') # Light green
    HIGHLIGHT_BAD = colors.HexColor('#fecaca') # Light red/pink
    TEXT_COLOR = colors.HexColor('#1e293b')
    FONT_NAME = 'Helvetica'
    BOLD_FONT = 'Helvetica-Bold'

    def __init__(self):
        self.styles = getSampleStyleSheet()
        # Initialize default colors/fonts to avoid linter errors before _configure_styles is called
        self.header_color = colors.HexColor('#4c1d95')
        self.accent_color = colors.HexColor('#7c3aed')
        self.text_color = colors.HexColor('#1e293b')
        self.font_name = 'Helvetica'
        self.bold_font = 'Helvetica-Bold'
        self.bg_color = colors.HexColor('#f0e7ff')
        
        # Custom styles will be created per-report based on preset
        self.student_name: str = "Unknown Student"

    def _configure_styles(self, preset: str, custom_accent_color: Optional[str] = None):
        """Configures the report styles based on the selected preset."""
        self.styles = getSampleStyleSheet() # Reset styles
        
        # Default / Classic Colors
        header_color = colors.HexColor('#4c1d95')
        accent_color = colors.HexColor('#7c3aed')
        text_color = colors.HexColor('#1e293b')
        font_name = 'Helvetica'
        bold_font = 'Helvetica-Bold'
        bg_color = colors.HexColor('#f0e7ff')
        
        if preset == 'academic':
            header_color = colors.black
            accent_color = colors.black
            text_color = colors.black
            font_name = 'Times-Roman'
            bold_font = 'Times-Bold'
            bg_color = colors.white
        elif preset == 'supportive':
            header_color = colors.HexColor('#047857') # Green
            accent_color = colors.HexColor('#059669')
            text_color = colors.HexColor('#374151')
            font_name = 'Helvetica'
            bold_font = 'Helvetica-Bold'
            bg_color = colors.HexColor('#ecfdf5')
        elif preset == 'minimalist':
            header_color = colors.black
            accent_color = colors.darkgrey
            text_color = colors.black
            font_name = 'Courier'
            bold_font = 'Courier-Bold'
            bg_color = colors.white

        # Override accent color if custom one provided
        if custom_accent_color:
            try:
                accent_color = colors.HexColor(custom_accent_color)
                header_color = accent_color  # Use accent as header too
            except Exception:
                pass  # Keep defaults if invalid hex

        # Update instance vars for usage in methods
        self.header_color = header_color
        self.accent_color = accent_color
        self.text_color = text_color
        self.font_name = font_name
        self.bold_font = bold_font
        self.bg_color = bg_color

        self.styles.add(ParagraphStyle(name='Base', parent=self.styles['Normal'], fontName=font_name, fontSize=10, textColor=text_color, leading=14))
        
        # Title Styles
        if preset == 'academic':
             self.styles.add(ParagraphStyle(name='MainTitle', parent=self.styles['h1'], fontName=bold_font, fontSize=18, spaceAfter=6, alignment=TA_CENTER, textColor=text_color))
             self.styles.add(ParagraphStyle(name='StudentTitle', parent=self.styles['h2'], fontName=font_name, fontSize=12, spaceAfter=2, alignment=TA_CENTER, textColor=text_color))
             self.styles.add(ParagraphStyle(name='ScoreTitle', parent=self.styles['h3'], fontName=bold_font, fontSize=12, spaceAfter=12, alignment=TA_CENTER, textColor=text_color))
             self.styles.add(ParagraphStyle(name='SectionTitle', parent=self.styles['h3'], fontName=bold_font, fontSize=12, textColor=text_color, borderPadding=0))
        elif preset == 'minimalist':
             self.styles.add(ParagraphStyle(name='MainTitle', parent=self.styles['h1'], fontName=bold_font, fontSize=20, spaceAfter=12, alignment=TA_LEFT, textColor=text_color))
             self.styles.add(ParagraphStyle(name='StudentTitle', parent=self.styles['h2'], fontName=font_name, fontSize=14, spaceAfter=6, alignment=TA_LEFT, textColor=text_color))
             self.styles.add(ParagraphStyle(name='ScoreTitle', parent=self.styles['h3'], fontName=bold_font, fontSize=12, spaceAfter=18, alignment=TA_LEFT, textColor=text_color))
             self.styles.add(ParagraphStyle(name='SectionTitle', parent=self.styles['h3'], fontName=bold_font, fontSize=14, textColor=text_color))
        else: # Classic & Supportive
             self.styles.add(ParagraphStyle(name='MainTitle', parent=self.styles['h1'], fontName=bold_font, fontSize=24, spaceAfter=12, alignment=TA_CENTER, textColor=accent_color))
             self.styles.add(ParagraphStyle(name='StudentTitle', parent=self.styles['h2'], fontName=font_name, fontSize=14, spaceAfter=6, alignment=TA_CENTER, textColor=header_color))
             self.styles.add(ParagraphStyle(name='ScoreTitle', parent=self.styles['h3'], fontName=bold_font, fontSize=12, spaceAfter=18, alignment=TA_CENTER, textColor=text_color))
             self.styles.add(ParagraphStyle(name='SectionTitle', parent=self.styles['h3'], fontName=bold_font, fontSize=14, textColor=header_color))

        # Common Styles
        self.styles.add(ParagraphStyle(name='TableHeader', fontName=bold_font, alignment=TA_CENTER, textColor=colors.white if preset != 'minimalist' and preset != 'academic' else colors.black))
        self.styles.add(ParagraphStyle(name='TableCell', parent=self.styles['Base'], alignment=TA_LEFT, leading=12))
        self.styles.add(ParagraphStyle(name='TableCellBold', parent=self.styles['TableCell'], fontName=bold_font))
        self.styles.add(ParagraphStyle(name='TableCellCenter', parent=self.styles['TableCell'], alignment=TA_CENTER))
        self.styles.add(ParagraphStyle(name='FeedbackCell', parent=self.styles['TableCell'], fontSize=9))
        self.styles.add(ParagraphStyle(name='SuggestionItem', parent=self.styles['Base'], leftIndent=18, bulletIndent=0, spaceBefore=3, bulletFontName=bold_font, bulletFontSize=10, bulletColor=accent_color))
        self.styles.add(ParagraphStyle(name='MiniLessonItem', parent=self.styles['Base'], leftIndent=18, bulletIndent=0, spaceBefore=3, bulletFontName=bold_font, bulletFontSize=10, bulletColor=colors.HexColor('#0d9488') if preset == 'classic' else accent_color))
        self.styles.add(ParagraphStyle(name='HighlightText', parent=self.styles['Base'], backColor=colors.HexColor('#fef08a') if preset != 'academic' and preset != 'minimalist' else colors.white, borderPadding=(2, 4)))
        self.styles.add(ParagraphStyle(name='HighlightIssue', parent=self.styles['Base'], leftIndent=10, textColor=colors.HexColor('#dc2626') if preset != 'minimalist' else colors.black, fontName=bold_font, spaceBefore=2))
        self.styles.add(ParagraphStyle(name='HighlightSuggestion', parent=self.styles['Base'], leftIndent=10, textColor=colors.HexColor('#059669') if preset != 'minimalist' else colors.black, spaceBefore=1))
        self.styles.add(ParagraphStyle(name='ErrorText', parent=self.styles['Base'], textColor=colors.red, fontName=bold_font, alignment=TA_CENTER, spaceBefore=12, fontSize=12))

    def on_page(self, canvas, doc):
        canvas.saveState()
        # Draw header bar only for Classic/Supportive
        if hasattr(self, 'header_color') and self.header_color not in [colors.black, colors.white]:
             # Header removed as per request
             pass
        
        canvas.setFont(self.font_name, 8)
        canvas.setFillColor(self.text_color)
        # canvas.drawString(doc.leftMargin + 0.1 * inch, doc.height + doc.topMargin - 0.25 * inch, f"Student: {self.student_name}")
        canvas.drawString(doc.leftMargin + doc.width - 0.5 * inch, doc.bottomMargin - 0.25 * inch, f"Page {doc.page}")
        canvas.restoreState()

    def _get_score_color(self, score: float, max_score: float) -> colors.Color:
        if max_score is None or max_score <= 0:
            return self.TEXT_COLOR
        try:
            percentage = float(score) / float(max_score)
        except (ValueError, TypeError):
            return self.TEXT_COLOR
        if percentage >= 0.8:
            return self.SUCCESS_COLOR
        if percentage >= 0.6:
            return self.ACCENT_COLOR
        if percentage >= 0.4:
            return self.WARNING_COLOR
        return self.DANGER_COLOR

    @staticmethod
    def _get_letter_grade(score: float, max_score: float) -> tuple:
        """Returns (letter_grade, grade_color_hex) based on UAlberta grading scale."""
        if max_score <= 0:
            return ('N/A', '#6b7280')
        pct = (score / max_score) * 100
        if pct >= 95:
            return ('A+', '#059669')
        elif pct >= 90:
            return ('A', '#059669')
        elif pct >= 85:
            return ('A-', '#10b981')
        elif pct >= 80:
            return ('B+', '#34d399')
        elif pct >= 75:
            return ('B', '#6366f1')
        elif pct >= 70:
            return ('B-', '#818cf8')
        elif pct >= 65:
            return ('C+', '#f59e0b')
        elif pct >= 60:
            return ('C', '#d97706')
        elif pct >= 55:
            return ('C-', '#ea580c')
        elif pct >= 50:
            return ('D+', '#ef4444')
        elif pct >= 45:
            return ('D', '#dc2626')
        else:
            return ('F', '#991b1b')

    @staticmethod
    def _is_positive_passage(issue_text: str) -> bool:
        """Determines if a highlight passage is a strength or a weakness."""
        positive_keywords = ['good', 'great', 'strong', 'excellent', 'effective', 'well',
                           'clear', 'vivid', 'insightful', 'strength', 'positive',
                           'impressive', 'compelling', 'solid', 'nice', 'proper',
                           'appropriate', 'commendable', 'notable', 'successful']
        negative_keywords = ['weak', 'error', 'incorrect', 'awkward', 'unclear', 'vague',
                           'needs', 'improve', 'lack', 'missing', 'issue', 'problem',
                           'fix', 'avoid', 'wrong', 'poor', 'confus', 'fragment',
                           'run-on', 'wordy', 'redundant']
        lower = issue_text.lower()
        pos_count = sum(1 for w in positive_keywords if w in lower)
        neg_count = sum(1 for w in negative_keywords if w in lower)
        return pos_count > neg_count

    def _create_section_title(self, title_text: str, doc_width: float, preset: str) -> Table:
        title_para = Paragraph(title_text, self.styles['SectionTitle'])
        section_table = Table([[title_para]], colWidths=[doc_width])
        
        bg_color = self.bg_color # Default for styles
        
        # Style override for the section header box
        t_style = [
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]
        
        if preset == 'academic':
            t_style.append(('LINEBELOW', (0, 0), (-1, -1), 1, colors.black))
        elif preset == 'minimalist':
             t_style.append(('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.grey))
        else:
             t_style.append(('BACKGROUND', (0, 0), (-1, -1), self.bg_color))
        
        if preset == 'academic':
            section_table.spaceBefore = 10
            section_table.spaceAfter = 4
        elif preset == 'minimalist':
            section_table.spaceBefore = 12
            section_table.spaceAfter = 8
        else: # Classic & Supportive
            section_table.spaceBefore = 12
            section_table.spaceAfter = 8

        # Explicitly cast to List[Any] to satisfy linter with heterogeneous list types
        section_table_style = TableStyle(cast(List[Any], t_style))
        section_table.setStyle(section_table_style)
        return section_table

    def _render_annotated_essay(self, doc_width: float, evaluation: EssayEvaluation) -> List[Any]:
        """Renders the full essay text with inline highlights."""
        elements = []
        
        # Style for the essay text
        essay_style = ParagraphStyle(
            name='EssayBody',
            parent=self.styles['Normal'],
            fontName='Times-Roman',
            fontSize=11,
            leading=16,
            textColor=colors.black,
            spaceAfter=12,
            alignment=TA_LEFT
        )

        # 1. Prepare text with annotations
        # We need to find the highlighting passages in the text and wrap them in color tags
        
        essay_text_escaped = evaluation.essay_text
        if not essay_text_escaped:
             elements.append(Paragraph("<i>(Original essay text not available for annotation)</i>", self.styles['Base']))
             return elements

        # Escape existing XML characters to avoid ReportLab markup errors
        # CRITICAL: Do NOT convert \n to <br/> yet. We need to match text across lines first.
        essay_text_escaped = essay_text_escaped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Apply highlights
        # Sort highlights by length descending to prioritize longer phrases
        sorted_passages = sorted(evaluation.highlighted_passages, key=lambda p: len(p.text), reverse=True)
        
        highlight_count = 0
        match_count = 0

        for passage in sorted_passages:
             highlight_count += 1
             # Basic heuristics to classify highlight sentiment
             positive_keywords = ['good', 'great', 'strong', 'excellent', 'effective', 'well', 'clear', 'vivid', 'insightful']
             is_positive = any(word in passage.issue.lower() for word in positive_keywords)
             
             color_hex = self.HIGHLIGHT_GOOD.hexval() if is_positive else self.HIGHLIGHT_BAD.hexval()
             
             # Escape the search text to match the escaped essay text
             clean_search = passage.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             
             # Create a regex pattern that allows for flexible whitespace (space, tab, newline)
             # Escape the search string for regex, then replace literal spaces with [\s]+ to match any whitespace/newlines
             # We use re.escape but need to be careful with spaces.
             pattern_str = re.escape(clean_search)
             # Restore spaces as flexible whitespace matchers
             pattern_str = pattern_str.replace(r"\ ", r"[\s\n]+") 
             
             try:
                 # Find and replace. Use a distinct function to ensure we don't double-replace inside existing tags.
                 # The replacement wraps the *matched content* (\g<0>) in font tags.
                 # This preserves the original newline characters of the document match.
                 new_text, subs_made = re.subn(
                     f"({pattern_str})", 
                     f"<font backColor='{color_hex}'>\g<1></font>", 
                     essay_text_escaped, 
                     flags=re.IGNORECASE
                 )
                 
                 if subs_made > 0:
                     essay_text_escaped = new_text
                     match_count += 1
                 else:
                     logger.warning(f"Could not find exact match for quote: '{passage.text[:30]}...'")
             except Exception as e:
                 logger.error(f"Regex error processing highlight '{passage.text[:20]}...': {e}")

        logger.info(f"Highlighter annotated {match_count}/{highlight_count} passages.")

        # Finally, convert newlines to <br/> for ReportLab display
        # We assume the <font> tags don't interfere with this global replace
        annotated_text = essay_text_escaped.replace("\n", "<br/>")

        elements.append(self._create_section_title("Annotated Essay", doc_width, "super_annotated"))
        elements.append(Spacer(1, 0.1 * inch))
        
        # Render the text
        elements.append(Paragraph(annotated_text, essay_style))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Add a legend
        legend_data = [[
            Paragraph(f"<font backColor='{self.HIGHLIGHT_GOOD.hexval()}'>&nbsp;&nbsp;&nbsp;&nbsp;</font> Strengths / Good Points", self.styles['Base']),
            Paragraph(f"<font backColor='{self.HIGHLIGHT_BAD.hexval()}'>&nbsp;&nbsp;&nbsp;&nbsp;</font> Areas for Improvement", self.styles['Base'])
        ]]
        legend_table = Table(legend_data, colWidths=[doc_width/2, doc_width/2])
        elements.append(legend_table)
        elements.append(Spacer(1, 0.25 * inch))

        return elements

    def create(self, evaluation_data: Union[EssayEvaluation, Dict[str, Any]], config_flags: Dict[str, Any]) -> BytesIO:
        preset = config_flags.get("pdf_report_preset", "classic")
        custom_accent = config_flags.get("accent_color", None)
        self._configure_styles(preset, custom_accent_color=custom_accent)
        
        pdf_buffer = BytesIO()
        doc = BaseDocTemplate(pdf_buffer, pagesize=letter,
                              rightMargin=0.75 * inch, leftMargin=0.75 * inch,
                              topMargin=1.0 * inch, bottomMargin=1.0 * inch)
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        template = PageTemplate(id='main', frames=[frame], onPage=self.on_page)
        doc.addPageTemplates([template])
        elements = []

        if isinstance(evaluation_data, dict) and evaluation_data.get("is_error_object"):
            self.student_name = evaluation_data.get("student_name", "Error Report")
            elements.append(Paragraph("Essay Evaluation Report", self.styles['MainTitle']))
            elements.append(Paragraph(f"Student: {self.student_name}", self.styles['StudentTitle']))
            elements.append(Paragraph("Evaluation Failed", self.styles['ScoreTitle']))
            error_msg = evaluation_data.get('error', 'An unknown error occurred during evaluation.')
            elements.append(Paragraph(f"Error Details: {error_msg}", self.styles['ErrorText']))
            logger.warning(f"Generating PDF report for a failed evaluation: {self.student_name}")
            doc.build(elements)
            pdf_buffer.seek(0)
            return pdf_buffer

        if not isinstance(evaluation_data, EssayEvaluation):
            logger.error(f"Invalid data type passed to PDFReport.create: {type(evaluation_data)}. Expected EssayEvaluation or error dict.")
            self.student_name = "Generation Error"
            elements.append(Paragraph("Report Generation Error", self.styles['MainTitle']))
            elements.append(Paragraph("Could not generate report due to invalid input data.", self.styles['ErrorText']))
            doc.build(elements)
            pdf_buffer.seek(0)
            return pdf_buffer

        evaluation = evaluation_data
        self.student_name = evaluation.student_name

        max_score_total = sum(c.max_score for c in evaluation.criteria)
        if max_score_total <= 0 and evaluation.criteria:
            max_score_total = sum(10 for _ in evaluation.criteria)

        # Special Title for Super Report
        if preset == 'super_annotated':
             self.styles.add(ParagraphStyle(name='SuperTitle', parent=self.styles['h1'], fontName='Helvetica-Bold', fontSize=22, spaceAfter=2, alignment=TA_CENTER, textColor=colors.HexColor('#be185d')))
             elements.append(Paragraph("✨ Essay Super Report ✨", self.styles['SuperTitle']))
        else:
             elements.append(Paragraph("Essay Evaluation Report", self.styles['MainTitle']))
        
        elements.append(Paragraph(f"Student: {self.student_name}", self.styles['StudentTitle']))
        elements.append(Spacer(1, 0.15 * inch))

        # --- Grade Summary Card ---
        score_color = self._get_score_color(evaluation.overall_score, max_score_total)
        letter_grade, grade_color_hex = self._get_letter_grade(evaluation.overall_score, max_score_total)
        pct_val = (evaluation.overall_score / max_score_total * 100) if max_score_total > 0 else 0

        grade_badge_style = ParagraphStyle(
            name='GradeBadge', parent=self.styles['Normal'],
            fontName=self.bold_font, fontSize=28, alignment=TA_CENTER,
            textColor=colors.white, leading=34
        )
        score_display_style = ParagraphStyle(
            name='ScoreDisplay', parent=self.styles['Normal'],
            fontName=self.bold_font, fontSize=14, alignment=TA_CENTER,
            textColor=self.text_color, leading=18
        )
        pct_style = ParagraphStyle(
            name='PctDisplay', parent=self.styles['Normal'],
            fontName=self.font_name, fontSize=10, alignment=TA_CENTER,
            textColor=colors.HexColor('#6b7280'), leading=14
        )

        grade_para = Paragraph(letter_grade, grade_badge_style)
        score_text = f"<font color='{score_color.hexval()}'><b>{evaluation.overall_score:.1f}</b></font>"
        if max_score_total > 0:
            score_text += f" / {max_score_total:.1f}"
        score_para = Paragraph(score_text, score_display_style)
        pct_para = Paragraph(f"{pct_val:.0f}%", pct_style)

        grade_card_data = [[
            grade_para,
            [score_para, Spacer(1, 4), pct_para]
        ]]
        grade_card = Table(grade_card_data, colWidths=[1.2 * inch, 3.0 * inch])
        grade_card_style_cmds = [
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor(grade_color_hex)),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('ROUNDEDCORNERS', [8, 8, 8, 8]),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ]
        grade_card.setStyle(TableStyle(cast(List[Any], grade_card_style_cmds)))
        grade_card.hAlign = 'CENTER'
        elements.append(grade_card)
        elements.append(Spacer(1, 0.3 * inch))

        # --- Thin decorative separator ---
        sep_line = Table([['']], colWidths=[4.5 * inch])
        sep_line.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, self.accent_color),
        ]))
        sep_line.hAlign = 'CENTER'
        elements.append(sep_line)
        elements.append(Spacer(1, 0.25 * inch))

        include_criteria = config_flags.get("include_criteria", True)
        include_highlights = config_flags.get("include_highlights", True)
        include_suggestions = config_flags.get("include_suggestions", True)
        include_mini_lessons = config_flags.get("include_mini_lessons", True)

        # -- SUPER REPORT: Render Annotated Text FIRST --
        if preset == 'super_annotated':
             elements.extend(self._render_annotated_essay(doc.width, evaluation))

        if include_criteria and evaluation.criteria:
            elements.append(self._create_section_title("Evaluation Breakdown", doc.width, preset))
            elements.append(Spacer(1, 0.1 * inch))
            table_data = [[
                Paragraph("Criterion", self.styles['TableHeader']),
                Paragraph("Score", self.styles['TableHeader']),
                Paragraph("Feedback", self.styles['TableHeader'])
            ]]
            for crit in evaluation.criteria:
                crit_score_color = self._get_score_color(crit.score, crit.max_score)
                table_data.append([
                    Paragraph(crit.name, self.styles['TableCellBold']),
                    Paragraph(f"<font color='{crit_score_color.hexval()}'>{crit.score:.1f}</font> / {crit.max_score:.1f}", self.styles['TableCellCenter']),
                    Paragraph(crit.feedback.replace("\n", "<br/>"), self.styles['FeedbackCell'])
                ])
            table = Table(table_data, colWidths=[1.8 * inch, 0.7 * inch, 4.0 * inch])
            
            t_style = [
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), self.bold_font),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 1), (-1, -1), 6),
                ('RIGHTPADDING', (0, 1), (-1, -1), 6),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ]
            
            if preset == 'academic' or preset == 'minimalist':
                t_style.append(('TEXTCOLOR', (0, 0), (-1, 0), colors.black))
                t_style.append(('LINEBELOW', (0, 0), (-1, 0), 1, colors.black))
                t_style.append(('GRID', (0, 0), (-1, -1), 0.5, colors.black if preset=='academic' else colors.grey))
            else:
                t_style.append(('BACKGROUND', (0, 0), (-1, 0), self.accent_color))
                t_style.append(('TEXTCOLOR', (0, 0), (-1, 0), colors.white))
                t_style.append(('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey))
                t_style.append(('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]))

            # Explicitly cast to List[Any] to satisfy linter
            table.setStyle(TableStyle(cast(List[Any], t_style)))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        if include_highlights and evaluation.highlighted_passages:
            elements.append(self._create_section_title("Highlighted Passages / Examples", doc.width, preset))
            elements.append(Spacer(1, 0.1 * inch))
            for i, passage in enumerate(evaluation.highlighted_passages):
                is_positive = self._is_positive_passage(passage.issue)
                tag_label = '✅ Strength' if is_positive else '⚠️ Needs Work'
                tag_color = '#059669' if is_positive else '#dc2626'
                border_color = colors.HexColor('#bbf7d0') if is_positive else colors.HexColor('#fecaca')
                bg_tint = colors.HexColor('#f0fdf4') if is_positive else colors.HexColor('#fef2f2')

                tag_style = ParagraphStyle(
                    name=f'PassageTag{i}', parent=self.styles['Base'],
                    fontName=self.bold_font, fontSize=8, textColor=colors.HexColor(tag_color)
                )
                issue_style = ParagraphStyle(
                    name=f'PassageIssue{i}', parent=self.styles['Base'],
                    leftIndent=10, fontName=self.bold_font, spaceBefore=2,
                    textColor=colors.HexColor(tag_color)
                )

                passage_elements = [
                    Paragraph(f"{tag_label}", tag_style),
                    Paragraph(f"<b>Passage {i+1}:</b> \"{passage.text}\"", self.styles['HighlightText']),
                    Paragraph(f"<b>Note:</b> {passage.issue}", issue_style),
                    Paragraph(f"<b>Suggestion:</b> {passage.suggestion}", self.styles['HighlightSuggestion'])
                ]
                if passage.example_revision:
                    passage_elements.append(Paragraph(f"<b>Example Revision:</b> {passage.example_revision}", self.styles['HighlightSuggestion']))
                highlight_table = Table([[p] for p in passage_elements], colWidths=[doc.width - 0.2 * inch])
                highlight_table.setStyle(TableStyle([
                    ('BOX', (0, 0), (-1, -1), 0.75, border_color),
                    ('BACKGROUND', (0, 0), (-1, -1), bg_tint),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
                elements.append(highlight_table)
                elements.append(Spacer(1, 0.15 * inch))

        if include_suggestions and evaluation.suggestions:
            elements.append(self._create_section_title("General Suggestions for Improvement", doc.width, preset))
            elements.append(Spacer(1, 0.1 * inch))
            for sug in evaluation.suggestions:
                if isinstance(sug, str) and sug.strip():
                    elements.append(Paragraph(sug, self.styles['SuggestionItem'], bulletText='•'))
            elements.append(Spacer(1, 0.2 * inch))

        if include_mini_lessons and evaluation.mini_lessons:
            elements.append(self._create_section_title("Key Mini-Lessons / Focus Areas", doc.width, preset))
            elements.append(Spacer(1, 0.1 * inch))
            for lesson in evaluation.mini_lessons:
                if isinstance(lesson, str) and lesson.strip():
                    clean_lesson = re.sub(r"^\s*(?:Mini-Lesson|Key Lesson|Focus Area)\s*[:\-]\s*", "", lesson, flags=re.IGNORECASE).strip()
                    elements.append(Paragraph(clean_lesson, self.styles['MiniLessonItem'], bulletText='💡'))
            elements.append(Spacer(1, 0.2 * inch))

        try:
            doc.build(elements)
            pdf_buffer.seek(0)
            logger.info(f"Successfully created PDF report for {self.student_name}.")
            return pdf_buffer
        except Exception as build_err:
            logger.error(f"Error building PDF for {self.student_name}: {build_err}\n{traceback.format_exc()}")
            pdf_buffer = BytesIO()
            doc = BaseDocTemplate(pdf_buffer, pagesize=letter)
            frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='error_frame')
            template = PageTemplate(id='error_page', frames=[frame])
            doc.addPageTemplates([template])
            error_elements = [
                Paragraph("PDF Generation Error", self.styles['MainTitle']),
                Paragraph(f"Student: {self.student_name}", self.styles['StudentTitle']),
                Paragraph(f"An error occurred while building the PDF report: {build_err}", self.styles['ErrorText'])
            ]
            doc.build(error_elements)
            pdf_buffer.seek(0)
            return pdf_buffer

# --- Rubric Management Helper ---

def get_rubric_by_id(rubric_id: str) -> tuple[Optional[str], Optional[str]]:
    if not re.match(r'^[\w\-]+$', rubric_id):
        logger.warning(f"Invalid rubric_id format attempted: {rubric_id}")
        return None, None

    filepath = os.path.join("rubrics", f"{rubric_id}.txt")
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            content = f.read()
        lines = content.strip().split('\n', 1)
        rubric_name = None
        rubric_content = None
        if lines:
            first_line = lines[0].strip()
            if len(first_line) < 100 and not re.search(r'\(\s*\d+\s*-\s*\d+\s*\)', first_line):
                rubric_name = first_line
                rubric_content = lines[1].strip() if len(lines) > 1 else None
            else:
                rubric_name = f"Rubric {rubric_id}"
                rubric_content = content.strip()
        if not rubric_content:
            logger.warning(f"Rubric file '{filepath}' content is effectively empty.")
            return None, rubric_name
        logger.info(f"Loaded rubric '{rubric_name}' from ID: {rubric_id}")
        return rubric_content, rubric_name
    except FileNotFoundError:
        logger.warning(f"Rubric file not found for ID: {rubric_id} at path: {filepath}")
        return None, None
    except Exception as e:
        logger.error(f"Error reading rubric file {filepath}: {e}")
        return None, None

# --- API Endpoints ---

@app.post("/evaluate/", tags=["Evaluation"], response_model=Dict[str, Any])
@app.post("/evaluate/", tags=["Evaluation"], response_model=Dict[str, Any])
async def evaluate_essay_endpoint(
    essay: Union[UploadFile, str] = File(None), # Accepts file or string (via some hack? No, UploadFile works for file input)
    # Actually, essay is handled below. But wait, if I use File(None), it might be optional?
    # The original code had: essay: UploadFile = File(...)
    # But my frontend sends 'essay' as a field.
    # Let's check original signature again.
    # Original: essay: UploadFile = File(...)
    # If the frontend sends a string blob, it comes as a file.
    
    # Explicit Form parameters:
    rubric_text: Optional[str] = Form(None),
    rubric_id: Optional[str] = Form(None),
    include_criteria: bool = Form(True),
    include_suggestions: bool = Form(True),
    include_highlights: bool = Form(True),
    include_mini_lessons: bool = Form(True),
    api_key: Optional[str] = Form(None),
    generosity: Literal['strict', 'standard', 'generous'] = Form('standard'),
    paper_mode: Literal['organization', 'general'] = Form('organization'),
    pdf_report_preset: Literal['classic', 'academic', 'supportive', 'minimalist', 'super_annotated'] = Form('classic'),
    accent_color: Optional[str] = Form(None),
    
    rubric_file: Optional[UploadFile] = File(None)
):
    server_api_key = os.getenv('GEMINI_API_KEY')
    effective_api_key = api_key or server_api_key

    if not effective_api_key:
        logger.error("API key is not configured on the server and was not provided in the request.")
        raise HTTPException(status_code=500, detail="AI API key is not configured.")

    effective_rubric_text = DEFAULT_RUBRIC
    rubric_source = "default"
    
    # Debug logging
    logger.info(f"DEBUG: Endpoint received rubric_text: '{rubric_text[:50] if rubric_text else 'None'}'")
    logger.info(f"DEBUG: Endpoint received rubric_file: '{rubric_file.filename if rubric_file else 'None'}'")

    if rubric_text:
        effective_rubric_text = rubric_text
        rubric_source = "text input"
    elif rubric_file:
        try:
            rubric_file_content = await extract_text(rubric_file)
            if rubric_file_content.strip():
                effective_rubric_text = rubric_file_content
                rubric_source = f"file upload ({rubric_file.filename})"
            else:
                logger.warning(f"Uploaded rubric file '{rubric_file.filename}' extracted empty text. Falling back to default.")
                rubric_source = "default (uploaded file empty)"
        except ValueError as e:
            logger.warning(f"Could not extract text from uploaded rubric file: {e}. Falling back to default.")
            rubric_source = "default (upload extraction failed)"
    elif rubric_id:
        rubric_id_str = cast(str, rubric_id)
        loaded_rubric_content, loaded_rubric_name = get_rubric_by_id(rubric_id_str)
        if loaded_rubric_content:
            effective_rubric_text = loaded_rubric_content
            rubric_source = f"library preset ({loaded_rubric_name})"
        else:
            logger.warning(f"Rubric ID '{rubric_id}' not found via API. Using default.")
            rubric_source = "default (ID not found)"

    essay_identifier = "unknown"
    if isinstance(essay, UploadFile) and hasattr(essay, 'filename') and essay.filename:
        essay_identifier = essay.filename
    elif isinstance(essay, str):
        essay_identifier = "pasted_text"

    


    logger.info(f"Using rubric from: {rubric_source}")
    logger.info(f"Evaluation generosity level: {generosity}")
    logger.info(f"Paper mode: {paper_mode}")

    try:
        essay_text_content = await extract_text(essay)
        if not essay_text_content.strip():
            logger.error(f"Essay input '{essay_identifier}' resulted in empty content.")
            raise HTTPException(status_code=400, detail="Essay file is empty or could not be read.")
    except ValueError as e:
        logger.error(f"Failed to extract text from essay '{essay_identifier}': {e}")
        raise HTTPException(status_code=400, detail=f"Error processing essay file: {e}")
    except Exception as e:
        logger.error(f"Unexpected error extracting text from '{essay_identifier}': {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while reading the essay file.")

    try:
        evaluations = await evaluate_essays(
            essay_text=essay_text_content,
            rubric_text=effective_rubric_text,
            api_key=effective_api_key,
            generosity=generosity,
            paper_mode=paper_mode,
            pdf_report_preset=pdf_report_preset
        )
    except ValueError as e:
        logger.error(f"Evaluation failed permanently: {e}")
        raise HTTPException(status_code=500, detail=f"AI evaluation failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during evaluation process: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred during evaluation.")

    if not evaluations:
        logger.warning(f"Evaluation process returned no results for '{essay_identifier}'. This might be due to empty content after splitting.")
        return {
            "evaluation_status": "empty",
            "message": "No valid essay content found in the uploaded file after processing.",
            "session_id": None,
            "results": []
        }

    session_id = str(uuid.uuid4())
    session_storage_entry: Dict[str, Any] = {}
    results_summary = []
    config_flags = {
        'include_criteria': include_criteria,
        'include_suggestions': include_suggestions,
        'include_highlights': include_highlights,
        'include_mini_lessons': include_mini_lessons,
        'pdf_report_preset': pdf_report_preset,
        'accent_color': accent_color if accent_color else None,
        'generosity': generosity,
        'paper_mode': paper_mode
    }

    for i, evaluation_result in enumerate(evaluations):
        is_error = isinstance(evaluation_result, dict) and evaluation_result.get("is_error_object")
        student_name = "Evaluation Error"
        overall_score = 0
        max_score = 0
        error_message = None

        if not is_error and isinstance(evaluation_result, EssayEvaluation):
            student_name = evaluation_result.student_name
            overall_score = evaluation_result.overall_score
            max_score = sum(c.max_score for c in evaluation_result.criteria if c.max_score > 0)
            if max_score <= 0 and evaluation_result.criteria:
                max_score = sum(10 for _ in evaluation_result.criteria)
        elif is_error:
            student_name = evaluation_result.get("student_name", f"Failed_Essay_{i+1}")
            error_message = evaluation_result.get("error", "Unknown evaluation error")

        safe_name = re.sub(r'[^\w\-]+', '_', student_name).strip('_')
        safe_name = safe_name[:50]
        filename = f"{safe_name}_Evaluation_{i+1}.pdf"

        session_storage_entry[filename] = {"data": evaluation_result, "config": config_flags}

        summary_entry = {
            "id": i,
            "filename": filename,
            "student_name": student_name,
            "overall_score": overall_score if not is_error else 0,
            "max_score": max_score if not is_error else 0,
            "error": error_message
        }
        results_summary.append(summary_entry)

    evaluation_storage[session_id] = session_storage_entry
    save_storage()
    logger.info(f"Stored {len(evaluations)} evaluation result(s) under session ID: {session_id}")

    response_payload: Dict[str, Any] = {
        "evaluation_status": "multiple" if len(evaluations) > 1 else "single",
        "session_id": session_id,
        "count": len(evaluations),
        "results": results_summary
    }

    if len(evaluations) == 1:
        single_result = results_summary[0]
        response_payload["filename"] = single_result["filename"]
        response_payload["student_name"] = single_result["student_name"]
        response_payload["overall_score"] = single_result["overall_score"]
        response_payload["max_score"] = single_result["max_score"]
        response_payload["error"] = single_result["error"]

    return response_payload

@app.get("/download-report/{session_id}/{filename}", tags=["Download"])
async def download_single_report(session_id: str, filename: str):
    logger.info(f"Download request received for session '{session_id}', filename '{filename}'")

    if not re.match(r'^[\w\-]+\.pdf$', filename, re.IGNORECASE):
        logger.warning(f"Invalid filename format requested: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename format.")

    if not re.match(r'^[a-fA-F0-9\-]+$', session_id):
        logger.warning(f"Invalid session ID format requested: {session_id}")
        raise HTTPException(status_code=400, detail="Invalid session ID format.")

    session_data = evaluation_storage.get(session_id)
    if not session_data:
        logger.warning(f"Session ID not found: {session_id}")
        raise HTTPException(status_code=404, detail="Evaluation session not found or expired.")

    report_info = session_data.get(filename)
    if not report_info:
        logger.warning(f"Filename '{filename}' not found within session '{session_id}'")
        raise HTTPException(status_code=404, detail="Specific report file not found in this session.")

    evaluation_result_data = report_info.get("data")
    config_flags = report_info.get("config", {})

    if evaluation_result_data is None:
        logger.error(f"Missing 'data' key for report '{filename}' in session '{session_id}'")
        raise HTTPException(status_code=500, detail="Internal error: Evaluation data missing.")

    try:
        pdf_generator = PDFReport()
        pdf_buffer = pdf_generator.create(evaluation_result_data, config_flags)
        logger.info(f"Sending PDF report: {filename}")
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\""
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error during PDF generation/download for {filename}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while generating the report.")

# --- Rubric Management Endpoints ---

@app.get("/rubrics/", tags=["Rubrics"], response_model=Dict[str, str])
async def list_rubrics():
    rubrics_dir = "rubrics"
    rubric_files = {}
    try:
        if not os.path.isdir(rubrics_dir):
            logger.warning(f"Rubrics directory '{rubrics_dir}' not found.")
            return {}
        for filename in os.listdir(rubrics_dir):
            if filename.endswith(".txt"):
                rubric_id = safe_slice_str(filename, end=-4) # type: ignore
                _, name = get_rubric_by_id(rubric_id)
                rubric_files[rubric_id] = name if name else rubric_id
        return rubric_files
    except Exception as e:
        logger.error(f"Error listing rubrics: {e}")
        raise HTTPException(status_code=500, detail="Could not list available rubrics.")

@app.get("/rubrics/{rubric_id}", tags=["Rubrics"], response_model=Dict[str, Optional[str]])
async def get_rubric_details(rubric_id: str):
    content, name = get_rubric_by_id(rubric_id)
    if content is None and name is None:
        raise HTTPException(status_code=404, detail=f"Rubric with ID '{rubric_id}' not found.")
    return {"id": rubric_id, "name": name, "content": content}

@app.get("/default-rubric/", tags=["Rubrics"], response_model=Dict[str, str])
async def get_default_rubric():
    return {"name": "Default Academic Rubric", "content": DEFAULT_RUBRIC}

if __name__ == "__main__":
    import uvicorn # type: ignore
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("RELOAD", "false").lower() in ["true", "1", "yes"]
    log_level = "info"

    print(f"--- Starting Essay Evaluator API ---")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reloading: {'Enabled' if reload else 'Disabled'}")
    print(f"Allowed Origins: {origins if origins else '*'}")
    print(f"Log Level: {log_level}")
    print(f"------------------------------------")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level.lower()
    )
