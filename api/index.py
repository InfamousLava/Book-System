# Vercel Serverless Function Entry Point
# This file wraps the Flask app for Vercel deployment

import sys
import os

# Add parent directory to path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set VERCEL environment flag
os.environ.setdefault('VERCEL', '1')

# Load environment variables from .env if available (for local testing)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import the Flask app - this is what Vercel's Python runtime uses as the handler
from app import app

# Vercel expects 'app' to be a WSGI application
