"""
services/movement.py — Construcción de secuencias de movimiento para el ESP32.

v3.0 — Moji Amigo Familiar

Primitivas BLE/ESP32:
    turn_right_deg:GRADOS             — giro derecha N grados
    turn_left_deg:GRADOS              — giro izquierda N grados
    move_forward_duration:DUR_MS      — avance por tiempo fijo
    move_backward_duration:DUR_MS     — retroceso por tiempo fijo
    move_forward_cm:CM                — avance N centímetros
    move_backward_cm:CM               — retroceso N centímetros
    stop                              — detener movimiento
    led_color:R:G:B[:dur_ms]          — color LED (0-255 por canal), con duración opcional

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

    steps, remainder = parse_actions_tag("[actions:wave:800|move_forward_duration:400] Hola")
    sequence = build_move_sequence("Saludo de bienvenida", steps)
    # sequence["total_duration_ms"] == 1200 (aprox, usando duraciones explícitas o estimadas)
"""

import re as _re


# ── Primitivas ESP32 ─────────────────────────────────────────────────────────

ESP32_PRIMITIVES: frozenset[str] = frozenset(
    {
        "turn_right_deg",
        "turn_left_deg",
        "move_forward_duration",
        "move_backward_duration",
        "move_forward_cm",
        "move_backward_cm",
        "stop",
        "led_color",
        "pause",
    }
)

TURN_MS_PER_90_DEG = 420
MOVE_MS_PER_10_CM = 350

