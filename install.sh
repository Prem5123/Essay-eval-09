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

echo "Installing requirements..."
if ! python3 -m pip install -r requirements.txt; then
    echo "Bulk installation failed, trying one by one..."
    while read -r package; do
        # Skip empty lines and comments
        [[ -z "$package" || "$package" =~ ^#.*$ ]] && continue
        echo "Installing $package..."
        python3 -m pip install "$package" || echo "Failed to install $package"
    done < requirements.txt
fi
