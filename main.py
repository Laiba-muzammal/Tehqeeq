"""
main.py

Root Vercel entrypoint for Tasdeeq.
Imports the FastAPI app from backend/main.py and mounts the static frontend.
"""

import logging
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Import the initialized FastAPI app from backend/main.py
from backend.main import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Locate project directories
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

# 1. Mount static assets (style.css, script.js) under /static
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    logger.info("Mounted frontend directory at /static")
else:
    logger.warning("Frontend directory not found at %s", FRONTEND_DIR)


# 2. Serve index.html directly at the root URL "/"
@app.get("/", include_in_schema=False)
async def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": "index.html not found in frontend directory."}
