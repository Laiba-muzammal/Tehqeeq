"""
main.py - Root Vercel entrypoint for Tasdeeq.
"""

import logging
import sys
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# 1. Add project root directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 2. Check for capitalized 'Backend' or lowercase 'backend' directory
if (BASE_DIR / "Backend").exists():
    from Backend.main import app
elif (BASE_DIR / "backend").exists():
    from backend.main import app
else:
    raise ImportError("Neither 'Backend' nor 'backend' directory was found.")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 3. Locate Frontend directory (checks both Frontend and frontend)
FRONTEND_DIR = BASE_DIR / "Frontend"
if not FRONTEND_DIR.exists():
    FRONTEND_DIR = BASE_DIR / "frontend"

# 4. Mount static assets (style.css, script.js) under /static
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    logger.info("Mounted frontend static directory from %s", FRONTEND_DIR)
else:
    logger.warning("Frontend directory not found!")


# 5. Serve index.html directly at the root URL "/"
@app.get("/", include_in_schema=False)
async def serve_index():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": f"index.html not found at {index_path}"}
