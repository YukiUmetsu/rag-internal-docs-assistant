from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")
VECTORSTORE_PATH = os.getenv("VECTORSTORE_PATH")

if not EMBEDDING_MODEL_NAME:
    raise ValueError("EMBEDDING_MODEL_NAME is not set in .env")

if not VECTORSTORE_PATH:
    raise ValueError("VECTORSTORE_PATH is not set in .env")