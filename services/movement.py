"""
services/movement.py — Construcción de secuencias de movimiento para el ESP32.

Uso:
    from services.movement import build_move_sequence

    sequence = build_move_sequence(
        description="Giro de saludo",
        steps=[
            {"action": "rotate", "direction": "left", "duration_ms": 500},
            {"action": "pause", "duration_ms": 200},
            {"action": "rotate", "direction": "right", "duration_ms": 500},
        ],
    )
    # sequence["total_duration_ms"] == 1200
"""


def build_move_sequence(description: str, steps: list[dict]) -> dict:
    """
    Construye el payload de secuencia de movimiento para el cliente Android/ESP32.

    Calcula `total_duration_ms` sumando el campo `duration_ms` de cada step.
    Los steps que no tengan `duration_ms` contribuyen 0 al total.

    Parámetros:
        description: Descripción legible de la secuencia (p.ej. "Saludo de bienvenida").
        steps: Lista de dicts de movimiento. Cada step debe tener al menos:
               - "action": str  (rotate | move_forward | move_backward | pause | wave, …)
               - "duration_ms": int (milisegundos que dura el paso)
               Puede tener campos adicionales como "direction", "speed", "distance_cm", etc.

    Devuelve un dict con:
        - "description": str
        - "steps": list[dict]
        - "total_duration_ms": int  (suma de duration_ms de todos los steps)
        - "step_count": int
    """
    total_duration_ms: int = sum(int(step.get("duration_ms", 0)) for step in steps)
    return {
        "description": description,
        "steps": steps,
        "total_duration_ms": total_duration_ms,
        "step_count": len(steps),
    }


# ── parse_actions_tag ─────────────────────────────────────────────────────────

import re as _re  # noqa: E402

_ACTIONS_TAG_RE = _re.compile(r"^\[actions:([^\]]+)\]\s*", _re.IGNORECASE)


def parse_actions_tag(text: str) -> tuple[list[dict], str]:
    """
    Extrae [actions:step1|step2|...] del inicio del texto.

    Formatos de step (separados por |):
      accion:dur_ms              → {"action": "wave",   "duration_ms": 800}
      accion:direccion:dur_ms    → {"action": "rotate", "direction": "left", "duration_ms": 500}

    Acciones válidas: wave, rotate_left, rotate_right, move_forward, move_backward,
                      nod, shake_head, wiggle, pause

    Devuelve (lista_de_steps, texto_restante).
    Si no hay tag al inicio, devuelve ([], text sin modificar).

    Ejemplos:
        parse_actions_tag("[actions:wave:800|nod:300] Hola")
        # → ([{action:wave,dur:800},{action:nod,dur:300}], "Hola")

        parse_actions_tag("Sin tag")  # → ([], "Sin tag")
    """
    m = _ACTIONS_TAG_RE.match(text)
    if not m:
        return [], text
    steps: list[dict] = []
    for part in m.group(1).split("|"):
        parts = [p.strip() for p in part.split(":") if p.strip()]
        if not parts:
            continue
        action = parts[0]
        if len(parts) == 2 and parts[1].isdigit():
            steps.append({"action": action, "duration_ms": int(parts[1])})
        elif len(parts) == 3 and parts[2].isdigit():
            steps.append(
                {"action": action, "direction": parts[1], "duration_ms": int(parts[2])}
            )
        else:
            steps.append({"action": action, "duration_ms": 500})
    return steps, text[m.end() :]
