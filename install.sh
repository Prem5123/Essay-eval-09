#!/bin/bash
set -ex

echo "Current directory: $(pwd)"
echo "Listing files in current directory:"
ls -la

echo "Python version:"
python3 --version || echo "Python3 not found"

echo "Checking if requirements.txt exists:"
if [ -f "requirements.txt" ]; then
    echo "requirements.txt found"
else
    echo "requirements.txt not found"
    # Try to find requirements.txt in subdirectories
    find . -name "requirements.txt" -type f
    # Copy from Backend if it exists there
    if [ -f "Backend/requirements.txt" ]; then
        echo "Found requirements.txt in Backend directory, copying to root"
        cp Backend/requirements.txt .
    else
        echo "Could not find requirements.txt anywhere"
        exit 1
    fi
fi

echo "Updating pip..."
python3 -m pip install --upgrade pip || echo "Failed to upgrade pip"

# Install virtualenv
echo "Installing virtualenv..."
python3 -m pip install virtualenv

# Create and activate virtual environment
echo "Creating virtual environment..."
python3 -m virtualenv venv
echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing requirements in virtual environment..."
pip install -r requirements.txt

# Verify installations
echo "Verifying installations..."
python -c "import fastapi; print(f'FastAPI version: {fastapi.__version__}')" || echo "FastAPI not installed correctly"
python -c "import uvicorn; print(f'Uvicorn version: {uvicorn.__version__}')" || echo "Uvicorn not installed correctly"
python -c "import pydantic; print(f'Pydantic version: {pydantic.__version__}')" || echo "Pydantic not installed correctly"

# Create a simple test file to verify imports
cat > test_imports.py << EOF
try:
    import fastapi
    import uvicorn
    import pydantic
    import pdfplumber
    import python_multipart
    import docx
    import google.generativeai
    import reportlab
    import gunicorn
    print("All imports successful!")
except ImportError as e:
    print(f"Import error: {e}")
EOF

echo "Testing imports..."
python test_imports.py

# Create a script to activate the virtual environment
cat > activate_venv.sh << EOF
#!/bin/bash
source venv/bin/activate
EOF

chmod +x activate_venv.sh
