"""FastAPI entrypoint. Run with: uvicorn kbsearch_backend.__main__:app"""

from kbsearch_backend.factory import create_app

app = create_app()
