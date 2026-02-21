"""
Tests unitarios para los servicios de IA (paso 5).

Tests cubiertos:
  - services/expression.py: parse_emotion_tag + emotion_to_emojis
  - services/movement.py:   build_move_sequence
  - services/history.py:    add_message, get_history, compact_if_needed (mockado)
  - services/intent.py:     classify_intent
  - services/gemini.py:     singleton reset (sin llamada a API)

No se hacen llamadas reales a la API de Gemini.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import db as db_module
from db import create_all_tables, drop_all_tables
from services.expression import (
    EMOTION_TO_EMOJIS,
    VALID_TAGS,
    emotion_to_emojis,
    parse_emotion_tag,
)
from services.history import ConversationHistory
from services.intent import classify_intent
from services.movement import build_move_sequence


# ── Fixture: BD en memoria para ConversationHistory ───────────────────────────


@pytest.fixture(autouse=True)
async def in_memory_db():
    db_module.init_db("sqlite+aiosqlite:///:memory:")
    await create_all_tables()
    yield
    await drop_all_tables()
    if db_module.engine is not None:
        await db_module.engine.dispose()


# ── parse_emotion_tag ─────────────────────────────────────────────────────────


class TestParseEmotionTag:
    def test_happy_tag_extracted(self):
        tag, rest = parse_emotion_tag("[emotion:happy] Hola, ¿cómo estás?")
        assert tag == "happy"
        assert rest == "Hola, ¿cómo estás?"

    def test_empathy_tag_extracted(self):
        tag, rest = parse_emotion_tag("[emotion:empathy] Lo siento mucho.")
        assert tag == "empathy"
        assert rest == "Lo siento mucho."

    def test_tag_without_trailing_text(self):
        tag, rest = parse_emotion_tag("[emotion:sad]")
        assert tag == "sad"
        assert rest == ""

    def test_tag_with_extra_spaces_stripped(self):
        tag, rest = parse_emotion_tag("[emotion:excited]   Genial!")
        assert tag == "excited"
        assert rest == "Genial!"

    def test_no_tag_returns_neutral(self):
        tag, rest = parse_emotion_tag("Texto sin etiqueta")
        assert tag == "neutral"
        assert rest == "Texto sin etiqueta"

    def test_unknown_tag_returns_neutral(self):
        tag, rest = parse_emotion_tag("[emotion:superalien] Hey!")
        assert tag == "neutral"
        assert rest == "Hey!"

    def test_case_insensitive_tag(self):
        tag, rest = parse_emotion_tag("[emotion:HAPPY] Hola!")
        assert tag == "happy"
        assert rest == "Hola!"

    def test_greeting_tag(self):
        tag, _ = parse_emotion_tag("[emotion:greeting] Buenos días!")
        assert tag == "greeting"

    def test_curious_tag(self):
        tag, rest = parse_emotion_tag("[emotion:curious] ¿Qué tienes ahí?")
        assert tag == "curious"
        assert rest == "¿Qué tienes ahí?"

    def test_empty_string(self):
        tag, rest = parse_emotion_tag("")
        assert tag == "neutral"
        assert rest == ""

    def test_tag_in_middle_not_extracted(self):
        text = "Hola [emotion:happy] esto no está al inicio"
        tag, rest = parse_emotion_tag(text)
        assert tag == "neutral"
        assert rest == text  # no se modifica

    def test_all_valid_tags_recognized(self):
        for valid_tag in VALID_TAGS:
            tag, _ = parse_emotion_tag(f"[emotion:{valid_tag}] Test")
            assert tag == valid_tag, f"Tag {valid_tag!r} no reconocido"

    def test_playful_tag(self):
        tag, rest = parse_emotion_tag("[emotion:playful] ¡Ja ja ja!")
        assert tag == "playful"
        assert rest == "¡Ja ja ja!"

    def test_worried_tag(self):
        tag, rest = parse_emotion_tag("[emotion:worried] Espero que estés bien.")
        assert tag == "worried"
        assert rest == "Espero que estés bien."


# ── emotion_to_emojis ─────────────────────────────────────────────────────────


class TestEmotionToEmojis:
    def test_happy_returns_list(self):
        emojis = emotion_to_emojis("happy")
        assert isinstance(emojis, list)
        assert len(emojis) > 0
        assert "1F600" in emojis

    def test_unknown_tag_returns_neutral(self):
        emojis = emotion_to_emojis("nonexistent_tag")
        assert emojis == EMOTION_TO_EMOJIS["neutral"]

    def test_all_valid_tags_have_emojis(self):
        for tag in VALID_TAGS:
            emojis = emotion_to_emojis(tag)
            assert len(emojis) > 0, f"Tag {tag!r} no tiene emojis"

    def test_love_contains_heart(self):
        assert "2764" in emotion_to_emojis("love")

    def test_excited_contains_sparkle(self):
        assert "2728" in emotion_to_emojis("excited")


# ── build_move_sequence ───────────────────────────────────────────────────────


class TestBuildMoveSequence:
    def test_total_duration_sum(self):
        steps = [
            {"action": "rotate", "duration_ms": 500},
            {"action": "pause", "duration_ms": 200},
            {"action": "rotate", "duration_ms": 300},
        ]
        result = build_move_sequence("Giro", steps)
        assert result["total_duration_ms"] == 1000

    def test_empty_steps(self):
        result = build_move_sequence("Nada", [])
        assert result["total_duration_ms"] == 0
        assert result["step_count"] == 0

    def test_description_preserved(self):
        result = build_move_sequence("Saludo de bienvenida", [])
        assert result["description"] == "Saludo de bienvenida"

    def test_steps_preserved(self):
        steps = [{"action": "wave", "duration_ms": 800, "direction": "right"}]
        result = build_move_sequence("Wave", steps)
        assert result["steps"] == steps

    def test_step_count(self):
        steps = [{"action": "a", "duration_ms": 100}] * 5
        result = build_move_sequence("Five steps", steps)
        assert result["step_count"] == 5

    def test_missing_duration_ms_treated_as_zero(self):
        steps = [
            {"action": "rotate", "duration_ms": 400},
            {"action": "led_on"},  # sin duration_ms
        ]
        result = build_move_sequence("Mixed", steps)
        assert result["total_duration_ms"] == 400

    def test_large_sequence(self):
        steps = [{"action": "move", "duration_ms": 1000} for _ in range(10)]
        result = build_move_sequence("Long", steps)
        assert result["total_duration_ms"] == 10000

    def test_returns_dict_with_required_keys(self):
        result = build_move_sequence("Test", [])
        assert "description" in result
        assert "steps" in result
        assert "total_duration_ms" in result
        assert "step_count" in result


# ── ConversationHistory ───────────────────────────────────────────────────────


class TestConversationHistory:
    async def test_add_and_get(self):
        history = ConversationHistory()
        await history.add_message("sess1", "user", "Hola Robi")
        await history.add_message("sess1", "assistant", "[emotion:greeting] Hola!")

        msgs = history.get_history("sess1")
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "Hola Robi"}
        assert msgs[1] == {"role": "assistant", "content": "[emotion:greeting] Hola!"}

    async def test_empty_session_returns_empty_list(self):
        history = ConversationHistory()
        msgs = history.get_history("nonexistent_session")
        assert msgs == []

    async def test_multiple_sessions_isolated(self):
        history = ConversationHistory()
        await history.add_message("sess_a", "user", "Mensaje A")
        await history.add_message("sess_b", "user", "Mensaje B")

        msgs_a = history.get_history("sess_a")
        msgs_b = history.get_history("sess_b")
        assert len(msgs_a) == 1
        assert len(msgs_b) == 1
        assert msgs_a[0]["content"] == "Mensaje A"
        assert msgs_b[0]["content"] == "Mensaje B"

    async def test_get_history_format(self):
        history = ConversationHistory()
        await history.add_message("sess1", "user", "Pregunta")
        msgs = history.get_history("sess1")
        assert set(msgs[0].keys()) == {"role", "content"}

    async def test_compact_if_needed_below_threshold(self):
        """Sin llegar al umbral, compact_if_needed no lanza tarea."""
        history = ConversationHistory()
        for i in range(5):
            await history.add_message("sess1", "user", f"Msg {i}")

        # Parchear create_task para verificar que NO se llama
        with patch("services.history.asyncio.create_task") as mock_task:
            await history.compact_if_needed("sess1")
            mock_task.assert_not_called()

    async def test_compact_if_needed_at_threshold(self):
        """Al llegar al umbral (20), sí debe lanzar la tarea."""
        history = ConversationHistory()
        # Añadir exactamente CONVERSATION_COMPACTION_THRESHOLD mensajes
        from config import settings

        for i in range(settings.CONVERSATION_COMPACTION_THRESHOLD):
            await history.add_message("sess1", "user", f"Msg {i}")

        def _close_coro(coro, **kwargs):
            coro.close()  # cierra el coroutine para evitar RuntimeWarning
            return MagicMock()

        with patch(
            "services.history.asyncio.create_task", side_effect=_close_coro
        ) as mock_task:
            await history.compact_if_needed("sess1")
            mock_task.assert_called_once()

    async def test_compact_updates_cache(self):
        """_compact debe reducir el historial en memoria."""
        history = ConversationHistory()

        for i in range(10):
            role = "user" if i % 2 == 0 else "assistant"
            await history.add_message("sess1", role, f"Mensaje {i}")

        # Mockear Gemini para que devuelva un resumen
        mock_response = MagicMock()
        mock_response.content = "Resumen de la conversación"

        mock_model = MagicMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        with patch("services.history.get_model", return_value=mock_model):
            await history._compact("sess1")

        msgs = history.get_history("sess1")
        # Debe contener el resumen + los últimos 5 mensajes (keep=5)
        assert len(msgs) == 6  # 1 resumen + 5 últimos
        assert "[RESUMEN]" in msgs[0]["content"]

    async def test_load_from_db(self):
        """load_from_db recupera el historial persistido."""
        h1 = ConversationHistory()
        await h1.add_message("sess_load", "user", "Persistido")
        await h1.add_message("sess_load", "assistant", "Respuesta")

        # Nueva instancia sin caché — carga desde BD
        h2 = ConversationHistory()
        await h2.load_from_db("sess_load")
        msgs = h2.get_history("sess_load")
        assert len(msgs) == 2
        assert msgs[0]["content"] == "Persistido"


# ── classify_intent ───────────────────────────────────────────────────────────


class TestClassifyIntent:
    def test_no_intent_returns_none(self):
        assert classify_intent("Hola, ¿cómo estás hoy?") is None

    def test_photo_request_spanish(self):
        assert classify_intent("Toma una foto de esto") == "photo_request"

    def test_photo_request_show_face(self):
        assert classify_intent("Muéstrame tu cara por favor") == "photo_request"

    def test_photo_request_english(self):
        assert classify_intent("Can you take a picture of this?") == "photo_request"

    def test_video_request_spanish(self):
        assert (
            classify_intent("Graba un video de lo que está ocurriendo")
            == "video_request"
        )

    def test_video_request_english(self):
        assert classify_intent("Please record a video") == "video_request"

    def test_video_takes_priority_over_photo(self):
        # Si se mencionan ambas, video tiene prioridad
        assert classify_intent("graba un video con una foto") == "video_request"

    def test_case_insensitive(self):
        assert classify_intent("TOMA UNA FOTO") == "photo_request"

    def test_empty_string(self):
        assert classify_intent("") is None

    def test_unrelated_text(self):
        assert classify_intent("El tiempo estará nublado mañana") is None

    def test_show_what_is_happening(self):
        assert classify_intent("muéstrame qué está pasando allí") == "video_request"

    def test_photo_partial_match(self):
        assert classify_intent("hazme una foto rápida") == "photo_request"
