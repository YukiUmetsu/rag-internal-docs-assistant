from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq


load_dotenv()

GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME")

if not GROQ_MODEL_NAME:
    raise ValueError("GROQ_MODEL_NAME is not set in .env")


def get_llm() -> ChatGroq:
    return ChatGroq(
        model=GROQ_MODEL_NAME,
        temperature=0,
    )