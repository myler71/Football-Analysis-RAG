"""Vercel FastAPI entrypoint.

Vercel's Python runtime loads the ASGI app from this module and routes every
request to it; `src.api.main` keeps serving the API, the SPA mount at /app and
the docs exactly as it does under Docker.
"""

from src.api.main import app  # noqa: F401
