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

# Load environment variables
load_dotenv()

# Create uploads directory if it doesn't exist
os.makedirs("uploads", exist_ok=True)
os.makedirs("rubrics", exist_ok=True)

# Initialize FastAPI app with CORS
app = FastAPI()

# Get allowed origins from environment or use defaults
allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
origins = allowed_origins.split(",")

# For debugging, allow all origins temporarily
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins temporarily
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

# Essay Processing Functions
async def extract_text(file: UploadFile) -> str:
    """Extract text from uploaded files (PDF, TXT, DOCX)."""
    content = await file.read()
    if not content:
        raise ValueError(f"Cannot read an empty file: '{file.filename}'.")

    # Check file extension as a fallback
    filename = file.filename.lower()
    
    # Handle TXT files
    if file.content_type == 'text/plain' or filename.endswith('.txt'):
        try:
            return content.decode('utf-8')
        except UnicodeDecodeError:
            # Try different encodings if UTF-8 fails
            try:
                return content.decode('latin-1')
            except UnicodeDecodeError:
                raise ValueError(f"Failed to decode TXT file '{file.filename}'. Encoding not supported.")
    
    # Handle PDF files
    elif file.content_type == 'application/pdf' or filename.endswith('.pdf'):
        try:
            with pdfplumber.open(BytesIO(content)) as pdf:
                text = '\n'.join([page.extract_text() or '' for page in pdf.pages])
                return text
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF '{file.filename}': {str(e)}")
    
    # Handle DOCX files
    elif file.content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or filename.endswith('.docx'):
        try:
            with BytesIO(content) as doc_file:
                doc = Document(doc_file)
                text = '\n'.join([para.text for para in doc.paragraphs])
                return text
        except Exception as e:
            raise ValueError(f"Failed to extract text from DOCX '{file.filename}': {str(e)}")
    
    else:
        raise ValueError(f"Unsupported file format: {file.content_type} for file {file.filename}")

def split_essays(text: str) -> List[str]:
    """Split text into multiple essays based on student name pattern."""
    # Use multiple patterns to match student identifiers
    patterns = [
        r"Student Name:\s+([A-Za-z]+(?: [A-Za-z]+){0,2})",
        r"Student:\s+([A-Za-z]+(?: [A-Za-z]+){0,2})",
        r"Name:\s+([A-Za-z]+(?: [A-Za-z]+){0,2})"
    ]
    
    all_matches = []
    for pattern in patterns:
        matches = list(re.finditer(pattern, text))
        all_matches.extend(matches)
    
    # Sort matches by their position in the text
    all_matches.sort(key=lambda m: m.start())
    
    # If no matches or only one match, return the entire text as a single essay
    if len(all_matches) <= 1:
        # Try another approach - look for essay separators like multiple newlines
        chunks = re.split(r'\n{3,}', text)
        if len(chunks) > 1 and any("Student" in chunk for chunk in chunks):
            # Check if these look like separate essays
            essays = []
            for chunk in chunks:
                if len(chunk.strip()) > 100:  # Only consider chunks of reasonable length
                    essays.append(chunk)
            if len(essays) > 1:
                print(f"Split text into {len(essays)} essays based on newline separators")
                return essays
        return [text]
    
    print(f"Found {len(all_matches)} student name markers")
    
    essays = []
    # For each match, extract text until the next match or end of text
    for i, match in enumerate(all_matches):
        start_pos = match.start()
        
        # If it's the last match, take all text until the end
        if i == len(all_matches) - 1:
            essays.append(text[start_pos:])
        else:
            # Otherwise, take text until the next match
            end_pos = all_matches[i + 1].start()
            essays.append(text[start_pos:end_pos])
    
    # Add debug info about what was found
    for i, essay in enumerate(essays):
        student_name = "Unknown"
        name_match = re.search(r"Student Name:\s+([A-Za-z]+(?: [A-Za-z]+){0,2})", essay)
        if name_match:
            student_name = name_match.group(1)
        print(f"Essay {i+1}: {student_name} - {len(essay)} characters")
    
    return essays

async def evaluate_essays(essay_text: str, rubric_text: str | None, api_key: str) -> List[dict]:
    """Split and evaluate multiple essays if detected, or evaluate as single essay."""
    # Check if we have a long document or multiple student names
    is_large_document = len(essay_text.split('\n')) > 200
    
    # Check for multiple student identifiers with different patterns
    student_name_count = essay_text.count("Student Name:")
    student_count = essay_text.count("Student:")
    name_count = essay_text.count("Name:")
    
    has_multiple_students = (student_name_count + student_count + name_count) > 1
    
    print(f"Document stats: {len(essay_text.split())} words, {len(essay_text.split('\\n'))} lines")
    print(f"Student indicators: Student Name:{student_name_count}, Student:{student_count}, Name:{name_count}")
    
    results = []
    
    if is_large_document or has_multiple_students:
        # Split into separate essays
        essays = split_essays(essay_text)
        
        print(f"Split into {len(essays)} essays")
        
        # If we have more than 12 pages but only one essay detected, try page-based splitting
        if len(essays) == 1 and is_large_document:
            # Attempt a page-based split
            pages = essay_text.split('\n\n\n')
            if len(pages) > 1:
                chunks = []
                current_chunk = ""
                for page in pages:
                    # Look for any student identifier
                    has_student_marker = any(marker in page for marker in ["Student Name:", "Student:", "Name:"])
                    if has_student_marker and current_chunk:
                        chunks.append(current_chunk)
                        current_chunk = page
                    else:
                        current_chunk += "\n\n\n" + page if current_chunk else page
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                if len(chunks) > 1:
                    essays = chunks
                    print(f"Adjusted to {len(essays)} essays using page-based splitting")
        
        # Process essays with student name indicator
        if len(essays) > 1:
            print(f"Processing {len(essays)} separate essays")
            
            # Calculate a time delay between API calls based on essay count to avoid rate limits
            # More essays = longer delay to spread out API calls
            base_delay = 2  # Base delay in seconds
            if len(essays) > 5:
                base_delay = 3  # Increase delay for more essays
            
            # Process each essay individually
            for i, essay in enumerate(essays):
                if len(essay.strip()) > 100:  # Only evaluate non-trivial essays
                    try:
                        print(f"Processing essay {i+1}/{len(essays)}")
                        # Extract first few characters for logging (avoid logging entire essay)
                        preview = essay[:100].replace('\n', ' ') + "..."
                        print(f"Essay preview: {preview}")
                        
                        # Add a delay between API calls to avoid rate limits, except for the first essay
                        if i > 0:
                            # Add some randomness to the delay to avoid synchronized requests
                            delay = base_delay + (random.uniform(0, 1.5) * (i % 3))
                            print(f"Adding delay of {delay:.2f}s before processing next essay to avoid rate limits")
                            await asyncio.sleep(delay)
                        
                        # Attempt to evaluate the essay with retry logic for rate limits
                        evaluation = await evaluate_essay(essay, rubric_text, api_key)
                        print(f"Evaluation complete for essay {i+1}, student: {evaluation.get('student_name', 'Unknown')}")
                        results.append(evaluation)
                    except Exception as e:
                        print(f"Error processing essay {i+1}: {str(e)}")
                        
                        # Extract student name for the error report
                        student_name = "Unknown"
                        for pattern in [r"Student Name:\s+([A-Za-z]+(?: [A-Za-z]+){0,2})", r"Student:\s+([A-Za-z]+(?: [A-Za-z]+){0,2})", r"Name:\s+([A-Za-z]+(?: [A-Za-z]+){0,2})"]:
                            name_match = re.search(pattern, essay)
                            if name_match:
                                student_name = name_match.group(1)
                                break
                        
                        # Add a placeholder result for failed essays
                        results.append({
                            "student_name": student_name,
                            "overall_score": 0,
                            "criteria": [{"name": "Processing Error", "score": 0, "max_score": 10, "feedback": str(e)}],
                            "suggestions": ["Processing error occurred. Please try again."],
                            "highlighted_passages": []
                        })
        else:
            # Process as single essay
            print("Processing as a single essay despite potential markers")
            evaluation = await evaluate_essay(essay_text, rubric_text, api_key)
            results.append(evaluation)
    else:
        # Process as a single essay
        print("Processing as a single essay (no multiple essay markers detected)")
        evaluation = await evaluate_essay(essay_text, rubric_text, api_key)
        results.append(evaluation)
    
    print(f"Completed processing with {len(results)} results")
    return results

