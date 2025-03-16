#!/bin/bash
set -ex

echo "Environment test script"
echo "======================="

echo "Current directory: $(pwd)"
echo "Listing files in current directory:"
ls -la

echo "System information:"
uname -a

echo "Python information:"
which python3 || echo "python3 not found in PATH"
python3 --version || echo "Failed to get Python version"

echo "Pip information:"
python3 -m pip --version || echo "pip not found"

echo "Environment variables:"
env | sort

echo "Test completed successfully"
