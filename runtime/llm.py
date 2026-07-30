import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


def get_llm(timeout: float | None = None) -> ChatOpenAI | None:
    """Initialize and return a ChatOpenAI client instance based on environment variables.

    Returns None if LLM_API_KEY / OPENAI_API_KEY is not configured or DITING_MOCK_MODE is enabled.
    """
    mock_mode = os.getenv("DITING_MOCK_MODE", "").lower() in ("true", "1", "yes")
    if mock_mode:
        return None

    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_API_BASE")
    model = os.getenv("LLM_MODEL", "Qwen/Qwen3.5-35B-A3B")

    if timeout is None:
        env_timeout = os.getenv("LLM_TIMEOUT")
        req_timeout = float(env_timeout) if env_timeout else 120.0
    else:
        req_timeout = timeout

    max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))

    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=0.1,
        request_timeout=req_timeout,
        max_retries=max_retries,
    )