async def evaluate_essay(essay_text: str, rubric_text: str | None, api_key: str) -> dict:
    """Evaluate an essay using the Gemini API with retry logic for rate limits."""
    if not api_key:
        raise ValueError("API key is required for evaluation.")
    
    genai.configure(api_key=api_key)
    
    # Note: Adjust the model name based on the latest available Gemini model
    model = genai.GenerativeModel('gemini-2.0-pro-exp-02-05')  # Updated to the latest model name
    client = model.start_chat(history=[])
    rubric = rubric_text if rubric_text else DEFAULT_RUBRIC

    # Extract criteria names and max scores from the rubric more precisely
    criteria_pattern = r'(\d+)\.\s+([\w\s&,\-]+)\s+\(0-(\d+)\):'
    criteria_matches = re.findall(criteria_pattern, rubric)
    
    # If we can't extract criteria, fall back to counting
    if not criteria_matches:
        criteria_count = len(re.findall(r'\d+\.\s+[\w\s&,\-]+\s+\(0-\d+\):', rubric))
        if criteria_count == 0:
            criteria_count = 5  # Default to 5 if we can't determine
        # Default max score per criterion
        max_score_per_criterion = 10
        criteria_names = []
        criteria_max_scores = []
    else:
        criteria_count = len(criteria_matches)
        # Extract the actual criteria names and max scores for explicit instruction
        criteria_names = [match[1].strip() for match in criteria_matches]
        criteria_max_scores = [int(match[2]) for match in criteria_matches]
        max_score_per_criterion = criteria_max_scores[0] if criteria_max_scores else 10
    
    # Calculate the maximum possible score
    if 'criteria_max_scores' in locals() and criteria_max_scores:
        max_score = sum(criteria_max_scores)
    else:
        max_score = criteria_count * max_score_per_criterion

    # Extract student name if available - improved patterns to limit name capture
    student_name = "Unknown"
    name_patterns = [
        r"Student Name:\s+([A-Za-z]+(?: [A-Za-z]+){0,2})(?:\s*\n|\s{2,}|$)",  # Student Name: John Doe
        r"Name:\s+([A-Za-z]+(?: [A-Za-z]+){0,2})(?:\s*\n|\s{2,}|$)",  # Name: John Doe
        r"Student:\s+([A-Za-z]+(?: [A-Za-z]+){0,2})(?:\s*\n|\s{2,}|$)",  # Student: John Doe
        r"Author:\s+([A-Za-z]+(?: [A-Za-z]+){0,2})(?:\s*\n|\s{2,}|$)",  # Author: John Doe
        r"By:\s+([A-Za-z]+(?: [A-Za-z]+){0,2})(?:\s*\n|\s{2,}|$)"  # By: John Doe
    ]
    
    for pattern in name_patterns:
        name_match = re.search(pattern, essay_text, re.IGNORECASE)
        if name_match:
            student_name = name_match.group(1).strip()
            break
    
    # If name not found with the stricter patterns, try a more focused approach
    if student_name == "Unknown":
        first_line_match = re.match(r'^([A-Za-z]+(?: [A-Za-z]+){0,2})\s*$', essay_text.split('\n')[0])
        if first_line_match:
            student_name = first_line_match.group(1).strip()
    
    # Limit name length to avoid capturing essay content
    if len(student_name.split()) > 3:
        name_parts = student_name.split()[:2]  # Limit to first two words
        student_name = " ".join(name_parts)

    prompt = f"""
    Evaluate the following essay based on the provided rubric. Provide an overall score and detailed feedback.
    
    IMPORTANT INSTRUCTIONS:
    1. Use ONLY the criteria specified in the rubric below.
    2. Do NOT add any additional criteria that are not in the rubric.
    3. Do NOT modify, rename, or reinterpret any criteria from the rubric.
    4. Score each criterion according to its specified scale in the rubric (e.g., 0-10, 0-5, etc.).
    5. The overall_score should be the sum of all individual criteria scores.
    6. Use the EXACT names of the criteria as they appear in the rubric.
    7. Additionally, identify 3-5 specific passages in the essay that could be improved. For each passage:
       a. Quote the exact text that needs improvement (keep quotes under 100 characters)
       b. Explain what specific issue exists in this passage
       c. Provide a constructive suggestion for how to improve it
       d. If appropriate, offer a brief example of how the passage could be rewritten
    8. Make sure to return VALID JSON - check that all quotes and brackets are properly balanced

    RUBRIC:
    {rubric}

    ESSAY:
    {essay_text}

    Respond with JSON format:
    {{
        "student_name": "{student_name}",
        "overall_score": float (0-{max_score}),
        "criteria": [
            {{
                "name": str,
                "score": float,
                "max_score": int,
                "feedback": str
            }}
        ],
        "suggestions": [str],
        "highlighted_passages": [
            {{
                "text": str,
                "issue": str,
                "suggestion": str,
                "example_revision": str
            }}
        ]
    }}
    """
    
    # If we successfully extracted criteria names and max scores, add them explicitly to ensure model follows them
    if 'criteria_names' in locals() and criteria_names and 'criteria_max_scores' in locals() and criteria_max_scores:
        prompt += f"\n\nYou MUST use EXACTLY these {len(criteria_names)} criteria with their EXACT names and max scores:\n"
        for i, (name, max_score) in enumerate(zip(criteria_names, criteria_max_scores)):
            prompt += f"{i+1}. {name} (0-{max_score})\n"
    
    # Add retry logic with exponential backoff for rate limits
    max_retries = 5
    base_delay = 2  # Starting delay in seconds
    
    for retry_count in range(max_retries):
        try:
            # If this is a retry attempt, add a note about it
            if retry_count > 0:
                print(f"Retry attempt {retry_count}/{max_retries} for student: {student_name}")
            
            response = await client.send_message_async(prompt)
            cleaned_response = re.sub(r'```json|```', '', response.text).strip()
            
            # Additional JSON error handling
            try:
                result = json.loads(cleaned_response)
            except json.JSONDecodeError as json_err:
                print(f"JSON parsing error: {str(json_err)}")
                print(f"Attempting to fix malformed JSON...")
                
                # Attempt to fix common JSON issues
                fixed_json = cleaned_response
                # Replace single quotes with double quotes where appropriate
                fixed_json = re.sub(r"'([^']*)':", r'"\1":', fixed_json)
                # Ensure proper quotes around keys
                fixed_json = re.sub(r'(\w+):', r'"\1":', fixed_json)
                
                try:
                    result = json.loads(fixed_json)
                except json.JSONDecodeError:
                    # If still failing, create a default structure
                    print("Creating default evaluation structure")
                    result = {
                        "student_name": student_name,
                        "overall_score": max_score / 2,  # Default to middle score
                        "criteria": [
                            {
                                "name": name, 
                                "score": max_score_per_criterion / 2, 
                                "max_score": max_score_per_criterion,
                                "feedback": "Unable to evaluate this criterion."
                            } for name in (criteria_names if criteria_names else ["Overall Quality"])
                        ],
                        "suggestions": ["Unable to generate suggestions due to processing error."],
                        "highlighted_passages": []
                    }
            
            # Ensure all required keys exist
            required_keys = ["student_name", "overall_score", "criteria", "suggestions", "highlighted_passages"]
            for key in required_keys:
                if key not in result:
                    if key == "student_name":
                        result[key] = student_name
                    elif key == "overall_score":
                        result[key] = 0  # Default value
                    elif key == "criteria":
                        result[key] = []
                    elif key == "suggestions":
                        result[key] = []
                    elif key == "highlighted_passages":
                        result[key] = []
            
            # Ensure each criterion has a max_score field
            for i, criterion in enumerate(result['criteria']):
                if not isinstance(criterion, dict):
                    # Handle case where criterion is not a dictionary
                    print(f"Invalid criterion format at index {i}: {criterion}")
                    result['criteria'][i] = {
                        "name": f"Criterion {i+1}",
                        "score": 0,
                        "max_score": max_score_per_criterion,
                        "feedback": "Invalid criterion format in response."
                    }
                    continue
                    
                if 'max_score' not in criterion:
                    if i < len(criteria_max_scores):
                        criterion['max_score'] = criteria_max_scores[i]
                    else:
                        criterion['max_score'] = max_score_per_criterion
                        
                # Ensure score is numeric
                if not isinstance(criterion.get('score'), (int, float)):
                    try:
                        criterion['score'] = float(criterion.get('score', 0))
                    except (ValueError, TypeError):
                        criterion['score'] = 0
            
            # Validate the result has the correct number of criteria
            if len(result['criteria']) != criteria_count:
                # If we have the criteria names, we can fix this by keeping only the correct ones
                if 'criteria_names' in locals() and criteria_names:
                    # Keep only criteria that match our extracted names exactly
                    correct_criteria = []
                    for i, name in enumerate(criteria_names):
                        # Find the matching criterion or create a default one
                        matching = next((c for c in result['criteria'] if isinstance(c, dict) and c.get('name', '').lower() == name.lower()), None)
                        if matching:
                            # Ensure the name is exactly as in the rubric
                            matching['name'] = name
                            # Ensure max_score is correct
                            if i < len(criteria_max_scores):
                                matching['max_score'] = criteria_max_scores[i]
                            correct_criteria.append(matching)
                        else:
                            # Create a default criterion if the model didn't provide one
                            max_score_for_criterion = criteria_max_scores[i] if i < len(criteria_max_scores) else max_score_per_criterion
                            correct_criteria.append({
                                "name": name,
                                "score": max_score_for_criterion / 2,  # Default middle score
                                "max_score": max_score_for_criterion,
                                "feedback": f"No specific feedback provided for {name}."
                            })
                    
                    # Replace with corrected criteria
                    result['criteria'] = correct_criteria
                else:
                    # If we don't have names, just take the first 'criteria_count' criteria
                    # Ensure we have at least one criterion
                    if not result['criteria']:
                        result['criteria'] = [{
                            "name": "Overall Quality",
                            "score": max_score_per_criterion / 2,
                            "max_score": max_score_per_criterion,
                            "feedback": "No specific feedback provided."
                        }]
                    # Limit to criteria_count
                    result['criteria'] = result['criteria'][:criteria_count]
            else:
                # Even if count is correct, ensure names match exactly
                if 'criteria_names' in locals() and criteria_names:
                    for i, name in enumerate(criteria_names):
                        if i < len(result['criteria']):
                            # Skip if not a dictionary
                            if not isinstance(result['criteria'][i], dict):
                                continue
                            result['criteria'][i]['name'] = name
                            # Also ensure max_score is correct
                            if i < len(criteria_max_scores):
                                result['criteria'][i]['max_score'] = criteria_max_scores[i]
            
            # Recalculate the overall score based on criteria - with error handling
            try:
                criteria_sum = sum(criterion.get('score', 0) for criterion in result['criteria'] 
                                if isinstance(criterion, dict) and isinstance(criterion.get('score'), (int, float)))
                result['overall_score'] = criteria_sum
            except Exception as sum_error:
                print(f"Error recalculating score: {str(sum_error)}")
                result['overall_score'] = 0
            
            # Ensure highlighted_passages exists and is a list
            if 'highlighted_passages' not in result or not isinstance(result['highlighted_passages'], list):
                result['highlighted_passages'] = []
            
            # Validate highlighted_passages format
            for i, passage in enumerate(result['highlighted_passages']):
                if not isinstance(passage, dict):
                    result['highlighted_passages'][i] = {
                        "text": str(passage),
                        "issue": "Invalid passage format",
                        "suggestion": "Unable to process",
                        "example_revision": ""
                    }
                    continue
                    
                # Ensure all keys exist
                for key in ["text", "issue", "suggestion", "example_revision"]:
                    if key not in passage:
                        passage[key] = ""
            
            # Limit to 5 highlighted passages maximum
            if len(result.get('highlighted_passages', [])) > 5:
                result['highlighted_passages'] = result['highlighted_passages'][:5]
                
            # Ensure suggestions is a list of strings
            if not isinstance(result.get('suggestions'), list):
                result['suggestions'] = []
            
            # Convert any non-string suggestions to strings
            result['suggestions'] = [str(s) for s in result['suggestions']]
                
            return result
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if this is a rate limit error (429)
            if "429" in error_str or "resource exhausted" in error_str or "quota" in error_str:
                if retry_count < max_retries - 1:
                    # Calculate backoff delay with some randomness to avoid thundering herd problem
                    delay = base_delay * (2 ** retry_count) + random.uniform(0, 1)
                    print(f"Rate limit (429) encountered. Retrying in {delay:.2f} seconds... (Attempt {retry_count + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                    continue
                else:
                    print(f"Maximum retries ({max_retries}) reached for rate limit. Creating placeholder evaluation.")
                    # Create a simplified evaluation to avoid failing the entire batch
                    return {
                        "student_name": student_name,
                        "overall_score": max_score / 2,  # Default to middle score
                        "criteria": [
                            {
                                "name": name, 
                                "score": max_score_per_criterion / 2, 
                                "max_score": max_score_per_criterion,
                                "feedback": "Unable to evaluate due to API rate limits. Please try again later."
                            } for name in (criteria_names if criteria_names else ["Overall Quality"])
                        ],
                        "suggestions": ["The evaluation could not be completed due to API rate limits. Please try again later with fewer essays or after some time has passed."],
                        "highlighted_passages": []
                    }
            else:
                # For non-rate limit errors, raise immediately
                raise ValueError(f"Error in Gemini API call: {str(e)}")
    
    # This should never be reached due to the loop structure, but added for safety
    raise ValueError("Failed to evaluate essay after maximum retries.")

# PDF Report Generation Class
class PDFReport:
    """Generate a PDF report from evaluation data with attractive styling."""
    
    # Enhanced color palette
    HEADER_COLOR = colors.HexColor('#1a365d')  # Navy blue
    ACCENT_COLOR = colors.HexColor('#3b82f6')  # Blue
    LIGHT_BG = colors.HexColor('#f3f4f6')      # Light gray
    SUCCESS_COLOR = colors.HexColor('#10b981') # Green
    WARNING_COLOR = colors.HexColor('#f59e0b') # Amber
    DANGER_COLOR = colors.HexColor('#ef4444')  # Red
    PURPLE_COLOR = colors.HexColor('#8b5cf6')  # Purple
    PINK_COLOR = colors.HexColor('#ec4899')    # Pink
    TEAL_COLOR = colors.HexColor('#14b8a6')    # Teal
    INDIGO_COLOR = colors.HexColor('#6366f1')  # Indigo
    HIGHLIGHT_COLOR = colors.HexColor('#fef9c3') # Light yellow for highlighting
    
    FONT_NAME = 'Helvetica'
    BOLD_FONT = 'Helvetica-Bold'

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name='MainTitle', fontName=self.BOLD_FONT, fontSize=18, leading=24,
            spaceAfter=24, alignment=TA_CENTER, textColor=self.HEADER_COLOR
        ))
        self.styles.add(ParagraphStyle(
            name='SubTitle', fontName=self.BOLD_FONT, fontSize=14, leading=18,
            spaceAfter=12, textColor=self.ACCENT_COLOR
        ))
        self.styles.add(ParagraphStyle(
            name='TableHeader', fontName=self.BOLD_FONT, fontSize=10, textColor=colors.white,
            alignment=TA_CENTER, leading=14
        ))
        self.styles.add(ParagraphStyle(
            name='TableBody', fontName=self.FONT_NAME, fontSize=10, textColor=colors.black,
            alignment=TA_LEFT, leading=14, wordWrap=True
        ))
        self.styles.add(ParagraphStyle(
            name='FeedbackText', fontName=self.FONT_NAME, fontSize=9, textColor=colors.black,
            alignment=TA_LEFT, leading=12, wordWrap=True
        ))
        self.styles.add(ParagraphStyle(
            name='SuggestionTitle', fontName=self.BOLD_FONT, fontSize=14, leading=18,
            spaceAfter=12, textColor=self.PURPLE_COLOR
        ))
        self.styles.add(ParagraphStyle(
            name='SuggestionItem', fontName=self.FONT_NAME, fontSize=10, 
            leftIndent=20, spaceAfter=8, textColor=colors.black
        ))
        self.styles.add(ParagraphStyle(
            name='HighlightTitle', fontName=self.BOLD_FONT, fontSize=14, leading=18,
            spaceAfter=12, textColor=self.TEAL_COLOR
        ))
        self.styles.add(ParagraphStyle(
            name='HighlightedText', fontName=self.FONT_NAME, fontSize=10, 
            textColor=colors.black, backColor=self.HIGHLIGHT_COLOR,
            borderWidth=1, borderColor=colors.HexColor('#fde68a'),
            borderPadding=5, borderRadius=5
        ))
        self.styles.add(ParagraphStyle(
            name='IssueText', fontName=self.FONT_NAME, fontSize=9, 
            textColor=self.DANGER_COLOR, leftIndent=10
        ))
        self.styles.add(ParagraphStyle(
            name='SuggestionText', fontName=self.FONT_NAME, fontSize=9, 
            textColor=self.ACCENT_COLOR, leftIndent=10
        ))
        self.styles.add(ParagraphStyle(
            name='ExampleText', fontName=self.FONT_NAME, fontSize=9, 
            textColor=self.SUCCESS_COLOR, leftIndent=10, fontStyle='italic'
        ))
        self.styles.add(ParagraphStyle(
            name='Footer', 
            parent=self.styles['BodyText'],
            alignment=TA_CENTER,
            textColor=self.ACCENT_COLOR,
            fontSize=9,
            fontName=self.BOLD_FONT
        ))

    def _get_score_color(self, score, max_score=10):
        """Return appropriate color based on score percentage."""
        percentage = score / max_score
        if percentage >= 0.8:
            return self.SUCCESS_COLOR
        elif percentage >= 0.6:
            return self.ACCENT_COLOR
        elif percentage >= 0.4:
            return self.WARNING_COLOR
        else:
            return self.DANGER_COLOR

    def create(self, evaluation):
        """Create a PDF report from evaluation data."""
        try:
            print(f"Creating PDF report with evaluation data...")
            
            # Validate evaluation data
            if not isinstance(evaluation, dict):
                print(f"Warning: evaluation is not a dictionary, got {type(evaluation)}")
                evaluation = {"student_name": "Unknown", "overall_score": 0, "criteria": []}
            
            pdf_buffer = BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, 
                                  rightMargin=50, leftMargin=50, 
                                  topMargin=50, bottomMargin=50)
            
            # Get student name if available
            student_name = evaluation.get("student_name", "Unknown")
            print(f"Creating PDF for student: {student_name}")
            
            # Calculate max score and overall score
            criteria = evaluation.get("criteria", [])
            
            # Ensure criteria is a list
            if not isinstance(criteria, list):
                print(f"Warning: criteria is not a list, got {type(criteria)}")
                criteria = []
                evaluation["criteria"] = criteria
            
            # Ensure we have at least one criterion
            if not criteria:
                print(f"Warning: no criteria found, adding default criterion")
                criteria.append({
                    "name": "Overall Quality", 
                    "score": evaluation.get("overall_score", 0),
                    "max_score": 10,
                    "feedback": "No specific feedback provided."
                })
                evaluation["criteria"] = criteria
            
            # Calculate max score from criteria
            try:
                max_score = sum(criterion.get("max_score", 10) for criterion in criteria)
                overall_score = evaluation.get("overall_score", 0)
                print(f"Score: {overall_score}/{max_score}")
            except Exception as e:
                print(f"Error calculating scores: {str(e)}")
                max_score = 10 * len(criteria)
                overall_score = evaluation.get("overall_score", 0)
            
            score_color = self._get_score_color(overall_score, max_score)
            
            # Create elements list
            elements = []
            
            # Add title with student name
            if student_name and student_name != "Unknown":
                title = Paragraph(
                    f"<font size='18' color='{self.HEADER_COLOR.hexval()}'>Essay Evaluation Report</font><br/>"
                    f"<font size='14' color='{self.ACCENT_COLOR.hexval()}'>Student: {student_name}</font><br/>"
                    f"<font size='12'>Overall Score: "
                    f"<font color='{score_color.hexval()}'><b>{overall_score}</b></font>/{max_score}</font>",
                    self.styles['MainTitle']
                )
            else:
                title = Paragraph(
                    f"<font size='18' color='{self.HEADER_COLOR.hexval()}'>Essay Evaluation Report</font><br/>"
                    f"<font size='12'>Overall Score: "
                    f"<font color='{score_color.hexval()}'><b>{overall_score}</b></font>/{max_score}</font>",
                    self.styles['MainTitle']
                )
            
            elements.append(title)
            
            # Add a decorative line with gradient effect
            elements.append(Spacer(1, 10))
            
            # Create a gradient-like effect with multiple lines
            colors_list = [self.HEADER_COLOR, self.ACCENT_COLOR, self.TEAL_COLOR, self.PURPLE_COLOR]
            for i, color in enumerate(colors_list):
                elements.append(
                    Table([['']], colWidths=[450 - (i*30)], 
                          style=[('LINEABOVE', (0,0), (0,0), 2 - (i*0.4), color)])
                    )
                elements.append(Spacer(1, 2))
            
            elements.append(Spacer(1, 15))
            
            # Add criteria table
            elements.append(Paragraph("Criteria Evaluation", self.styles['SubTitle']))
            
            # Create table style with proper text wrapping
            table_style = [
                ('BACKGROUND', (0,0), (-1,0), self.HEADER_COLOR),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), self.BOLD_FONT),
                ('ALIGN', (0,0), (-1,0), 'CENTER'),
                ('ALIGN', (1,1), (1,-1), 'CENTER'),  # Center-align score column
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (0,0), (-1,-1), 8),
                ('RIGHTPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 12),
                ('TOPPADDING', (0,0), (-1,-1), 12),
            ]
            
            # Create header row
            rows = [
                [Paragraph('<b>Criteria</b>', self.styles['TableHeader']),
                Paragraph('<b>Score</b>', self.styles['TableHeader']),
                Paragraph('<b>Feedback</b>', self.styles['TableHeader'])]
            ]
            
            # Choose light blue color pair for alternating rows
            bg_colors = [colors.HexColor('#f0f9ff'), colors.HexColor('#e0f2fe')]
            row_colors = []
            
            for i in range(len(criteria)):
                row_colors.append(bg_colors[i % 2])
            
            table_style.append(('ROWBACKGROUNDS', (0,1), (-1,-1), row_colors))
            
            # Add each criterion row
            for criterion in criteria:
                try:
                    if not isinstance(criterion, dict):
                        print(f"Warning: criterion is not a dictionary: {criterion}")
                        continue
                        
                    name = criterion.get("name", "")
                    score = criterion.get("score", 0)
                    max_score = criterion.get("max_score", 10)
                    feedback = criterion.get("feedback", "")
                    score_color = self._get_score_color(score, max_score)
                    
                    # Format score with color
                    score_cell = Paragraph(
                        f"<font color='{score_color.hexval()}'><b>{score}</b></font>/{max_score}",
                        self.styles['TableBody']
                    )
                    
                    # Create a more readable feedback cell
                    feedback_cell = Paragraph(feedback, self.styles['FeedbackText'])
                    
                    rows.append([
                        Paragraph(f"<b>{name}</b>", self.styles['TableBody']),
                        score_cell,
                        feedback_cell
                    ])
                except Exception as e:
                    print(f"Error processing criterion: {str(e)}")
                    continue
            
            # Calculate column widths
            col_widths = [1.5*inch, 1*inch, 3.5*inch]
            
            # Create table
            criteria_table = Table(rows, colWidths=col_widths, style=table_style)
            elements.append(criteria_table)
            elements.append(Spacer(1, 20))
            
            # Process remaining elements of the PDF (highlighted passages, suggestions)
            try:
                # Add highlighted passages
                highlighted_passages = evaluation.get("highlighted_passages", [])
                if highlighted_passages and isinstance(highlighted_passages, list):
                    elements.append(Paragraph("Areas for Improvement", self.styles['HighlightTitle']))
                    elements.append(Spacer(1, 10))
                    
                    for i, passage in enumerate(highlighted_passages, 1):
                        if not isinstance(passage, dict):
                            continue
                            
                        text = passage.get("text", "")
                        issue = passage.get("issue", "")
                        suggestion = passage.get("suggestion", "")
                        example_revision = passage.get("example_revision", "")
                        
                        # Create a table for each highlighted passage
                        passage_data = []
                        
                        # Highlighted text
                        passage_data.append([
                            Paragraph(
                                f"<b>Passage {i}:</b>",
                                self.styles['TableBody']
                            )
                        ])
                        passage_data.append([
                            Paragraph(
                                f"<bgcolor='{self.HIGHLIGHT_COLOR.hexval()}'>{text}</bgcolor>",
                                self.styles['HighlightedText']
                            )
                        ])
                        
                        # Issue
                        passage_data.append([
                            Paragraph(
                                f"<b>Issue:</b> {issue}",
                                self.styles['IssueText']
                            )
                        ])
                        
                        # Suggestion
                        passage_data.append([
                            Paragraph(
                                f"<b>Suggestion:</b> {suggestion}",
                                self.styles['SuggestionText']
                            )
                        ])
                        
                        # Example revision (if provided)
                        if example_revision:
                            passage_data.append([
                                Paragraph(
                                    f"<b>Example Revision:</b> {example_revision}",
                                    self.styles['ExampleText']
                                )
                            ])
                        
                        # Create a table for this passage
                        passage_table = Table(
                            passage_data,
                            colWidths=[500],
                            style=[
                                ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#f0fdfa')),
                                ('BACKGROUND', (0, 1), (0, -1), colors.white),
                                ('BOX', (0, 0), (-1, -1), 1, self.LIGHT_BG),
                                ('TOPPADDING', (0, 0), (-1, -1), 8),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                            ]
                        )
                        elements.append(passage_table)
                        elements.append(Spacer(1, 15))
            except Exception as e:
                print(f"Error processing highlighted passages: {str(e)}")
            
            try:
                # General suggestions
                suggestions = evaluation.get("suggestions", [])
                if suggestions and isinstance(suggestions, list):
                    elements.append(Paragraph("General Suggestions", self.styles['SuggestionTitle']))
                    elements.append(Spacer(1, 10))
                    
                    suggestion_data = []
                    for i, suggestion in enumerate(suggestions):
                        if not isinstance(suggestion, str):
                            suggestion = str(suggestion)
                            
                        colors_list = [self.ACCENT_COLOR, self.PURPLE_COLOR, self.TEAL_COLOR, self.INDIGO_COLOR, self.PINK_COLOR]
                        color = colors_list[i % len(colors_list)]
                        
                        bullet_text = Paragraph(
                            f"<font color='{color.hexval()}'><b>{i+1}.</b></font> {suggestion}",
                            self.styles['SuggestionItem']
                        )
                        suggestion_data.append([bullet_text])
                    
                    # Create a table for suggestions with alternating background colors
                    suggestion_table = Table(
                        suggestion_data,
                        colWidths=[500],
                        style=[
                            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#fafafa')),
                            ('BOX', (0, 0), (-1, -1), 1, self.LIGHT_BG),
                            ('TOPPADDING', (0, 0), (-1, -1), 8),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                            ('LEFTPADDING', (0, 0), (-1, -1), 12),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                        ]
                    )
                    elements.append(suggestion_table)
            except Exception as e:
                print(f"Error processing suggestions: {str(e)}")
            
            # Add a footer with a motivational message
            elements.append(Spacer(1, 20))
            elements.append(
                Paragraph(
                    "Keep improving! Every essay is a step toward mastery.",
                    self.styles['Footer']
                )
            )
            
            # Build PDF
            try:
                doc.build(elements)
                pdf_buffer.seek(0)
                pdf_size = len(pdf_buffer.getvalue())
                print(f"Successfully created PDF: {pdf_size} bytes")
                return pdf_buffer
            except Exception as build_err:
                print(f"Error building PDF document: {str(build_err)}")
                raise
        except Exception as e:
            print(f"Error in PDF generation: {str(e)}")
            # Create a minimal error PDF
            try:
                pdf_buffer = BytesIO()
                doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
                elements = []
                
                elements.append(Paragraph(
                    "Error in PDF Generation",
                    self.styles['MainTitle']
                ))
                elements.append(Spacer(1, 20))
                elements.append(Paragraph(
                    f"An error occurred while generating this PDF report: {str(e)}",
                    self.styles['BodyText']
                ))
                
                doc.build(elements)
                pdf_buffer.seek(0)
                return pdf_buffer
            except:
                # If all else fails, create an extremely minimal PDF
                pdf_buffer = BytesIO()
                doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
                doc.build([Paragraph("Error in PDF Generation", self.styles['Normal'])])
                pdf_buffer.seek(0)
                return pdf_buffer

