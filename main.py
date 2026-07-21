"""
main.py - Root Vercel entrypoint for Tasdeeq.
"""

import logging
import sys
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# 1. Add project root to sys.path BEFORE importing backend
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 2. Now import app from backend/main.py
from backend.main import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

FRONTEND_DIR = BASE_DIR / "frontend"

# 3. Mount static files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# 4. Serve index.html
@app.get("/", include_in_schema=False)
async def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": "index.html not found"}
