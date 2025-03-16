# Essay Evaluator Backend

This is the backend API for the Essay Evaluator application, built with FastAPI and Google's Generative AI.

## Features

- Essay evaluation using Google's Generative AI
- Custom rubric creation and management
- PDF report generation
- Support for multiple file formats (PDF, TXT, DOCX)

## Local Development

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file based on `.env.example` and add your Google API key
4. Run the development server:
   ```
   uvicorn main:app --reload
   ```

## Deployment on Render

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Configure the service:
   - **Name**: essay-evaluator-api (or your preferred name)
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app`
   - **Root Directory**: `Backend` (if your backend is in a subdirectory)

4. Add the following environment variables:
   - `GOOGLE_API_KEY`: Your Google Generative AI API key

5. Deploy the service

## API Endpoints

- `POST /evaluate/`: Evaluate an essay using a rubric
- `POST /extract_text/`: Extract text from a file
- `GET /rubrics/`: List all saved rubrics
- `GET /rubrics/{rubric_id}`: Get a specific rubric
- `POST /rubrics/`: Create a new rubric
- `PUT /rubrics/{rubric_id}`: Update a rubric
- `DELETE /rubrics/{rubric_id}`: Delete a rubric
- `GET /default-rubric/`: Get the default rubric
- `POST /generate-rubric/`: Generate a rubric using AI
- `POST /upload-rubric-file/`: Upload a rubric file

## CORS Configuration

By default, CORS is configured to allow requests from all origins. For production, update the `allow_origins` parameter in `main.py` to include only your frontend domain. 