# Rubric management functions
def get_saved_rubrics():
    """Get list of saved rubrics."""
    rubrics = []
    rubrics_dir = "rubrics"
    
    if os.path.exists(rubrics_dir):
        for filename in os.listdir(rubrics_dir):
            if filename.endswith(".txt"):
                rubric_id = filename[:-4]  # Remove .txt extension
                try:
                    with open(os.path.join(rubrics_dir, filename), "r") as f:
                        content = f.read()
                        # Extract name from first line if possible
                        name = content.strip().split("\n")[0][:50]
                        if not name:
                            name = f"Rubric {rubric_id[:8]}"
                        
                        rubrics.append({
                            "id": rubric_id,
                            "name": name,
                            "preview": content[:100] + "..." if len(content) > 100 else content
                        })
                except Exception:
                    continue
    
    return rubrics

def save_rubric(content: str, rubric_id: Optional[str] = None) -> str:
    """Save a rubric to file and return its ID."""
    if not rubric_id:
        rubric_id = str(uuid.uuid4())
    
    with open(f"rubrics/{rubric_id}.txt", "w") as f:
        f.write(content)
    
    return rubric_id

def get_rubric_by_id(rubric_id: str) -> str:
    """Get rubric content by ID."""
    try:
        with open(f"rubrics/{rubric_id}.txt", "r") as f:
            return f.read()
    except FileNotFoundError:
        raise ValueError(f"Rubric with ID {rubric_id} not found")

