"""
services/expression.py — Parser de emotion tags y mapeo a OpenMoji.

El LLM emite el primer token de cada respuesta en formato [emotion:TAG].
Esta función extrae el tag y devuelve (tag, texto_restante) para que
el WebSocket pueda enviar la emoción inmediatamente al cliente.

Uso:
    from services.expression import parse_emotion_tag, emotion_to_emojis

    tag, rest = parse_emotion_tag("[emotion:happy] Hola, ¿cómo estás?")
    # tag = "happy", rest = "Hola, ¿cómo estás?"

    emojis = emotion_to_emojis("happy")
    # ["1F600", "1F603", "1F604", "1F60A"]
"""

import re

# ── Regex para el emotion tag ─────────────────────────────────────────────────

_EMOTION_RE = re.compile(r"^\[emotion:([a-zA-Z_]+)\]\s*", re.ASCII)

# Tags válidos (§3.7)
VALID_TAGS: frozenset[str] = frozenset(
    [
        "happy",
        "excited",
        "sad",
        "empathy",
        "confused",
        "surprised",
        "love",
        "cool",
        "greeting",
        "neutral",
        "curious",
        "worried",
        "playful",
    ]
)

# ── Mapeo emotion → códigos Unicode OpenMoji (§3.7) ───────────────────────────

EMOTION_TO_EMOJIS: dict[str, list[str]] = {
    "happy": ["1F600", "1F603", "1F604", "1F60A"],
    "excited": ["1F929", "1F389", "1F38A", "2728"],
    "sad": ["1F622", "1F625", "1F62D"],
    "empathy": ["1F97A", "1F615", "2764"],
    "confused": ["1F615", "1F914", "2753"],
    "surprised": ["1F632", "1F62E", "1F92F"],
    "love": ["2764", "1F60D", "1F970", "1F498"],
    "cool": ["1F60E", "1F44D", "1F525"],
    "greeting": ["1F44B", "1F917"],
    "neutral": ["1F642", "1F916"],
    "curious": ["1F9D0", "1F50D"],
    "worried": ["1F61F", "1F628"],
    "playful": ["1F61C", "1F609", "1F638"],
}

# Estados fijos (no vienen del LLM, pero útiles para el cliente)
FIXED_STATE_EMOJIS: dict[str, str] = {
    "IDLE": "1F916",
    "LISTENING": "1F442",
    "THINKING": "1F914",
    "ERROR": "1F615",
    "DISCONNECTED": "1F50C",
}


# ── Funciones públicas ────────────────────────────────────────────────────────


def parse_emotion_tag(text: str) -> tuple[str, str]:
    """
    Intenta extraer un [emotion:TAG] del comienzo de `text`.

    Devuelve (tag, remaining_text):
      - Si hay match y el tag es válido: (tag, texto_sin_el_tag)
      - Si el tag no es reconocido pero el formato es correcto: ("neutral", texto_sin_el_tag)
      - Si no hay match: ("neutral", text_original_sin_modificar)

    Ejemplos:
        parse_emotion_tag("[emotion:happy] Hola!")  → ("happy", "Hola!")
        parse_emotion_tag("[emotion:UNKNOWN] Hey")  → ("neutral", "Hey")
        parse_emotion_tag("Hola sin tag")           → ("neutral", "Hola sin tag")
        parse_emotion_tag("[emotion:sad]")           → ("sad", "")
    """
    m = _EMOTION_RE.match(text)
    if m is None:
        return ("neutral", text)

    tag = m.group(1).lower()
    remaining = text[m.end() :]

    if tag not in VALID_TAGS:
        tag = "neutral"

    return (tag, remaining)


def emotion_to_emojis(tag: str) -> list[str]:
    """
    Devuelve la lista de códigos Unicode OpenMoji para el tag dado.
    Si el tag no existe, devuelve la lista de "neutral".
    """
    return EMOTION_TO_EMOJIS.get(tag, EMOTION_TO_EMOJIS["neutral"])


# ── parse_emojis_tag ──────────────────────────────────────────────────────────

_EMOJIS_TAG_RE = re.compile(r"^\[emojis:([^\]]+)\]\s*", re.IGNORECASE)


def parse_emojis_tag(text: str) -> tuple[list[str], str]:
    """
    Extrae [emojis:CODE1,CODE2,...] del inicio del texto.

    Los códigos son codepoints Unicode en formato OpenMoji: mayúsculas, guión para
    ZWJ/variation sequences (p.ej. "1F1EB-1F1F7", "2708-FE0F", "1F600").

    Devuelve (lista_de_codigos, texto_restante).
    Si no hay tag al inicio, devuelve ([], text sin modificar).

    Ejemplos:
        parse_emojis_tag("[emojis:1F1EB-1F1F7,2708] Francia")  → (["1F1EB-1F1F7","2708"], "Francia")
        parse_emojis_tag("Sin tag")                            → ([], "Sin tag")
    """
    m = _EMOJIS_TAG_RE.match(text)
    if not m:
        return [], text
    codes = [c.strip().upper() for c in m.group(1).split(",") if c.strip()]
    return codes, text[m.end() :]
