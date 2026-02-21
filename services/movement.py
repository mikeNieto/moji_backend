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