def delete_rubric(rubric_id: str) -> bool:
    """Delete a rubric by ID."""
    try:
        os.remove(f"rubrics/{rubric_id}.txt")
        return True
    except FileNotFoundError:
        return False

# API Endpoints
@app.post("/verify_api_key/")
async def verify_api_key(api_key: str = Form(...)):
    """Verify the Gemini API key."""
    try:
        print(f"Attempting to verify API key: {api_key[:5]}...")  # Print first 5 chars for security
        
        # Check if API key is empty or malformed
        if not api_key or len(api_key) < 10:
            print("API key is too short or empty")
            raise HTTPException(status_code=400, detail="API key is too short or empty")
        
        # Configure Gemini with the API key
        genai.configure(api_key=api_key)
        
        # Try to list available models
        try:
            models = genai.list_models()
            model_names = [model.name for model in models]
            print(f"API key verification successful. Found {len(models)} models: {', '.join(model_names[:3])}...")
            return {"status": "success", "message": "API key is valid", "models_found": len(models)}
        except Exception as model_error:
            print(f"Error listing models: {str(model_error)}")
            
            # Try a simpler test - just create a model instance
            try:
                model = genai.GenerativeModel('gemini-1.5-pro')
                print("API key appears valid (model created successfully)")
                return {"status": "success", "message": "API key is valid (basic verification)"}
            except Exception as model_create_error:
                print(f"Error creating model: {str(model_create_error)}")
                raise HTTPException(status_code=400, detail=f"Invalid API key: {str(model_create_error)}")
    
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        print(f"API key verification failed with unexpected error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid API key: {str(e)}")

