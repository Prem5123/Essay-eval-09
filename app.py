#!/usr/bin/env python3
"""
This is a simple entry point for the Essay Evaluator application.
It imports and runs the main FastAPI application from the Backend directory.
"""

import os
import sys

if __name__ == "__main__":
    # Add the Backend directory to the Python path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Backend"))
    
    # Change to the Backend directory
    os.chdir(os.path.join(os.path.dirname(__file__), "Backend"))
    
    # Import and run the main FastAPI application
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
