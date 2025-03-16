FROM python:3.10-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Set environment variables
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Expose the port
EXPOSE 8000

# Start the application
CMD ["python", "Backend/main.py"]
