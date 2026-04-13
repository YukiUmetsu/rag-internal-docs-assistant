from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq


load_dotenv()


def get_llm() -> ChatGroq:
    model_name = os.getenv("GROQ_MODEL_NAME")
    if not model_name:
        raise ValueError("GROQ_MODEL_NAME is not set in .env")

    return ChatGroq(
        model=model_name,
        temperature=0,
    )