@app.post("/evaluate/")
async def evaluate_essay_endpoint(
    essay: UploadFile, 
    api_key: str = Form(...), 
    rubric_text: Optional[str] = Form(None),
    rubric_id: Optional[str] = Form(None)
):
    """Evaluate an essay and return results, handling multiple essays if detected."""
    if not essay.size:
        raise HTTPException(status_code=400, detail=f"Cannot read an empty file: '{essay.filename}'.")
    if essay.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type. Allowed types: PDF, TXT, DOCX")

    # Get rubric content - prioritize direct text over ID
    if not rubric_text and rubric_id:
        try:
            rubric_text = get_rubric_by_id(rubric_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    pdf_report = PDFReport()
    try:
        essay_text = await extract_text(essay)
        evaluations = await evaluate_essays(essay_text, rubric_text, api_key)
        
        # Create a unique session ID for this batch
        session_id = str(uuid.uuid4())
        
        # If there's only one essay, return it directly
        if len(evaluations) == 1:
            evaluation = evaluations[0]
            pdf_buffer = pdf_report.create(evaluation)
            student_name = evaluation.get("student_name", "Unknown")
            safe_name = re.sub(r'[^a-zA-Z0-9]', '_', student_name)
            filename = f"{safe_name}_report.pdf" if safe_name != "Unknown" else "evaluation_report.pdf"
            
            return Response(
                content=pdf_buffer.getvalue(),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "X-Essay-Score": str(evaluation['overall_score']),
                    "X-Total-Essays": "1",
                    "X-Session-ID": session_id
                }
            )
        
        # For multiple essays, create a response with information about each essay
        results = []
        pdf_buffers = {}
        
        # Generate PDF reports for each essay
        for i, evaluation in enumerate(evaluations):
            student_name = evaluation.get("student_name", f"Essay_{i+1}")
            safe_name = re.sub(r'[^a-zA-Z0-9]', '_', student_name)
            
            # Create PDF report
            pdf_buffer = pdf_report.create(evaluation)
            pdf_data = pdf_buffer.getvalue()
            
            # Store PDF data with a filename
            filename = f"{safe_name}_report.pdf"
            pdf_buffers[filename] = pdf_data
            
            # Calculate max score
            max_score = sum(criterion.get("max_score", 10) for criterion in evaluation.get("criteria", []))
            
            # Add result info
            results.append({
                "id": i,
                "student_name": student_name,
                "filename": filename,
                "overall_score": evaluation.get("overall_score", 0),
                "max_score": max_score
            })
        
        # Save the pdf_buffers in memory (you would use a persistent storage in production)
        # Here we're using global variables for demonstration
        if not hasattr(app, "_evaluation_storage"):
            app._evaluation_storage = {}
        
        app._evaluation_storage[session_id] = pdf_buffers
        
        # Return a JSON response with information about all essays
        return {
            "multiple_essays": True,
            "count": len(evaluations),
            "session_id": session_id,
            "results": results
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/download-report/{session_id}/{filename}")
async def download_single_report(session_id: str, filename: str):
    """Download a single essay evaluation report."""
    try:
        if not hasattr(app, "_evaluation_storage") or session_id not in app._evaluation_storage:
            raise HTTPException(status_code=404, detail="Session not found")
        
        pdf_buffers = app._evaluation_storage[session_id]
        if filename not in pdf_buffers:
            raise HTTPException(status_code=404, detail="File not found")
        
        pdf_data = pdf_buffers[filename]
        
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/generate-all-zip/")
async def generate_all_zip(data: dict = Body(...)):
    """Generate a zip file containing all essay evaluation PDFs."""
    try:
        session_id = data.get("session_id")
        evaluations = data.get("evaluations", [])
        
        print(f"ZIP generation request received: {len(evaluations)} evaluations, session_id: {session_id}")
        
        # Create a zip file in memory
        zip_buffer = BytesIO()
        
        # Always prioritize evaluations from the request body if available
        if evaluations and len(evaluations) > 0:
            print(f"Generating ZIP from {len(evaluations)} evaluations sent in request body")
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                pdf_report = PDFReport()
                success_count = 0
                
                for i, eval_data in enumerate(evaluations):
                    try:
                        # Log the evaluation data structure for debugging
                        print(f"Processing evaluation {i+1}/{len(evaluations)}")
                        student_name = eval_data.get("student_name", f"Essay_{i+1}")
                        print(f"Student: {student_name}")
                        
                        # Ensure evaluation has all required fields
                        if "criteria" not in eval_data or not eval_data["criteria"]:
                            print(f"Warning: Missing criteria for {student_name}, adding default")
                            eval_data["criteria"] = [{
                                "name": "Overall Quality",
                                "score": eval_data.get("overall_score", 0),
                                "max_score": 10,
                                "feedback": "No specific feedback provided."
                            }]
                        
                        # Create PDF for each evaluation - with explicit error handling
                        try:
                            pdf_buffer = pdf_report.create(eval_data)
                            pdf_data = pdf_buffer.getvalue()
                            print(f"Created PDF for {student_name}: {len(pdf_data)} bytes")
                            
                            if len(pdf_data) < 100:
                                print(f"Warning: PDF for {student_name} seems too small ({len(pdf_data)} bytes)")
                                continue
                        except Exception as pdf_err:
                            print(f"Error creating PDF for {student_name}: {str(pdf_err)}")
                            continue
                        
                        # Generate filename
                        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', student_name)
                        filename = f"{safe_name}_evaluation.pdf"
                        
                        # Add to zip file - with explicit error handling
                        try:
                            zip_file.writestr(filename, pdf_data)
                            print(f"Added {filename} to ZIP ({len(pdf_data)} bytes)")
                            success_count += 1
                        except Exception as zip_err:
                            print(f"Error adding {filename} to ZIP: {str(zip_err)}")
                            continue
                    except Exception as e:
                        print(f"Error processing evaluation {i}: {str(e)}")
                        continue
                
                print(f"Successfully added {success_count} PDFs to ZIP file")
                if success_count == 0:
                    raise HTTPException(status_code=500, detail="Failed to create any valid PDFs for ZIP")
                    
        # Fall back to session storage if no evaluations provided
        elif session_id and hasattr(app, "_evaluation_storage") and session_id in app._evaluation_storage:
            print(f"Generating ZIP from session storage for session {session_id}")
            # Use stored PDF buffers
            pdf_buffers = app._evaluation_storage[session_id]
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                success_count = 0
                for filename, pdf_data in pdf_buffers.items():
                    try:
                        if len(pdf_data) < 100:
                            print(f"Warning: PDF {filename} from session seems too small ({len(pdf_data)} bytes)")
                            continue
                            
                        zip_file.writestr(filename, pdf_data)
                        print(f"Added {filename} to ZIP from session storage ({len(pdf_data)} bytes)")
                        success_count += 1
                    except Exception as e:
                        print(f"Error adding {filename} from session to ZIP: {str(e)}")
                
                print(f"Successfully added {success_count} PDFs from session to ZIP file")
                if success_count == 0:
                    raise HTTPException(status_code=500, detail="Failed to add any PDFs from session to ZIP")
        else:
            raise HTTPException(status_code=400, detail="No evaluations provided and no session found")
        
        # Reset buffer position
        zip_buffer.seek(0)
        zip_content = zip_buffer.getvalue()
        
        print(f"ZIP file generated successfully. Size: {len(zip_content)} bytes")
        
        # Ensure the ZIP is not empty
        if len(zip_content) < 100:
            raise HTTPException(status_code=500, detail="Generated ZIP file is empty or corrupted")
        
        # Return the zip file
        return Response(
            content=zip_content,
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=evaluation_reports.zip"
            }
        )
    except Exception as e:
        print(f"Error generating ZIP: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/extract_text/")
