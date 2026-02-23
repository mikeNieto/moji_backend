"""
Entidades de dominio — representación en memoria (no SQLAlchemy).
Usadas como DTOs entre repositorios y servicios.

v2.0 — Moji Amigo Familiar
  - Eliminadas: User, Interaction
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Personas ──────────────────────────────────────────────────────────────────


@dataclass
class Person:
    """Persona conocida por Moji (familiar, amigo, vecino…)."""

    person_id: str  # slug único, p.ej. "persona_juan_01"
    name: str
    first_seen: datetime = field(default_factory=_now)
    last_seen: datetime = field(default_factory=_now)
    interaction_count: int = 0
    notes: str = ""  # contexto libre: "le gusta el café", "trabaja de noche"
    id: int | None = None  # PK asignada por la BD


@dataclass
class FaceEmbedding:
    """Embedding facial (128D) asociado a una persona conocida."""

    person_id: str  # FK → people.person_id
    embedding: bytes  # vector 128D serializado
    captured_at: datetime = field(default_factory=_now)
    source_lighting: str | None = None  # "day" | "night" | None
    id: int | None = None


# ── Memorias ──────────────────────────────────────────────────────────────────

# Tipos válidos de memoria
MEMORY_TYPES = frozenset({"experience", "person_fact", "general"})


@dataclass
class Memory:
    """Recuerdo almacenado por Moji."""

    memory_type: str  # experience | person_fact | general
    content: str
    person_id: str | None = None  # FK → people.person_id (nullable)
    importance: int = 5  # 1-10
    timestamp: datetime = field(default_factory=_now)
    expires_at: datetime | None = None
    id: int | None = None


# ── Historial de conversación ─────────────────────────────────────────────────


@dataclass
class ConversationMessage:
    session_id: str
    role: str  # "user" | "assistant"
    content: str
    message_index: int = 0
    is_compacted: bool = False  # True si representa un resumen compactado
    timestamp: datetime = field(default_factory=_now)
    id: int | None = None
