"""
main.py - Root Vercel entrypoint for Tasdeeq API & Frontend.
"""

import logging
import sys
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# 1. Add root directory to sys.path explicitly
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 2. Match exact folder capitalization 'Backend'
from Backend.main import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 3. Match exact folder capitalization 'Frontend'
FRONTEND_DIR = BASE_DIR / "Frontend"

# 4. Mount CSS and JS files static directory
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# 5. Serve index.html on root "/"
@app.get("/", include_in_schema=False)
async def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": f"index.html not found at {index_path}"}
