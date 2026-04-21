from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq


load_dotenv()

DEFAULT_GROQ_MODEL_NAME = "meta-llama/llama-4-scout-17b-16e-instruct"


def get_llm() -> ChatGroq:
    model_name = os.getenv("GROQ_MODEL_NAME")
    if not model_name:
        raise ValueError("GROQ_MODEL_NAME is not set in .env")

    return ChatGroq(
        model=model_name,
        temperature=0,
    )


def get_judge_llm() -> ChatGroq:
    model_name = os.getenv("GROQ_JUDGE_MODEL_NAME", DEFAULT_GROQ_MODEL_NAME)

    return ChatGroq(
        model=model_name,
        temperature=0,
    )