async def extract_text_endpoint(file: UploadFile):
    """Extract text from a PDF or TXT file (for rubric)."""
    if not file.size:
        raise HTTPException(status_code=400, detail=f"Cannot read an empty file: '{file.filename}'.")
    
    # Check file extension explicitly
    filename = file.filename.lower()
    if not (filename.endswith('.txt') or filename.endswith('.pdf')):
        raise HTTPException(status_code=400, detail="Only .txt and .pdf files are supported for rubric extraction")
    
    try:
        # Force content type for .txt files if needed
        if filename.endswith('.txt') and file.content_type != 'text/plain':
            file.content_type = 'text/plain'
            
        text = await extract_text(file)
        return {"text": text}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/rubrics/")
async def list_rubrics():
    """List all saved rubrics."""
    try:
        rubrics = get_saved_rubrics()
        return {"rubrics": rubrics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/rubrics/{rubric_id}")
async def get_rubric(rubric_id: str):
    """Get a specific rubric by ID."""
    try:
        content = get_rubric_by_id(rubric_id)
        return {"id": rubric_id, "content": content}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.post("/rubrics/")
async def create_rubric(content: str = Form(...), name: Optional[str] = Form(None)):
    """Create a new rubric."""
    try:
        # Add name as first line if provided
        if name:
            content = f"{name}\n\n{content}"
            
        rubric_id = save_rubric(content)
        return {"id": rubric_id, "message": "Rubric saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.put("/rubrics/{rubric_id}")
async def update_rubric(rubric_id: str, content: str = Form(...), name: Optional[str] = Form(None)):
    """Update an existing rubric."""
    try:
        # Check if rubric exists
        get_rubric_by_id(rubric_id)
        
        # Add name as first line if provided
        if name:
            content = f"{name}\n\n{content}"
            
        save_rubric(content, rubric_id)
        return {"id": rubric_id, "message": "Rubric updated successfully"}
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Rubric with ID {rubric_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.delete("/rubrics/{rubric_id}")
async def remove_rubric(rubric_id: str):
    """Delete a rubric."""
    if delete_rubric(rubric_id):
        return {"message": "Rubric deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail=f"Rubric with ID {rubric_id} not found")

@app.get("/default-rubric/")
async def get_default_rubric():
    """Get the default rubric."""
    return {"content": DEFAULT_RUBRIC}

@app.post("/generate-rubric/")
async def generate_rubric(
    subject: str = Form(...), 
    level: str = Form(...),
    criteria_count: int = Form(5),
    api_key: str = Form(...)
):
    """Generate a new rubric using AI based on subject and education level."""
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required")
    
    if criteria_count < 3 or criteria_count > 10:
        criteria_count = 5  # Default to 5 if outside reasonable range
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        prompt = f"""
        Create a detailed academic rubric for evaluating essays on the subject of {subject} at the {level} level.
        
        The rubric should have exactly {criteria_count} criteria, each with a score range of 0-10.
        
        Format the rubric as follows:
        
        {subject} Essay Evaluation Rubric ({level} Level):
        
        1. [Criterion Name] (0-8):
           - [Description point 1]
           - [Description point 2]
           - [Description point 3]
        
        2. [Criterion Name] (0-2):
           - [Description point 1]
           - [Description point 2]
           - [Description point 3]
        
        ... and so on for all {criteria_count} criteria.
        
        Make the criteria specific to {subject} and appropriate for {level} level students.
        Each criterion should have 3-4 bullet points describing what is being evaluated.
        """
        
        response = await model.generate_content_async(prompt)
        rubric_text = response.text
        
        # Clean up the response if needed
        rubric_text = rubric_text.strip()
        
        return {
            "content": rubric_text,
            "subject": subject,
            "level": level
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating rubric: {str(e)}")

@app.post("/upload-rubric-file/")
async def upload_rubric_file(file: UploadFile):
    """Upload a rubric file (TXT or PDF) and return its content."""
    if not file.size:
        raise HTTPException(status_code=400, detail=f"Cannot read an empty file: '{file.filename}'.")
    
    # Check file extension explicitly (don't rely solely on content_type)
    filename = file.filename.lower()
    if not (filename.endswith('.txt') or filename.endswith('.pdf')):
        raise HTTPException(status_code=400, detail="Only .txt and .pdf files are supported for rubric upload")
    
    try:
        # Force content type for .txt files if needed
        if filename.endswith('.txt') and file.content_type != 'text/plain':
            file.content_type = 'text/plain'
        
        # Extract text from the file
        text = await extract_text(file)
        
        # Return the extracted text
        return {"text": text, "filename": file.filename}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)