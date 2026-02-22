"""
Modelos Pydantic para respuestas de la REST API.
Sin `from typing import` — tipos nativos Python 3.12.

v2.0 — Solo 2 endpoints REST: GET /api/health y GET /api/restore.
  - Eliminadas: UserResponse, UserListResponse, FaceRegisterResponse,
                MemoryListResponse, MemorySaveResponse, MemoryDeleteResponse
  - Nuevas: RestorePersonResponse, RestoreZoneResponse,
            RestoreMemoryResponse, RestoreResponse
"""

from pydantic import BaseModel, Field


# ── Salud ─────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "2.0"


# ── Error estándar ─────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    error: bool = True
    error_code: str
    message: str
    details: str | None = None
    recoverable: bool = False
    retry_after: int | None = None  # segundos; None si no aplica
    timestamp: str  # ISO-8601


# ── Restauración (GET /api/restore) ───────────────────────────────────────────


class RestorePersonResponse(BaseModel):
    """Persona conocida con sus embeddings faciales (base64)."""

    person_id: str
    name: str
    embeddings: list[str] = Field(
        default_factory=list,
        description="Lista de embeddings 128D codificados en base64",
    )


class RestoreZonePathResponse(BaseModel):
    """Camino entre dos zonas del mapa mental."""

    to_zone: str
    direction_hint: str = ""
    distance_cm: int | None = None


class RestoreZoneResponse(BaseModel):
    """Zona del mapa mental de la casa."""

    name: str
    category: str  # kitchen | living | bedroom | bathroom | unknown
    description: str = ""
    accessible: bool = True
    paths: list[RestoreZonePathResponse] = Field(default_factory=list)


class RestoreMemoryResponse(BaseModel):
    """Recuerdo general de Robi (sin ligarse a persona específica)."""

    type: str  # experience | zone_info | person_fact | general
    content: str
    importance: int = Field(ge=1, le=10)


class RestoreResponse(BaseModel):
    """
    Respuesta completa de GET /api/restore.
    Permite a Android reconstruir su DB local tras reinstalación.
    """

    people: list[RestorePersonResponse] = Field(default_factory=list)
    zones: list[RestoreZoneResponse] = Field(default_factory=list)
    memories: list[RestoreMemoryResponse] = Field(default_factory=list)
