from fastapi import FastAPI, UploadFile, Form, HTTPException, Response, Body
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO
from docx import Document
import google.generativeai as genai
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
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

async def evaluate_essay(essay_text: str, rubric_text: str | None, api_key: str) -> dict:
    """Evaluate an essay using the Gemini API."""
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

    prompt = f"""
    Evaluate the following essay based on the provided rubric. Provide an overall score and detailed feedback.
    
    IMPORTANT INSTRUCTIONS:
    1. Use ONLY the criteria specified in the rubric below.
    2. Do NOT add any additional criteria that are not in the rubric.
    3. Do NOT modify, rename, or reinterpret any criteria from the rubric.
    4. Score each criterion according to its specified scale in the rubric (e.g., 0-10, 0-5, etc.).
    5. The overall_score should be the sum of all individual criteria scores.
    6. Use the EXACT names of the criteria as they appear in the rubric.

    RUBRIC:
    {rubric}

    ESSAY:
    {essay_text}

    Respond with JSON format:
    {{
        "overall_score": float (0-{max_score}),
        "criteria": [
            {{
                "name": str,
                "score": float,
                "max_score": int,
                "feedback": str
            }}
        ],
        "suggestions": [str]
    }}
    """
    
    # If we successfully extracted criteria names and max scores, add them explicitly to ensure model follows them
    if 'criteria_names' in locals() and criteria_names and 'criteria_max_scores' in locals() and criteria_max_scores:
        prompt += f"\n\nYou MUST use EXACTLY these {len(criteria_names)} criteria with their EXACT names and max scores:\n"
        for i, (name, max_score) in enumerate(zip(criteria_names, criteria_max_scores)):
            prompt += f"{i+1}. {name} (0-{max_score})\n"
    
    try:
        response = await client.send_message_async(prompt)
        cleaned_response = re.sub(r'```json|```', '', response.text).strip()
        result = json.loads(cleaned_response)
        
        # Ensure each criterion has a max_score field
        for i, criterion in enumerate(result['criteria']):
            if 'max_score' not in criterion:
                if i < len(criteria_max_scores):
                    criterion['max_score'] = criteria_max_scores[i]
                else:
                    criterion['max_score'] = max_score_per_criterion
        
        # Validate the result has the correct number of criteria
        if len(result['criteria']) != criteria_count:
            # If we have the criteria names, we can fix this by keeping only the correct ones
            if 'criteria_names' in locals() and criteria_names:
                # Keep only criteria that match our extracted names exactly
                correct_criteria = []
                for i, name in enumerate(criteria_names):
                    # Find the matching criterion or create a default one
                    matching = next((c for c in result['criteria'] if c['name'].lower() == name.lower()), None)
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
                result['criteria'] = result['criteria'][:criteria_count]
        else:
            # Even if count is correct, ensure names match exactly
            if 'criteria_names' in locals() and criteria_names:
                for i, name in enumerate(criteria_names):
                    if i < len(result['criteria']):
                        result['criteria'][i]['name'] = name
                        # Also ensure max_score is correct
                        if i < len(criteria_max_scores):
                            result['criteria'][i]['max_score'] = criteria_max_scores[i]
        
        # Recalculate the overall score based on criteria
        criteria_sum = sum(criterion['score'] for criterion in result['criteria'])
        result['overall_score'] = criteria_sum
            
        return result
    except json.JSONDecodeError:
        raise ValueError("Failed to parse Gemini API response as JSON.")
    except Exception as e:
        raise ValueError(f"Error in Gemini API call: {str(e)}")

