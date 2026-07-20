"""Compatibility ASGI entrypoint for uvicorn main:app.

This keeps the existing root-level launch command working while the real
application code lives in Backend.main.
"""

from Backend.main import app
