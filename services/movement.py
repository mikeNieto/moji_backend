"""
services/movement.py — Construcción de secuencias de movimiento para el ESP32.

v2.0 — Moji Amigo Familiar

5 primitivas ESP32:
  turn_right_deg:GRADOS:dur_ms   — giro derecha N grados
  turn_left_deg:GRADOS:dur_ms    — giro izquierda N grados
  move_forward_cm:CM:dur_ms      — avance N centímetros
  move_backward_cm:CM:dur_ms     — retroceso N centímetros
  led_color:R:G:B                — color LED (0-255 por canal)

Gestos de alias → secuencias de primitivas:
  wave        → turn_right_deg:25:250 | turn_left_deg:50:250 | turn_right_deg:25:250
  nod         → move_forward_cm:5:300 | move_backward_cm:5:300
  rotate_left / rotate_right → turn_left_deg:90:800 / turn_right_deg:90:800
  move_forward / move_backward → move_forward_cm:30:1000 / move_backward_cm:30:1000
  shake_head  → turn_left_deg:30:200 | turn_right_deg:60:200 | turn_left_deg:30:200
  wiggle      → turn_left_deg:15:150 | turn_right_deg:30:150 | turn_left_deg:15:150
  pause       → pause (paso sin movimiento)

Uso:
    from services.movement import build_move_sequence, parse_actions_tag

    steps, remainder = parse_actions_tag("[actions:wave:800|nod:400] Hola")
    sequence = build_move_sequence("Saludo de bienvenida", steps)
    # sequence["total_duration_ms"] == 1200 (aprox, suma de dur_ms de todos los pasos expandidos)
"""

import re as _re


# ── Primitivas ESP32 ─────────────────────────────────────────────────────────

ESP32_PRIMITIVES: frozenset[str] = frozenset(
    {
        "turn_right_deg",
        "turn_left_deg",
        "move_forward_cm",
        "move_backward_cm",
        "led_color",
        "pause",
    }
)

# ── Alias de gestos → secuencias de primitivas ───────────────────────────────
# Cada alias expande a una lista de steps con "action", parámetros y "duration_ms".

_GESTURE_ALIASES: dict[str, list[dict]] = {
    "wave": [
        {"action": "turn_right_deg", "degrees": 25, "duration_ms": 250},
        {"action": "turn_left_deg", "degrees": 50, "duration_ms": 250},
        {"action": "turn_right_deg", "degrees": 25, "duration_ms": 250},
    ],
    "nod": [
        {"action": "move_forward_cm", "cm": 5, "duration_ms": 300},
        {"action": "move_backward_cm", "cm": 5, "duration_ms": 300},
    ],
    "shake_head": [
        {"action": "turn_left_deg", "degrees": 30, "duration_ms": 200},
        {"action": "turn_right_deg", "degrees": 60, "duration_ms": 200},
        {"action": "turn_left_deg", "degrees": 30, "duration_ms": 200},
    ],
    "wiggle": [
        {"action": "turn_left_deg", "degrees": 15, "duration_ms": 150},
        {"action": "turn_right_deg", "degrees": 30, "duration_ms": 150},
        {"action": "turn_left_deg", "degrees": 15, "duration_ms": 150},
    ],
    "rotate_left": [
        {"action": "turn_left_deg", "degrees": 90, "duration_ms": 800},
    ],
    "rotate_right": [
        {"action": "turn_right_deg", "degrees": 90, "duration_ms": 800},
    ],
    "move_forward": [
        {"action": "move_forward_cm", "cm": 30, "duration_ms": 1000},
    ],
    "move_backward": [
        {"action": "move_backward_cm", "cm": 30, "duration_ms": 1000},
    ],
    "pause": [
        {"action": "pause", "duration_ms": 500},
    ],
}


def expand_step(step: dict) -> list[dict]:
    """
    Si `step` es un alias de gesto, lo expande a su secuencia de primitivas.
    Si ya es una primitiva ESP32, lo devuelve tal cual (en lista de 1 elemento).
    Si el alias tiene un duration_ms total personalizado, escala proporcionalmente.
    """
    action = step.get("action", "")
    if action in _GESTURE_ALIASES:
        alias_steps = _GESTURE_ALIASES[action]
        # Escalar si el tag especifica una duración total diferente a la por defecto
        default_dur = sum(s["duration_ms"] for s in alias_steps)
        override_dur = step.get("duration_ms")
        if override_dur and override_dur != default_dur and default_dur > 0:
            scale = override_dur / default_dur
            return [
                {**s, "duration_ms": int(s["duration_ms"] * scale)} for s in alias_steps
            ]
        return list(alias_steps)
    return [step]


