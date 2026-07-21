import sys
from pathlib import Path

# Ensures the project root is in Python's search path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from Backend.main import app

# Vercel entrypoint
__all__ = ["app"]
