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
from typing import Any, Dict, List, Literal, Optional, Union
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle
import google.generativeai as genai
import pdfplumber
from docx import Document
from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl, ValidationError, field_validator
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch

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

evaluation_storage: Dict[str, Dict[str, Union[EssayEvaluation, Dict[str, Any]]]] = {}

# --- Essay Processing Functions ---

async def extract_text(file: UploadFile) -> str:
    logger.info(f"Extracting text from file: '{file.filename}' (Type: {file.content_type})")
    content = await file.read()
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

def split_essays(text: str) -> List[str]:
    logger.info("Attempting to split text into multiple essays.")
    patterns = [
        r"^\s*(?:student\s+)?name\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
        r"^\s*student\s*:\s*([A-Za-z]+(?:['\- ]?[A-Za-z']+){0,4})\s*$",
    ]

    all_matches = []
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
            essay_content = text[start_pos:].strip()
        else:
            next_start_pos = all_matches[i + 1][0]
            essay_content = text[start_pos:next_start_pos].strip()
        if essay_content and len(essay_content) > 200:
            essays.append(essay_content)
        last_pos = start_pos if i == len(all_matches) - 1 else all_matches[i + 1][0]

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
) -> List[Union[EssayEvaluation, Dict[str, Any]]]:
    essays = split_essays(essay_text)
    logger.info(f"Attempting to evaluate {len(essays)} detected essay(s).")

    if not essays:
        logger.warning("Splitting resulted in zero essays.")
        return []

    results: List[Union[EssayEvaluation, Dict[str, Any]]] = []
    base_delay = 1.5
    max_delay_increment = 1.0

    tasks = []
    for i, essay_content in enumerate(essays):
        if not essay_content or not essay_content.strip():
            logger.warning(f"Skipping empty essay chunk at index {i}.")
            continue
        task = evaluate_single_essay_with_error_handling(
            essay_content=essay_content,
            rubric_text=rubric_text,
            api_key=api_key,
            essay_index=i,
            generosity=generosity,
            delay=(base_delay + random.uniform(0, max_delay_increment)) if i > 0 else 0
        )
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
    delay: float
) -> Union[EssayEvaluation, Dict[str, Any]]:
    if delay > 0:
        await asyncio.sleep(delay)

    student_name = "Unknown Student"
    try:
        logger.info(f"Starting evaluation for essay index {essay_index}...")
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
                    student_name = potential_name
                    logger.info(f"Extracted student name for essay {essay_index}: {student_name}")
                    break
        if student_name == "Unknown Student":
            logger.warning(f"Could not extract student name for essay {essay_index}.")

        evaluation = await evaluate_essay(essay_content, rubric_text, api_key, student_name, generosity)
        logger.info(f"Successfully evaluated essay index {essay_index} for '{evaluation.student_name}'.")
        return evaluation

    except (ValueError, ValidationError, Exception) as e:
        error_message = f"Evaluation failed: {str(e)}"
        logger.error(f"Error processing essay index {essay_index} for '{student_name}': {error_message}\n{traceback.format_exc()}")
        return {
            "student_name": student_name if student_name != "Unknown Student" else f"Failed_Essay_{essay_index+1}",
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
    generosity: Literal['strict', 'standard', 'generous']
) -> EssayEvaluation:
    if not api_key:
        logger.error("Gemini API key is missing.")
        raise ValueError("API key not configured.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

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
{generosity_instruction}
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
        temperature=temperature,
        response_mime_type="application/json",
    )

    for attempt in range(max_retries):
        try:
            logger.info(f"Sending request to Gemini API for '{extracted_student_name}' (Attempt {attempt + 1}/{max_retries}, Generosity: {generosity})...")
            response = await model.generate_content_async(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            if not response.candidates:
                block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else 'Unknown'
                finish_reason = response.candidates[0].finish_reason if response.candidates else 'Unknown'
                logger.error(f"Gemini API call failed for '{extracted_student_name}': No candidates returned.")
                logger.error(f"Block Reason: {block_reason}, Finish Reason: {finish_reason}")
                raise ValueError(f"API response blocked or empty. Reason: {block_reason}/{finish_reason}")

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
    HIGHLIGHT_COLOR = colors.HexColor('#fef08a')
    TEXT_COLOR = colors.HexColor('#1e293b')
    FONT_NAME = 'Helvetica'
    BOLD_FONT = 'Helvetica-Bold'

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()
        self.student_name: str = "Unknown Student"

    def _create_custom_styles(self):
        self.styles.add(ParagraphStyle(name='Base', parent=self.styles['Normal'], fontName=self.FONT_NAME, fontSize=10, textColor=self.TEXT_COLOR, leading=14))
        self.styles.add(ParagraphStyle(name='MainTitle', parent=self.styles['h1'], fontName=self.BOLD_FONT, fontSize=24, spaceAfter=12, alignment=TA_CENTER, textColor=self.ACCENT_COLOR))
        self.styles.add(ParagraphStyle(name='StudentTitle', parent=self.styles['h2'], fontName=self.FONT_NAME, fontSize=14, spaceAfter=6, alignment=TA_CENTER, textColor=self.HEADER_COLOR))
        self.styles.add(ParagraphStyle(name='ScoreTitle', parent=self.styles['h3'], fontName=self.BOLD_FONT, fontSize=12, spaceAfter=18, alignment=TA_CENTER, textColor=self.TEXT_COLOR))
        self.styles.add(ParagraphStyle(name='SectionTitle', parent=self.styles['h3'], fontName=self.BOLD_FONT, fontSize=14, spaceBefore=12, spaceAfter=8, textColor=self.HEADER_COLOR))
        self.styles.add(ParagraphStyle(name='TableHeader', fontName=self.BOLD_FONT, alignment=TA_CENTER, textColor=colors.white))
        self.styles.add(ParagraphStyle(name='TableCell', parent=self.styles['Base'], alignment=TA_LEFT, leading=12))
        self.styles.add(ParagraphStyle(name='TableCellBold', parent=self.styles['TableCell'], fontName=self.BOLD_FONT))
        self.styles.add(ParagraphStyle(name='TableCellCenter', parent=self.styles['TableCell'], alignment=TA_CENTER))
        self.styles.add(ParagraphStyle(name='FeedbackCell', parent=self.styles['TableCell'], fontSize=9))
        self.styles.add(ParagraphStyle(name='SuggestionItem', parent=self.styles['Base'], leftIndent=18, bulletIndent=0, spaceBefore=3, bulletFontName=self.BOLD_FONT, bulletFontSize=10, bulletColor=self.ACCENT_COLOR))
        self.styles.add(ParagraphStyle(name='MiniLessonItem', parent=self.styles['Base'], leftIndent=18, bulletIndent=0, spaceBefore=3, bulletFontName=self.BOLD_FONT, bulletFontSize=10, bulletColor=self.TEAL_COLOR))
        self.styles.add(ParagraphStyle(name='HighlightText', parent=self.styles['Base'], backColor=self.HIGHLIGHT_COLOR, borderPadding=(2, 4)))
        self.styles.add(ParagraphStyle(name='HighlightIssue', parent=self.styles['Base'], leftIndent=10, textColor=self.DANGER_COLOR, fontName=self.BOLD_FONT, spaceBefore=2))
        self.styles.add(ParagraphStyle(name='HighlightSuggestion', parent=self.styles['Base'], leftIndent=10, textColor=self.SUCCESS_COLOR, spaceBefore=1))
        self.styles.add(ParagraphStyle(name='ErrorText', parent=self.styles['Base'], textColor=self.DANGER_COLOR, fontName=self.BOLD_FONT, alignment=TA_CENTER, spaceBefore=12, fontSize=12))

    def on_page(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(self.HEADER_COLOR)
        canvas.rect(doc.leftMargin, doc.height + doc.topMargin - 0.1 * inch, doc.width, 0.1 * inch, fill=1)
        canvas.setFont(self.FONT_NAME, 8)
        canvas.setFillColor(self.TEXT_COLOR)
        canvas.drawString(doc.leftMargin + 0.1 * inch, doc.height + doc.topMargin - 0.25 * inch, f"Student: {self.student_name}")
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

    def _create_section_title(self, title_text: str, doc_width: float) -> Table:
        title_para = Paragraph(title_text, self.styles['SectionTitle'])
        section_table = Table([[title_para]], colWidths=[doc_width])
        section_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.LIGHT_BG),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        return section_table

    def create(self, evaluation_data: Union[EssayEvaluation, Dict[str, Any]], config_flags: Dict[str, bool]) -> BytesIO:
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

        elements.append(Paragraph("Essay Evaluation Report", self.styles['MainTitle']))
        elements.append(Paragraph(f"Student: {self.student_name}", self.styles['StudentTitle']))
        score_color = self._get_score_color(evaluation.overall_score, max_score_total)
        score_text = f"Overall Score: <font color='{score_color.hexval()}'><b>{evaluation.overall_score:.1f}</b></font>"
        if max_score_total > 0:
            score_text += f" / {max_score_total:.1f}"
        elements.append(Paragraph(score_text, self.styles['ScoreTitle']))

        include_criteria = config_flags.get("include_criteria", True)
        include_highlights = config_flags.get("include_highlights", True)
        include_suggestions = config_flags.get("include_suggestions", True)
        include_mini_lessons = config_flags.get("include_mini_lessons", True)

        if include_criteria and evaluation.criteria:
            elements.append(self._create_section_title("Evaluation Breakdown", doc.width))
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
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.ACCENT_COLOR),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), self.BOLD_FONT),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ('LEFTPADDING', (0, 1), (-1, -1), 6),
                ('RIGHTPADDING', (0, 1), (-1, -1), 6),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 0.2 * inch))

        if include_highlights and evaluation.highlighted_passages:
            elements.append(self._create_section_title("Highlighted Passages / Examples", doc.width))
            elements.append(Spacer(1, 0.1 * inch))
            for i, passage in enumerate(evaluation.highlighted_passages):
                passage_elements = [
                    Paragraph(f"<b>Passage {i+1}:</b> \"{passage.text}\"", self.styles['HighlightText']),
                    Paragraph(f"<b>Issue/Note:</b> {passage.issue}", self.styles['HighlightIssue']),
                    Paragraph(f"<b>Suggestion:</b> {passage.suggestion}", self.styles['HighlightSuggestion'])
                ]
                if passage.example_revision:
                    passage_elements.append(Paragraph(f"<b>Example Revision:</b> {passage.example_revision}", self.styles['HighlightSuggestion']))
                highlight_table = Table([[p] for p in passage_elements], colWidths=[doc.width - 0.2 * inch])
                highlight_table.setStyle(TableStyle([
                    ('BOX', (0, 0), (-1, -1), 0.5, self.ACCENT_COLOR),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ]))
                elements.append(highlight_table)
                elements.append(Spacer(1, 0.15 * inch))

        if include_suggestions and evaluation.suggestions:
            elements.append(self._create_section_title("General Suggestions for Improvement", doc.width))
            elements.append(Spacer(1, 0.1 * inch))
            for sug in evaluation.suggestions:
                if isinstance(sug, str) and sug.strip():
                    elements.append(Paragraph(sug, self.styles['SuggestionItem'], bulletText='•'))
            elements.append(Spacer(1, 0.2 * inch))

        if include_mini_lessons and evaluation.mini_lessons:
            elements.append(self._create_section_title("Key Mini-Lessons / Focus Areas", doc.width))
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
async def evaluate_essay_endpoint(
    form_data: EvaluationRequestForm = Depends(),
    essay: UploadFile = File(...),
    rubric_file: Optional[UploadFile] = File(None)
):
    server_api_key = os.getenv('GEMINI_API_KEY')
    effective_api_key = form_data.api_key or server_api_key

    if not effective_api_key:
        logger.error("API key is not configured on the server and was not provided in the request.")
        raise HTTPException(status_code=500, detail="AI API key is not configured.")

    effective_rubric_text = DEFAULT_RUBRIC
    rubric_source = "default"

    if form_data.rubric_text:
        effective_rubric_text = form_data.rubric_text
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
    elif form_data.rubric_id:
        loaded_rubric_content, loaded_rubric_name = get_rubric_by_id(form_data.rubric_id)
        if loaded_rubric_content:
            effective_rubric_text = loaded_rubric_content
            rubric_source = f"ID '{form_data.rubric_id}' ({loaded_rubric_name or 'Unnamed'})"
        else:
            logger.warning(f"Could not load rubric for ID '{form_data.rubric_id}'. Falling back to default.")
            rubric_source = f"default (ID '{form_data.rubric_id}' not found or invalid)"

    logger.info(f"Using rubric from: {rubric_source}")
    logger.info(f"Evaluation generosity level: {form_data.generosity}")

    try:
        essay_text_content = await extract_text(essay)
        if not essay_text_content.strip():
            logger.error(f"Uploaded essay file '{essay.filename}' resulted in empty content.")
            raise HTTPException(status_code=400, detail="Essay file is empty or could not be read.")
    except ValueError as e:
        logger.error(f"Failed to extract text from essay file '{essay.filename}': {e}")
        raise HTTPException(status_code=400, detail=f"Error processing essay file: {e}")
    except Exception as e:
        logger.error(f"Unexpected error extracting text from '{essay.filename}': {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while reading the essay file.")

    try:
        evaluations = await evaluate_essays(
            essay_text=essay_text_content,
            rubric_text=effective_rubric_text,
            api_key=effective_api_key,
            generosity=form_data.generosity
        )
    except ValueError as e:
        logger.error(f"Evaluation failed permanently: {e}")
        raise HTTPException(status_code=500, detail=f"AI evaluation failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error during evaluation process: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred during evaluation.")

    if not evaluations:
        logger.warning(f"Evaluation process returned no results for file '{essay.filename}'. This might be due to empty content after splitting.")
        return {
            "evaluation_status": "empty",
            "message": "No valid essay content found in the uploaded file after processing.",
            "session_id": None,
            "results": []
        }

    session_id = str(uuid.uuid4())
    session_storage_entry: Dict[str, Union[EssayEvaluation, Dict[str, Any]]] = {}
    results_summary = []
    config_flags = form_data.model_dump(include={'include_criteria', 'include_suggestions', 'include_highlights', 'include_mini_lessons'})

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
    logger.info(f"Stored {len(evaluations)} evaluation result(s) under session ID: {session_id}")

    response_payload = {
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
                rubric_id = filename[:-4]
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
    import uvicorn
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