PROTOCOL_PRIMITIVES: frozenset[str] = frozenset(
    {
        "turn_right_deg",
        "turn_left_deg",
        "move_forward_duration",
        "move_backward_duration",
        "move_forward_cm",
        "move_backward_cm",
        "stop",
        "led_color",
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
        {"action": "move_forward_duration", "duration_ms": 1000},
    ],
    "move_backward": [
        {"action": "move_backward_duration", "duration_ms": 1000},
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


def _is_int(value: str) -> bool:
    return value.isdigit()


def estimate_step_duration_ms(step: dict) -> int:
    """Estima la duración de una primitiva según el contrato BLE actual."""
    action_type = (step.get("type") or step.get("action") or "").strip().lower()
    if not action_type or action_type == "stop":
        return 0

    duration_ms = step.get("duration_ms")
    if isinstance(duration_ms, int) and duration_ms > 0:
        return duration_ms

    if action_type in {"turn_right_deg", "turn_left_deg"}:
        degrees = int(step.get("degrees", 0))
        return int((degrees * TURN_MS_PER_90_DEG) / 90)

    if action_type in {"move_forward_cm", "move_backward_cm"}:
        cm = int(step.get("cm", 0))
        return int((cm * MOVE_MS_PER_10_CM) / 10)

    return 0


def normalize_step_for_protocol(step: dict) -> dict | None:
    """
    Convierte un step interno con clave `action` al payload externo esperado
    por Android/ESP32 usando `type` y el contrato BLE actual.

    `pause` se mantiene solo como concepto interno y no se exporta al protocolo
    BLE porque el firmware del ESP32 no lo interpreta como primitiva directa.
    """
    action_type = (step.get("type") or step.get("action") or "").strip().lower()
    if not action_type or action_type == "pause":
        return None
    if action_type not in PROTOCOL_PRIMITIVES:
        return None

    normalized: dict = {"type": action_type}

    if action_type in {"turn_right_deg", "turn_left_deg"} and "degrees" in step:
        normalized["degrees"] = int(step["degrees"])
    elif action_type in {"turn_right_deg", "turn_left_deg"}:
        return None
    elif action_type in {"move_forward_duration", "move_backward_duration"}:
        if "duration_ms" not in step:
            return None
        normalized["duration_ms"] = int(step["duration_ms"])
    elif action_type in {"move_forward_cm", "move_backward_cm"} and "cm" in step:
        normalized["cm"] = int(step["cm"])
    elif action_type in {"move_forward_cm", "move_backward_cm"}:
        return None
    elif action_type == "stop":
        return normalized
    elif action_type == "led_color":
        normalized["r"] = int(step.get("r", 0))
        normalized["g"] = int(step.get("g", 0))
        normalized["b"] = int(step.get("b", 0))
        if "duration_ms" in step:
            normalized["duration_ms"] = int(step.get("duration_ms", 0))

    if "duration_ms" in step and action_type in {
        "turn_right_deg",
        "turn_left_deg",
        "move_forward_cm",
        "move_backward_cm",
    }:
        normalized["duration_ms"] = int(step.get("duration_ms", 0))

    return normalized


def protocol_steps_from_steps(steps: list[dict]) -> list[dict]:
    """Expande aliases y devuelve primitivas listas para el protocolo WS/BLE."""
    normalized_steps: list[dict] = []
    for step in steps:
        for expanded_step in expand_step(step):
            normalized = normalize_step_for_protocol(expanded_step)
            if normalized is not None:
                normalized_steps.append(normalized)
    return normalized_steps


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
    expanded = protocol_steps_from_steps(steps)

    total_duration_ms: int = sum(estimate_step_duration_ms(s) for s in expanded)
    return {
        "type": "move_sequence",
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
            accion
                → primitiva sin params, p.ej. stop
            accion:valor
                → alias con duración total override, o primitiva con 1 parámetro
                     turn_*:GRADOS, move_*_duration:DUR_MS, move_*_cm:CM
            accion:param:dur_ms
                → formato legado soportado para turn_* y move_*_cm, o alias con override
            led_color:R:G:B
                → primitiva LED instantánea
            led_color:R:G:B:dur_ms
                → primitiva LED con duración explícita

    Devuelve (lista_de_steps_expandidos, texto_restante).
    Si no hay tag al inicio, devuelve ([], text sin modificar).

    Ejemplos:
        parse_actions_tag("[actions:wave:800|move_forward_duration:400] Hola")
        # → ([{turn_right_deg,25,250},{turn_left_deg,50,250},...,{move_forward_cm,...}], "Hola")

        parse_actions_tag("[actions:turn_right_deg:45|stop] Girando")
        # → ([{action:turn_right_deg, degrees:45},{action:stop}], "Girando")

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
            if action == "stop":
                raw_steps.append({"action": action})
            else:
                raw_steps.append({"action": action, "duration_ms": 500})

        elif len(parts) == 2:
            # accion:valor → primitiva nueva o alias con duración override
            if action in ("turn_right_deg", "turn_left_deg") and _is_int(parts[1]):
                raw_steps.append({"action": action, "degrees": int(parts[1])})
            elif action in ("move_forward_cm", "move_backward_cm") and _is_int(
                parts[1]
            ):
                raw_steps.append({"action": action, "cm": int(parts[1])})
            elif action in (
                "move_forward_duration",
                "move_backward_duration",
            ) and _is_int(parts[1]):
                raw_steps.append({"action": action, "duration_ms": int(parts[1])})
            elif _is_int(parts[1]):
                raw_steps.append({"action": action, "duration_ms": int(parts[1])})
            else:
                raw_steps.append(
                    {"action": action, "param": parts[1], "duration_ms": 500}
                )

        elif len(parts) == 3:
            # Compatibilidad con formato legado accion:param:dur_ms
            if _is_int(parts[2]):
                step: dict = {"action": action, "duration_ms": int(parts[2])}
                if action in ("turn_right_deg", "turn_left_deg") and _is_int(parts[1]):
                    step["degrees"] = int(parts[1])
                elif action in ("move_forward_cm", "move_backward_cm") and _is_int(
                    parts[1]
                ):
                    step["cm"] = int(parts[1])
                else:
                    step["direction"] = parts[1]
                raw_steps.append(step)
            else:
                raw_steps.append(
                    {"action": action, "param": parts[1], "duration_ms": 500}
                )

        elif len(parts) in {4, 5} and action == "led_color":
            # led_color:R:G:B[:dur_ms]
            try:
                raw_steps.append(
                    {
                        "action": "led_color",
                        "r": int(parts[1]),
                        "g": int(parts[2]),
                        "b": int(parts[3]),
                        "duration_ms": int(parts[4]) if len(parts) == 5 else 0,
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


# ── Helpers para structured output ───────────────────────────────────────────


def action_steps_from_list(steps: list[str]) -> list[dict]:
    """
    Convierte una lista de strings de pasos (del campo actions de MojiResponse)
    en steps expandidos a primitivas ESP32, listos para build_move_sequence().

    Cada string usa el mismo formato que parse_actions_tag internamente:
    "wave:800", "nod:400", "turn_right_deg:45", "move_forward_duration:800",
    "led_color:255:0:0:1000"

    Ejemplo:
        action_steps_from_list(["wave:800", "nod:400"])
        # → lista de steps primitivos expandidos
    """
    if not steps:
        return []
    fake_tag = f"[actions:{'|'.join(steps)}]"
    expanded, _ = parse_actions_tag(fake_tag)
    return expanded


def build_response_actions(steps: list[dict]) -> list[dict]:
    """
    Construye el payload de `response_meta.actions`.

    - Una sola primitiva sale como acción directa para evitar ambigüedad.
    - Varias primitivas salen agrupadas en una `move_sequence`.
    """
    protocol_steps = protocol_steps_from_steps(steps)
    if not protocol_steps:
        return []
    if len(protocol_steps) == 1:
        return protocol_steps
    return [build_move_sequence("Movimiento sugerido por Moji", steps)]
