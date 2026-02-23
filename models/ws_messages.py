"""
Modelos de mensajes WebSocket — union discriminada con Literal.

v2.0 — Moji Amigo Familiar

Mensajes del cliente (Android → Backend):
  AuthMessage, InteractionStartMessage, AudioEndMessage,
  TextMessage, ImageMessage, VideoMessage,
  FaceScanModeMessage, PersonDetectedMessage

Mensajes del servidor (Backend → Android):
  AuthOkMessage, EmotionMessage,
  TextChunkMessage, ResponseMetaMessage, StreamEndMessage,
  WsErrorMessage, FaceScanActionsMessage, LowBatteryAlertMessage
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════
# Mensajes del CLIENTE (Android → Backend)
# ═══════════════════════════════════════════════════════


class AuthMessage(BaseModel):
    type: Literal["auth"]
    api_key: str
    device_id: str = ""


class InteractionStartMessage(BaseModel):
    type: Literal["interaction_start"]
    request_id: str
    person_id: str | None = None  # None si Moji no ha reconocido a nadie aún
    face_recognized: bool = False
    face_confidence: float | None = None  # similitud coseno 0-1; None si no reconocido
    face_embedding: str | None = (
        None  # base64 128D; presente cuando se quiere registrar nombre
    )
    context: dict[str, Any] = Field(default_factory=dict)


class AudioEndMessage(BaseModel):
    type: Literal["audio_end"]
    request_id: str
    face_embedding: str | None = (
        None  # base64 128D; adjunto para flujo de captura de nombre
    )


class TextMessage(BaseModel):
    type: Literal["text"]
    request_id: str
    content: str
    face_embedding: str | None = (
        None  # base64 128D; adjunto para flujo de captura de nombre
    )


class ImageMessage(BaseModel):
    type: Literal["image"]
    request_id: str
    purpose: Literal["context"]  # "registration" eliminado — ahora por WS flow
    data: str  # base64 JPEG


class VideoMessage(BaseModel):
    type: Literal["video"]
    request_id: str
    duration_ms: int
    data: str  # base64 MP4


class FaceScanModeMessage(BaseModel):
    """Android inicia escaneo facial activo — ESP32 gira buscando personas."""

    type: Literal["face_scan_mode"]
    request_id: str


class PersonDetectedMessage(BaseModel):
    """Android informa de una persona detectada (conocida o desconocida)."""

    type: Literal["person_detected"]
    request_id: str
    known: bool
    person_id: str | None = None  # None si desconocida
    confidence: float = Field(0.0, ge=0.0, le=1.0)


# Union discriminada de mensajes del cliente
ClientMessage = (
    AuthMessage
    | InteractionStartMessage
    | AudioEndMessage
    | TextMessage
    | ImageMessage
    | VideoMessage
    | FaceScanModeMessage
    | PersonDetectedMessage
)


# ═══════════════════════════════════════════════════════
# Mensajes del SERVIDOR (Backend → Android)
# ═══════════════════════════════════════════════════════


class AuthOkMessage(BaseModel):
    type: Literal["auth_ok"] = "auth_ok"
    session_id: str


class EmotionMessage(BaseModel):
    type: Literal["emotion"] = "emotion"
    request_id: str
    emotion: str  # happy | excited | sad | empathy | curious | …
    person_identified: str | None = None  # person_id si Moji reconoció a alguien
    confidence: float | None = None


class TextChunkMessage(BaseModel):
    type: Literal["text_chunk"] = "text_chunk"
    request_id: str
    text: str


class ExpressionPayload(BaseModel):
    emojis: list[str]  # códigos Unicode OpenMoji, p.ej. ["1F44B"]
    duration_per_emoji: int = 2000
    transition: str = "bounce"


class MoveAction(BaseModel):
    type: Literal["move"]
    params: dict[str, Any]


class MoveSequenceAction(BaseModel):
    type: Literal["move_sequence"]
    total_duration_ms: int
    emotion_during: str
    steps: list[dict[str, Any]]


class LightAction(BaseModel):
    type: Literal["light"]
    params: dict[str, Any]


ResponseAction = MoveAction | MoveSequenceAction | LightAction


class ResponseMetaMessage(BaseModel):
    type: Literal["response_meta"] = "response_meta"
    request_id: str
    response_text: str
    expression: ExpressionPayload
    actions: list[dict[str, Any]] = Field(default_factory=list)
    person_name: str | None = (
        None  # extraído de [person_name:NOMBRE] cuando llega embedding
    )


class StreamEndMessage(BaseModel):
    type: Literal["stream_end"] = "stream_end"
    request_id: str
    processing_time_ms: int = 0


class WsErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    request_id: str | None = None
    error_code: str
    message: str
    recoverable: bool = False


class FaceScanActionsMessage(BaseModel):
    """
    Backend → Android: secuencia de primitivas ESP32 para que Moji gire
    buscando personas durante `face_scan_mode`.
    """

    type: Literal["face_scan_actions"] = "face_scan_actions"
    request_id: str
    actions: list[dict[str, Any]] = Field(default_factory=list)


class LowBatteryAlertMessage(BaseModel):
    """
    Backend → Android: alerta de batería baja del robot o del teléfono.
    """

    type: Literal["low_battery_alert"] = "low_battery_alert"
    battery_level: int = Field(..., ge=0, le=100)  # porcentaje
    source: Literal["robot", "phone"]


# Union discriminada de mensajes del servidor
ServerMessage = (
    AuthOkMessage
    | EmotionMessage
    | TextChunkMessage
    | ResponseMetaMessage
    | StreamEndMessage
    | WsErrorMessage
    | FaceScanActionsMessage
    | LowBatteryAlertMessage
)
