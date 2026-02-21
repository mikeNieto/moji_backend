"""
tests/integration/test_ws_flow.py — Test de integración del WebSocket /ws/interact.

Levanta la app completa con TestClient y verifica el flujo WebSocket end-to-end:
  auth → interaction_start → text → emotion + text_chunks + stream_end

El agente se mockea para evitar llamadas reales a Gemini durante las pruebas.

Ejecución:
    uv run pytest tests/integration/ -v
"""

import os
from unittest.mock import patch, AsyncMock

import pytest
from starlette.testclient import TestClient

# Garantizar env vars antes de importar main
os.environ.setdefault("API_KEY", "test-api-key-for-unit-tests-only")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key-not-used-in-unit-tests")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from main import app  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────────


def make_agent_stream(*chunks: str):
    """
    Devuelve una función async generator que emite los chunks dados.
    Úsase para parchear ws_handlers.streaming.run_agent_stream.
    """

    async def _stream(*args, **kwargs):
        for chunk in chunks:
            yield chunk

    return _stream


@pytest.fixture()
def ws_app():
    """TestClient con lifespan activado (crea la BD in-memory en startup)."""
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestWebSocketFlow:
    def test_auth_valid_key(self, ws_app):
        """Auth con API Key válida → auth_ok con session_id."""
        with ws_app.websocket_connect("/ws/interact") as ws:
            ws.send_json(
                {"type": "auth", "api_key": "test-api-key-for-unit-tests-only"}
            )
            msg = ws.receive_json()
            assert msg["type"] == "auth_ok"
            assert isinstance(msg["session_id"], str)
            assert len(msg["session_id"]) > 0

    def test_auth_invalid_key_closes_connection(self, ws_app):
        """Auth con API Key inválida → error + cierre."""
        with ws_app.websocket_connect("/ws/interact") as ws:
            ws.send_json({"type": "auth", "api_key": "bad-key"})
            # Recibir mensaje de error
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["error_code"] == "INVALID_API_KEY"
            # La conexión se cierra después; recibir cierre
            with pytest.raises(Exception):
                # La conexión ya está cerrada, el siguiente receive lanza excepción
                ws.receive_json()

    def test_text_interaction_full_flow(self, ws_app):
        """
        Flujo completo: auth → text → emotion + text_chunks + response_meta + stream_end.
        """
        mock_stream = make_agent_stream("[emotion:happy] Hola! ¿Cómo estás?")

        with (
            patch("ws_handlers.streaming.run_agent_stream", mock_stream),
            patch("ws_handlers.streaming.create_agent", return_value=None),
            patch("ws_handlers.streaming._save_history_bg", new_callable=AsyncMock),
            patch("ws_handlers.streaming._save_interaction_bg", new_callable=AsyncMock),
        ):
            with ws_app.websocket_connect("/ws/interact") as ws:
                # 1. Auth
                ws.send_json(
                    {
                        "type": "auth",
                        "api_key": "test-api-key-for-unit-tests-only",
                    }
                )
                auth_ok = ws.receive_json()
                assert auth_ok["type"] == "auth_ok"

                # 2. Enviar texto
                ws.send_json(
                    {
                        "type": "text",
                        "request_id": "req-integration-001",
                        "content": "Hola Robi",
                    }
                )

                # 3. Recibir mensajes hasta stream_end
                received = []
                for _ in range(20):  # máx iteraciones de seguridad
                    msg = ws.receive_json()
                    received.append(msg)
                    if msg["type"] == "stream_end":
                        break

                # Verificar secuencia de mensajes
                types = [m["type"] for m in received]
                assert "emotion" in types, f"Falta 'emotion' en: {types}"
                assert "stream_end" in types, f"Falta 'stream_end' en: {types}"

                # emotion antes de text_chunk (si hay text_chunk)
                if "text_chunk" in types:
                    assert types.index("emotion") < types.index("text_chunk")

                # response_meta antes de stream_end
                assert "response_meta" in types, f"Falta 'response_meta' en: {types}"
                assert types.index("response_meta") < types.index("stream_end")

                # Verificar campos del emotion
                emotion_msg = next(m for m in received if m["type"] == "emotion")
                assert emotion_msg["emotion"] == "happy"
                assert emotion_msg["request_id"] == "req-integration-001"

                # Verificar stream_end
                end_msg = next(m for m in received if m["type"] == "stream_end")
                assert end_msg["request_id"] == "req-integration-001"
                assert "processing_time_ms" in end_msg

    def test_interaction_start_then_text(self, ws_app):
        """interaction_start setea el contexto y luego text lo procesa."""
        mock_stream = make_agent_stream("[emotion:greeting] ¡Bienvenido!")

        with (
            patch("ws_handlers.streaming.run_agent_stream", mock_stream),
            patch("ws_handlers.streaming.create_agent", return_value=None),
            patch("ws_handlers.streaming._save_history_bg", new_callable=AsyncMock),
            patch("ws_handlers.streaming._save_interaction_bg", new_callable=AsyncMock),
        ):
            with ws_app.websocket_connect("/ws/interact") as ws:
                ws.send_json(
                    {
                        "type": "auth",
                        "api_key": "test-api-key-for-unit-tests-only",
                    }
                )
                ws.receive_json()  # auth_ok

                # interaction_start context
                ws.send_json(
                    {
                        "type": "interaction_start",
                        "request_id": "req-start-001",
                        "user_id": "unknown",
                        "face_recognized": False,
                    }
                )

                # text message triggers processing
                ws.send_json(
                    {
                        "type": "text",
                        "request_id": "req-text-001",
                        "content": "Hola",
                    }
                )

                # Collect until stream_end
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
        """Respuesta sin emotion tag → se envía emotion='neutral'."""
        mock_stream = make_agent_stream("Aquí la respuesta sin tag de emoción.")

        with (
            patch("ws_handlers.streaming.run_agent_stream", mock_stream),
            patch("ws_handlers.streaming.create_agent", return_value=None),
            patch("ws_handlers.streaming._save_history_bg", new_callable=AsyncMock),
            patch("ws_handlers.streaming._save_interaction_bg", new_callable=AsyncMock),
        ):
            with ws_app.websocket_connect("/ws/interact") as ws:
                ws.send_json(
                    {
                        "type": "auth",
                        "api_key": "test-api-key-for-unit-tests-only",
                    }
                )
                ws.receive_json()  # auth_ok

                ws.send_json(
                    {
                        "type": "text",
                        "request_id": "req-neutral",
                        "content": "Hola",
                    }
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
        """response_meta incluye emojis del emotion tag."""
        mock_stream = make_agent_stream("[emotion:excited] ¡Fantástico!")

        with (
            patch("ws_handlers.streaming.run_agent_stream", mock_stream),
            patch("ws_handlers.streaming.create_agent", return_value=None),
            patch("ws_handlers.streaming._save_history_bg", new_callable=AsyncMock),
            patch("ws_handlers.streaming._save_interaction_bg", new_callable=AsyncMock),
        ):
            with ws_app.websocket_connect("/ws/interact") as ws:
                ws.send_json(
                    {
                        "type": "auth",
                        "api_key": "test-api-key-for-unit-tests-only",
                    }
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
                # Los emojis de 'excited' deben incluir 1F929 (starry eyes)
                assert "1F929" in emojis

    def test_empty_audio_end_sends_error(self, ws_app):
        """audio_end sin frames previos → error EMPTY_AUDIO."""
        with ws_app.websocket_connect("/ws/interact") as ws:
            ws.send_json(
                {
                    "type": "auth",
                    "api_key": "test-api-key-for-unit-tests-only",
                }
            )
            ws.receive_json()  # auth_ok

            ws.send_json(
                {
                    "type": "interaction_start",
                    "request_id": "req-audio",
                    "user_id": "unknown",
                    "face_recognized": False,
                }
            )

            ws.send_json(
                {
                    "type": "audio_end",
                    "request_id": "req-audio",
                }
            )

            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["error_code"] == "EMPTY_AUDIO"

    def test_multiple_interactions_in_session(self, ws_app):
        """Múltiples interacciones en la misma sesión → cada una recibe stream_end."""
        responses = [
            "[emotion:happy] Primera respuesta.",
            "[emotion:neutral] Segunda respuesta.",
        ]
        call_count = {"n": 0}

        async def multi_stream(*args, **kwargs):
            n = call_count["n"]
            call_count["n"] += 1
            resp = responses[n] if n < len(responses) else "[emotion:neutral] Hola."
            yield resp

        with (
            patch("ws_handlers.streaming.run_agent_stream", multi_stream),
            patch("ws_handlers.streaming.create_agent", return_value=None),
            patch("ws_handlers.streaming._save_history_bg", new_callable=AsyncMock),
            patch("ws_handlers.streaming._save_interaction_bg", new_callable=AsyncMock),
        ):
            with ws_app.websocket_connect("/ws/interact") as ws:
                ws.send_json(
                    {
                        "type": "auth",
                        "api_key": "test-api-key-for-unit-tests-only",
                    }
                )
                ws.receive_json()  # auth_ok

                # Primera interacción
                ws.send_json({"type": "text", "request_id": "req-1", "content": "Hola"})
                for _ in range(20):
                    msg = ws.receive_json()
                    if msg["type"] == "stream_end":
                        break
                else:
                    pytest.fail("Primera interacción no terminó con stream_end")

                # Segunda interacción
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
