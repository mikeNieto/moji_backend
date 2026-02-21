"""
services/gemini.py — Singleton del modelo Gemini Flash Lite.

Uso:
    from services.gemini import get_model
    model = get_model()
"""

from langchain_google_genai import ChatGoogleGenerativeAI

from config import settings

_model: ChatGoogleGenerativeAI | None = None


def get_model() -> ChatGoogleGenerativeAI:
    """
    Devuelve la instancia singleton de ChatGoogleGenerativeAI.
    Se inicializa en el primer llamado y se reutiliza después.
    """
    global _model
    if _model is None:
        _model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
            temperature=settings.GEMINI_TEMPERATURE,
            streaming=True,
        )
    return _model


def reset_model() -> None:
    """Fuerza la reinicialización del singleton. Útil en tests."""
    global _model
    _model = None
