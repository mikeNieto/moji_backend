"""
services/intent.py — Clasificación de intención de captura en la respuesta del LLM.

Detecta si el texto generado por Gemini implica una solicitud de:
  - "photo_request" — el agente quiere capturar una foto
  - "video_request" — el agente quiere capturar un video
  - None           — ninguna captura necesaria

La clasificación se basa en palabras clave del texto generado.
En iteraciones futuras se puede reemplazar por una llamada a Gemini.

Uso:
    from services.intent import classify_intent

    intent = classify_intent("Déjame ver cómo estás, ¿puedes mostrarme tu cara?")
    # "photo_request"

    intent = classify_intent("Muéstrame qué está pasando ahí")
    # "video_request"

    intent = classify_intent("Hola, ¿cómo estás hoy?")
    # None
"""

# ── Palabras clave por intención ──────────────────────────────────────────────

_PHOTO_KEYWORDS: frozenset[str] = frozenset(
    [
        # Español
        "toma una foto",
        "saca una foto",
        "haz una foto",
        "captura una imagen",
        "hazme una foto",
        "toma una imagen",
        "fotografía",
        "fotografia",
        "puedo ver",
        "déjame ver",
        "déjame verte",
        "muéstrame tu cara",
        "mostrarme tu cara",
        "mostrarme tu rostro",
        "enseñame tu cara",
        "enseñame tu rostro",
        "captura una foto",
        # Inglés
        "take a photo",
        "take a picture",
        "snap a photo",
        "snap a picture",
        "capture a photo",
        "capture an image",
        "let me see you",
        "show me your face",
        "let me see your face",
    ]
)

_VIDEO_KEYWORDS: frozenset[str] = frozenset(
    [
        # Español
        "graba un video",
        "graba un vídeo",
        "toma un video",
        "toma un vídeo",
        "filma",
        "captura un video",
        "captura un vídeo",
        "grabar un video",
        "grabar un vídeo",
        "muéstrame lo que",
        "mostrarme lo que",
        "qué está pasando",
        "que esta pasando",
        "muéstrame qué",
        "grábame",
        "grabame",
        "registra un video",
        "registra un vídeo",
        # Inglés
        "record a video",
        "take a video",
        "capture a video",
        "film this",
        "show me what",
        "what's happening",
        "what is happening",
        "let me see what",
    ]
)


# ── Función pública ───────────────────────────────────────────────────────────


def classify_intent(response_text: str) -> str | None:
    """
    Analiza `response_text` (texto generado por Gemini) y devuelve:
      - "photo_request" si el texto implica captura de foto
      - "video_request" si implica captura de video
      - None si no detecta ninguna intención de captura

    Nota: video_request se comprueba primero ya que "video" es más específico
    que "foto". Si aparecen ambas intenciones, se prioriza video.
    """
    lower = response_text.lower()

    # Comprobar video antes que foto (mayor especificidad)
    if any(kw in lower for kw in _VIDEO_KEYWORDS):
        return "video_request"

    if any(kw in lower for kw in _PHOTO_KEYWORDS):
        return "photo_request"

    return None
