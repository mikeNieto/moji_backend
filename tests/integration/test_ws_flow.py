"""
tests/integration/test_ws_flow.py — Test de integración del WebSocket /ws/interact (v3.0).

Levanta la app completa con TestClient y verifica el flujo WebSocket end-to-end:
  auth → interaction_start → text/audio_end → emotion + text_chunk + response_meta + stream_end

El agente se mockea (run_agent) para evitar llamadas reales a Gemini durante las pruebas.

Ejecución:
    uv run pytest tests/integration/ -v
"""

import os
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

os.environ.setdefault("API_KEY", "test-api-key-for-unit-tests-only")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key-not-used-in-unit-tests")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from main import app  # noqa: E402
from services.agent import MojiResponse  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_mock_response(**kwargs) -> MojiResponse:
    """Crea un MojiResponse con valores por defecto, sobrescribibles via kwargs."""
    defaults = {
        "emotion": "neutral",
        "emojis": ["1F642"],
        "actions": [],
        "response_text": "Hola!",
        "memories": [],
        "person_name": None,
        "media_summary": None,
    }
    defaults.update(kwargs)
    return MojiResponse(**defaults)


@pytest.fixture()
def ws_app():
    """TestClient con lifespan activado (crea la BD in-memory en startup)."""
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestWebSocketFlow:
    def test_auth_valid_key(self, ws_app):
        """Auth con API Key válida → auth_ok sin session_id (historial global)."""
        with ws_app.websocket_connect("/ws/interact") as ws:
            ws.send_json(
                {"type": "auth", "api_key": "test-api-key-for-unit-tests-only"}
            )
            msg = ws.receive_json()
            assert msg["type"] == "auth_ok"

    def test_auth_invalid_key_closes_connection(self, ws_app):
        """Auth con API Key inválida → error + cierre."""
        with ws_app.websocket_connect("/ws/interact") as ws:
            ws.send_json({"type": "auth", "api_key": "bad-key"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["error_code"] == "INVALID_API_KEY"
            with pytest.raises(Exception):
                ws.receive_json()

    def test_text_interaction_full_flow(self, ws_app):
        """Flujo completo: auth → text → emotion + text_chunks + response_meta + stream_end."""
        with (
            patch(
                "ws_handlers.streaming.run_agent",
                new_callable=AsyncMock,
                return_value=make_mock_response(
                    emotion="happy", response_text="Hola! ¿Cómo estás?"
                ),
            ),
            patch("ws_handlers.streaming._save_history_bg", new_callable=AsyncMock),
            patch(
                "ws_handlers.streaming._load_moji_context",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ws_handlers.streaming.compact_memories_async", new_callable=AsyncMock
            ),
        ):
            with ws_app.websocket_connect("/ws/interact") as ws:
                ws.send_json(
                    {"type": "auth", "api_key": "test-api-key-for-unit-tests-only"}
                )
                auth_ok = ws.receive_json()
                assert auth_ok["type"] == "auth_ok"

                ws.send_json(
                    {
                        "type": "text",
                        "request_id": "req-integration-001",
                        "content": "Hola Moji",
                    }
                )

                received = []
                for _ in range(20):
                    msg = ws.receive_json()
                    received.append(msg)
                    if msg["type"] == "stream_end":
                        break

                types = [m["type"] for m in received]
                assert "emotion" in types, f"Falta 'emotion' en: {types}"
                assert "stream_end" in types, f"Falta 'stream_end' en: {types}"

                if "text_chunk" in types:
                    assert types.index("emotion") < types.index("text_chunk")

                assert "response_meta" in types, f"Falta 'response_meta' en: {types}"
                assert types.index("response_meta") < types.index("stream_end")

                emotion_msg = next(m for m in received if m["type"] == "emotion")
                assert emotion_msg["emotion"] == "happy"
                assert emotion_msg["request_id"] == "req-integration-001"

                end_msg = next(m for m in received if m["type"] == "stream_end")
                assert end_msg["request_id"] == "req-integration-001"
                assert "processing_time_ms" in end_msg

    def test_interaction_start_with_person_id_then_text(self, ws_app):
        """interaction_start con person_id setea el contexto; text lo procesa."""
        with (
            patch(
                "ws_handlers.streaming.run_agent",
                new_callable=AsyncMock,
                return_value=make_mock_response(
                    emotion="greeting", response_text="¡Bienvenido, Ana!"
                ),
            ),
            patch("ws_handlers.streaming._save_history_bg", new_callable=AsyncMock),
            patch(
                "ws_handlers.streaming._load_moji_context",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ws_handlers.streaming.compact_memories_async", new_callable=AsyncMock
            ),
        ):
            with ws_app.websocket_connect("/ws/interact") as ws:
                ws.send_json(
                    {"type": "auth", "api_key": "test-api-key-for-unit-tests-only"}
                )
                ws.receive_json()  # auth_ok

                ws.send_json(
                    {
                        "type": "interaction_start",
                        "request_id": "req-start-001",
                        "person_id": "persona_ana_001",
                        "face_embedding": None,
                    }
                )

                ws.send_json(
                    {
                        "type": "text",
                        "request_id": "req-text-001",
                        "content": "Hola",
                    }
                )

                received = []
                for _ in range(20):
                    msg = ws.receive_json()
                    received.append(msg)
                    if msg["type"] == "stream_end":
                        break

                types = [m["type"] for m in received]
                assert "emotion" in types
                assert "stream_end" in types

    def test_interaction_start_without_person_id(self, ws_app):
        """interaction_start sin person_id (persona desconocida) → funciona sin error."""
        with (
            patch(
                "ws_handlers.streaming.run_agent",
                new_callable=AsyncMock,
                return_value=make_mock_response(
                    emotion="curious", response_text="Hola, ¿quién eres?"
                ),
            ),
            patch("ws_handlers.streaming._save_history_bg", new_callable=AsyncMock),
            patch(
                "ws_handlers.streaming._load_moji_context",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ws_handlers.streaming.compact_memories_async", new_callable=AsyncMock
            ),
        ):
            with ws_app.websocket_connect("/ws/interact") as ws:
                ws.send_json(
                    {"type": "auth", "api_key": "test-api-key-for-unit-tests-only"}
                )
                ws.receive_json()  # auth_ok

                ws.send_json(
                    {
                        "type": "interaction_start",
                        "request_id": "req-anon",
                        "person_id": None,
                        "face_embedding": None,
                    }
                )

                ws.send_json(
                    {
                        "type": "text",
                        "request_id": "req-anon-text",
                        "content": "¿Quién soy?",
                    }
                )

                received = []
                for _ in range(20):
                    msg = ws.receive_json()
                    received.append(msg)
                    if msg["type"] == "stream_end":
                        break

                types = [m["type"] for m in received]
                assert "emotion" in types
                assert "stream_end" in types

    def test_no_emotion_tag_defaults_neutral(self, ws_app):
        """Respuesta con emotion='neutral' (default) → se envía emotion='neutral'."""
        with (
            patch(
                "ws_handlers.streaming.run_agent",
                new_callable=AsyncMock,
                return_value=make_mock_response(
                    emotion="neutral", response_text="Aquí la respuesta."
                ),
            ),
            patch("ws_handlers.streaming._save_history_bg", new_callable=AsyncMock),
            patch(
                "ws_handlers.streaming._load_moji_context",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ws_handlers.streaming.compact_memories_async", new_callable=AsyncMock
            ),
        ):
            with ws_app.websocket_connect("/ws/interact") as ws:
                ws.send_json(
                    {"type": "auth", "api_key": "test-api-key-for-unit-tests-only"}
                )
                ws.receive_json()  # auth_ok

                ws.send_json(
                    {"type": "text", "request_id": "req-neutral", "content": "Hola"}
                )

                received = []
                for _ in range(20):
                    msg = ws.receive_json()
                    received.append(msg)
                    if msg["type"] == "stream_end":
                        break

                emotion_msgs = [m for m in received if m["type"] == "emotion"]
                assert len(emotion_msgs) == 1
                assert emotion_msgs[0]["emotion"] == "neutral"

    def test_response_meta_has_emojis(self, ws_app):
        """response_meta incluye emojis de MojiResponse."""
        with (
            patch(
                "ws_handlers.streaming.run_agent",
                new_callable=AsyncMock,
                return_value=make_mock_response(
                    emotion="excited",
                    emojis=["1F929", "1F389"],
                    response_text="¡Fantástico!",
                ),
            ),
            patch("ws_handlers.streaming._save_history_bg", new_callable=AsyncMock),
            patch(
                "ws_handlers.streaming._load_moji_context",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ws_handlers.streaming.compact_memories_async", new_callable=AsyncMock
            ),
        ):
            with ws_app.websocket_connect("/ws/interact") as ws:
                ws.send_json(
                    {"type": "auth", "api_key": "test-api-key-for-unit-tests-only"}
                )
                ws.receive_json()  # auth_ok

                ws.send_json(
                    {
                        "type": "text",
                        "request_id": "req-emojis",
                        "content": "¡Qué emoción!",
                    }
                )

                received = []
                for _ in range(20):
                    msg = ws.receive_json()
                    received.append(msg)
                    if msg["type"] == "stream_end":
                        break

                meta_msgs = [m for m in received if m["type"] == "response_meta"]
                assert len(meta_msgs) == 1
                emojis = meta_msgs[0]["expression"]["emojis"]
                assert isinstance(emojis, list)
                assert len(emojis) > 0
                assert "1F929" in emojis

    def test_empty_audio_end_sends_error(self, ws_app):
        """audio_end sin frames previos → error EMPTY_AUDIO."""
        with ws_app.websocket_connect("/ws/interact") as ws:
            ws.send_json(
                {"type": "auth", "api_key": "test-api-key-for-unit-tests-only"}
            )
            ws.receive_json()  # auth_ok

            ws.send_json(
                {
                    "type": "interaction_start",
                    "request_id": "req-audio",
                    "person_id": None,
                    "face_embedding": None,
                }
            )

            ws.send_json({"type": "audio_end", "request_id": "req-audio"})

            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["error_code"] == "EMPTY_AUDIO"

    def test_multiple_interactions_in_session(self, ws_app):
        """Múltiples interacciones en la misma sesión → cada una recibe stream_end."""
        call_count = {"n": 0}
        mock_responses = [
            make_mock_response(emotion="happy", response_text="Primera respuesta."),
            make_mock_response(emotion="neutral", response_text="Segunda respuesta."),
        ]

        async def multi_run(*args, **kwargs):
            n = call_count["n"]
            call_count["n"] += 1
            return (
                mock_responses[n] if n < len(mock_responses) else make_mock_response()
            )

        with (
            patch("ws_handlers.streaming.run_agent", side_effect=multi_run),
            patch("ws_handlers.streaming._save_history_bg", new_callable=AsyncMock),
            patch(
                "ws_handlers.streaming._load_moji_context",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "ws_handlers.streaming.compact_memories_async", new_callable=AsyncMock
            ),
        ):
            with ws_app.websocket_connect("/ws/interact") as ws:
                ws.send_json(
                    {"type": "auth", "api_key": "test-api-key-for-unit-tests-only"}
                )
                ws.receive_json()  # auth_ok

                ws.send_json({"type": "text", "request_id": "req-1", "content": "Hola"})
                for _ in range(20):
                    msg = ws.receive_json()
                    if msg["type"] == "stream_end":
                        break
                else:
                    pytest.fail("Primera interacción no terminó con stream_end")

                ws.send_json(
                    {"type": "text", "request_id": "req-2", "content": "¿Cómo estás?"}
                )
                for _ in range(20):
                    msg = ws.receive_json()
                    if msg["type"] == "stream_end":
                        break
                else:
                    pytest.fail("Segunda interacción no terminó con stream_end")

        assert call_count["n"] == 2

    def test_face_scan_mode_returns_actions(self, ws_app):
        """face_scan_mode → se envía face_scan_actions con primitivas ESP32."""
        with ws_app.websocket_connect("/ws/interact") as ws:
            ws.send_json(
                {"type": "auth", "api_key": "test-api-key-for-unit-tests-only"}
            )
            ws.receive_json()  # auth_ok

            ws.send_json({"type": "face_scan_mode", "request_id": "req-scan"})

            msg = ws.receive_json()
            assert msg["type"] == "face_scan_actions"
            assert msg["request_id"] == "req-scan"
            assert isinstance(msg["actions"], list)
            assert len(msg["actions"]) > 0

    def test_person_detected_known_person(self, ws_app):
        """person_detected con known=True y person_id → no hay error."""
        with ws_app.websocket_connect("/ws/interact") as ws:
            ws.send_json(
                {"type": "auth", "api_key": "test-api-key-for-unit-tests-only"}
            )
            ws.receive_json()  # auth_ok

            ws.send_json(
                {
                    "type": "person_detected",
                    "request_id": "req-person",
                    "known": True,
                    "person_id": "persona_ana_001",
                    "confidence": 0.92,
                }
            )

            # No error de protocolo esperado; la interacción fue válida
            # La respuesta puede no venir si es solo un update de estado
            # Solo verificamos que la conexión sigue viva enviando un ping type
            with (
                patch(
                    "ws_handlers.streaming.run_agent",
                    new_callable=AsyncMock,
                    return_value=make_mock_response(
                        emotion="happy", response_text="Hola Ana!"
                    ),
                ),
                patch("ws_handlers.streaming._save_history_bg", new_callable=AsyncMock),
                patch(
                    "ws_handlers.streaming._load_moji_context",
                    new_callable=AsyncMock,
                    return_value={},
                ),
                patch(
                    "ws_handlers.streaming.compact_memories_async",
                    new_callable=AsyncMock,
                ),
            ):
                ws.send_json(
                    {"type": "text", "request_id": "req-afterperson", "content": "Hola"}
                )
                for _ in range(20):
                    msg = ws.receive_json()
                    if msg["type"] == "stream_end":
                        break