# ── build_move_sequence ───────────────────────────────────────────────────────


def build_move_sequence(description: str, steps: list[dict]) -> dict:
    """
    Construye el payload de secuencia de movimiento para el cliente Android/ESP32.

    Los gestos alias se expanden a sus primitivas antes de calcular la duración.

    Parámetros:
        description: Descripción legible de la secuencia.
        steps: Lista de steps (primitivas o aliases). Cada step tiene al menos:
               - "action": str
               - "duration_ms": int (puede ser el total del gesto alias)

    Devuelve un dict con:
        - "description": str
        - "steps": list[dict]   (ya expandidos a primitivas)
        - "total_duration_ms": int
        - "step_count": int
    """
    expanded: list[dict] = []
    for step in steps:
        expanded.extend(expand_step(step))

    total_duration_ms: int = sum(int(s.get("duration_ms", 0)) for s in expanded)
    return {
        "description": description,
        "steps": expanded,
        "total_duration_ms": total_duration_ms,
        "step_count": len(expanded),
    }


# ── parse_actions_tag ─────────────────────────────────────────────────────────

_ACTIONS_TAG_RE = _re.compile(r"^\[actions:([^\]]+)\]\s*", _re.IGNORECASE)


def parse_actions_tag(text: str) -> tuple[list[dict], str]:
    """
    Extrae [actions:step1|step2|...] del inicio del texto y expande aliases.

    Formatos de step (separados por |):
      accion:dur_ms
        → alias de gesto con duración total override, o primitiva sin params
      accion:param:dur_ms
        → primitiva con 1 parámetro numérico (grados, cm, …)  o gesto con dur
      led_color:R:G:B
        → primitiva LED (3 parámetros numéricos)

    Devuelve (lista_de_steps_expandidos, texto_restante).
    Si no hay tag al inicio, devuelve ([], text sin modificar).

    Ejemplos:
        parse_actions_tag("[actions:wave:800|nod:400] Hola")
        # → ([{turn_right_deg,25,250},{turn_left_deg,50,250},...,{move_forward_cm,...}], "Hola")

        parse_actions_tag("[actions:turn_right_deg:45:600] Girando")
        # → ([{action:turn_right_deg, degrees:45, duration_ms:600}], "Girando")

        parse_actions_tag("Sin tag")  # → ([], "Sin tag")
    """
    m = _ACTIONS_TAG_RE.match(text)
    if not m:
        return [], text

    raw_steps: list[dict] = []
    for part in m.group(1).split("|"):
        parts = [p.strip() for p in part.split(":") if p.strip()]
        if not parts:
            continue
        action = parts[0].lower()

        if len(parts) == 1:
            # accion sola → usar duración por defecto del alias o 500ms
            raw_steps.append({"action": action, "duration_ms": 500})

        elif len(parts) == 2:
            # accion:valor → si valor es número = duration_ms override; si no = parámetro 1
            if parts[1].isdigit():
                raw_steps.append({"action": action, "duration_ms": int(parts[1])})
            else:
                raw_steps.append(
                    {"action": action, "param": parts[1], "duration_ms": 500}
                )

        elif len(parts) == 3:
            # accion:param_o_dir:dur_ms  o  primitiva:valor:dur_ms
            if parts[2].isdigit():
                step: dict = {"action": action, "duration_ms": int(parts[2])}
                # Asignar el parámetro según el tipo de primitiva
                if action in ("turn_right_deg", "turn_left_deg") and parts[1].isdigit():
                    step["degrees"] = int(parts[1])
                elif (
                    action in ("move_forward_cm", "move_backward_cm")
                    and parts[1].isdigit()
                ):
                    step["cm"] = int(parts[1])
                else:
                    step["direction"] = parts[1]
                raw_steps.append(step)
            else:
                raw_steps.append(
                    {"action": action, "param": parts[1], "duration_ms": 500}
                )

        elif len(parts) == 4 and action == "led_color":
            # led_color:R:G:B  (sin dur_ms — es instantáneo)
            try:
                raw_steps.append(
                    {
                        "action": "led_color",
                        "r": int(parts[1]),
                        "g": int(parts[2]),
                        "b": int(parts[3]),
                        "duration_ms": 0,
                    }
                )
            except ValueError:
                raw_steps.append({"action": action, "duration_ms": 0})
        else:
            raw_steps.append({"action": action, "duration_ms": 500})

    # Expandir aliases a primitivas
    expanded: list[dict] = []
    for step in raw_steps:
        expanded.extend(expand_step(step))

    return expanded, text[m.end() :]
