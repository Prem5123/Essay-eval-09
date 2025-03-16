#!/bin/bash
set -ex

echo "Current directory: $(pwd)"
echo "Listing files in current directory:"
ls -la

echo "Checking if Backend directory exists:"
if [ -d "Backend" ]; then
    echo "Backend directory found"
else
    echo "Backend directory not found"
    exit 1
fi

echo "Changing to Backend directory..."
cd Backend || { echo "Failed to change to Backend directory"; exit 1; }

echo "Listing files in Backend directory:"
ls -la

echo "Starting application..."
python3 main.py