# PDF Report Generation Class
class PDFReport:
    # Enhanced color palette
    HEADER_COLOR = colors.HexColor('#1e3a8a')  # Deep blue
    ACCENT_COLOR = colors.HexColor('#3b82f6')  # Blue
    LIGHT_BG = colors.HexColor('#f3f4f6')      # Light gray
    SUCCESS_COLOR = colors.HexColor('#10b981') # Green
    WARNING_COLOR = colors.HexColor('#f59e0b') # Amber
    DANGER_COLOR = colors.HexColor('#ef4444')  # Red
    PURPLE_COLOR = colors.HexColor('#8b5cf6')  # Purple
    PINK_COLOR = colors.HexColor('#ec4899')    # Pink
    TEAL_COLOR = colors.HexColor('#14b8a6')    # Teal
    INDIGO_COLOR = colors.HexColor('#6366f1')  # Indigo
    
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

    def _calculate_max_score(self, criteria):
        """Calculate the maximum possible score based on criteria."""
        # Sum up the max_score for each criterion
        return sum(criterion.get('max_score', 10) for criterion in criteria)

    def _build_header(self, data, elements):
        # Calculate max score based on criteria max scores
        max_score = self._calculate_max_score(data['criteria'])
        
        # Format the score with one decimal place
        score = round(data['overall_score'], 1)
        
        # Get score color
        score_color = self._get_score_color(score, max_score)
        
        # Create a colorful header
        title = Paragraph(
            f"<font size='18' color='{self.HEADER_COLOR.hexval()}'>Essay Evaluation Report</font><br/>"
            f"<font size='12'>Overall Score: "
            f"<font color='{score_color.hexval()}'><b>{score}</b></font>/{max_score}</font>",
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
        return elements

    def _build_criteria_table(self, criteria, elements, available_width):
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
        
        # Create alternating row colors with more vibrant colors
        row_colors = []
        color_pairs = [
            (colors.white, self.LIGHT_BG),
            (colors.HexColor('#f0f9ff'), colors.HexColor('#e0f2fe')),  # Light blue
            (colors.HexColor('#f0fdf4'), colors.HexColor('#dcfce7')),  # Light green
            (colors.HexColor('#fef2f2'), colors.HexColor('#fee2e2')),  # Light red
            (colors.HexColor('#faf5ff'), colors.HexColor('#f3e8ff')),  # Light purple
        ]
        
        # Choose one color pair for consistency
        bg_colors = color_pairs[1]  # Light blue pair
        
        for i in range(len(criteria)):
            if i % 2 == 0:
                row_colors.append(bg_colors[0])
            else:
                row_colors.append(bg_colors[1])
        
        table_style.append(('ROWBACKGROUNDS', (0,1), (-1,-1), row_colors))
        
        # Add each criterion row with controlled height
        for crit in criteria:
            score = crit['score']
            max_score = crit.get('max_score', 10)  # Default to 10 if not specified
            score_color = self._get_score_color(score, max_score)
            
            # Limit feedback length to prevent overflow
            feedback = crit['feedback']
            if len(feedback) > 800:  # Allow longer feedback
                feedback = feedback[:797] + "..."
            
            # Format score with color
            score_cell = Paragraph(
                f"<font color='{score_color.hexval()}'><b>{score}</b></font>/{max_score}",
                self.styles['TableBody']
            )
            
            # Create a more readable feedback cell
            feedback_cell = Paragraph(
                feedback,
                self.styles['FeedbackText']
            )
            
            rows.append([
                Paragraph(f"<b>{crit['name']}</b>", self.styles['TableBody']),
                score_cell,
                feedback_cell
            ])

        # Calculate column widths with better proportions for feedback
        available_width = min(available_width, 520)  # Ensure we don't exceed page width
        col_widths = [
            available_width * 0.22,  # Criteria column (22%)
            available_width * 0.13,  # Score column (13%)
            available_width * 0.65   # Feedback column (65%)
        ]
        
        # Create table with split option to handle page breaks
        table = Table(
            rows, 
            colWidths=col_widths,
            style=table_style,
            repeatRows=1,  # Repeat header row on each page
            splitByRow=1    # Allow table to split across pages
        )
        
        elements.append(table)
        elements.append(Spacer(1, 20))
        return elements

    def _build_suggestions(self, suggestions, elements):
        elements.append(Paragraph(
            f"<font color='{self.PURPLE_COLOR.hexval()}'>Improvement Suggestions</font>",
            self.styles['SuggestionTitle']
        ))
        elements.append(Spacer(1, 10))
        
        # Create a colorful box for suggestions
        suggestion_data = []
        
        for i, suggestion in enumerate(suggestions):
            # Alternate colors for suggestion bullets
            colors_list = [self.ACCENT_COLOR, self.PURPLE_COLOR, self.TEAL_COLOR, self.INDIGO_COLOR, self.PINK_COLOR]
            color = colors_list[i % len(colors_list)]
            
            bullet_text = Paragraph(
                f"<font color='{color.hexval()}'><b>{i+1}.</b></font> {suggestion}",
                self.styles['SuggestionItem']
            )
            suggestion_data.append([bullet_text])
        
        # Create a table for suggestions with alternating background colors
        if suggestion_data:
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
        
        elements.append(Spacer(1, 20))
        
        # Add a footer with a motivational message
        elements.append(
            Paragraph(
                "Keep improving! Every essay is a step toward mastery.",
                self.styles['Footer']
            )
        )
        
        return elements

    def create(self, data) -> BytesIO:
        buffer = BytesIO()
        
        # Set up the document with proper page size and margins
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter,
            leftMargin=0.4*inch,
            rightMargin=0.4*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
            allowSplitting=1  # Enable content splitting across pages
        )
        
        # Process data to prevent overflow issues
        processed_data = self._preprocess_data(data)
        
        elements = []
        self._build_header(processed_data, elements)
        self._build_criteria_table(processed_data['criteria'], elements, doc.width)
        self._build_suggestions(processed_data['suggestions'], elements)
        
        try:
            doc.build(elements)
        except Exception as e:
            # Fallback to a simpler report if the build fails
            buffer.seek(0)
            buffer.truncate(0)
            self._build_simple_report(processed_data, buffer)
            
        buffer.seek(0)
        return buffer
        
    def _preprocess_data(self, data):
        """Preprocess data to prevent overflow issues."""
        processed = data.copy()
        
        # Ensure criteria list isn't too long
        if len(processed['criteria']) > 10:
            processed['criteria'] = processed['criteria'][:10]
            
        # Ensure suggestions list isn't too long
        if len(processed['suggestions']) > 5:
            processed['suggestions'] = processed['suggestions'][:5]
            
        # Limit text length in criteria
        for crit in processed['criteria']:
            if len(crit['name']) > 100:
                crit['name'] = crit['name'][:97] + "..."
                
            # Allow longer feedback but still limit it
            if len(crit['feedback']) > 1000:
                crit['feedback'] = crit['feedback'][:997] + "..."
                
        # Limit text length in suggestions
        processed['suggestions'] = [
            s[:500] + "..." if len(s) > 500 else s 
            for s in processed['suggestions']
        ]
        
        return processed
        
    def _build_simple_report(self, data, buffer):
        """Build a simplified report as fallback."""
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=letter,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        elements = []
        
        # Simple title
        title_style = ParagraphStyle(
            'SimpleTitle',
            fontName=self.BOLD_FONT,
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=self.HEADER_COLOR
        )
        elements.append(Paragraph(
            f"Essay Evaluation Report (Score: {data['overall_score']})",
            title_style
        ))
        
        # Simple criteria list
        for crit in data['criteria']:
            score_color = self._get_score_color(crit['score'])
            elements.append(Paragraph(
                f"<b>{crit['name']}</b>: <font color='{score_color.hexval()}'>{crit['score']}</font>/10",
                self.styles['Normal']
            ))
            elements.append(Paragraph(
                crit['feedback'],
                self.styles['BodyText']
            ))
            elements.append(Spacer(1, 12))
        
        # Simple suggestions
        if data['suggestions']:
            elements.append(Paragraph(
                f"<font color='{self.PURPLE_COLOR.hexval()}'><b>Suggestions:</b></font>",
                self.styles['Normal']
            ))
            for i, suggestion in enumerate(data['suggestions']):
                elements.append(Paragraph(
                    f"{i+1}. {suggestion}",
                    self.styles['BodyText']
                ))
                
        doc.build(elements)

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
        genai.configure(api_key=api_key)
        models = genai.list_models()  # Test the API key
        print(f"API key verification successful. Found {len(models)} models.")
        return {"status": "success", "message": "API key is valid"}
    except Exception as e:
        print(f"API key verification failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid API key: {str(e)}")

@app.post("/evaluate/")
async def evaluate_essay_endpoint(
    essay: UploadFile, 
    api_key: str = Form(...), 
    rubric_text: Optional[str] = Form(None),
    rubric_id: Optional[str] = Form(None)
):
    """Evaluate an essay and return a PDF report."""
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
        evaluation = await evaluate_essay(essay_text, rubric_text, api_key)
        pdf_buffer = pdf_report.create(evaluation)
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=evaluation_report.pdf",
                "X-Essay-Score": str(evaluation['overall_score'])
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
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