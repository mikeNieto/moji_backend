"""
services/agent.py — Agente LangChain DeepAgents sobre Gemini Flash Lite.

El agente orquesta la conversación del robot Robi. Usa deepagents con
tools=[] (extensible en futuras versiones) y un system prompt TTS-safe
que instruye al LLM a emitir emotion tags al inicio de cada respuesta.

Uso:
    from services.agent import create_agent, run_agent_stream

    agent = create_agent()
    async for chunk in run_agent_stream(
        agent=agent,
        session_id="sess_abc",
        user_id="user_juan",
        user_input="Hola Robi, ¿cómo estás?",
        history=[{"role": "user", "content": "..."}, ...],
    ):
        print(chunk, end="", flush=True)
"""

from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from services.gemini import get_model

# ── System Prompt TTS-safe (§3.7) ─────────────────────────────────────────────

SYSTEM_PROMPT = """Eres Robi, un robot doméstico amigable e interactivo. Tienes memoria de las personas \
con las que interactúas y adaptas tus respuestas según el contexto y las preferencias \
de cada usuario.

INSTRUCCIONES DE EMOCIÓN:
Antes de cada respuesta, emite una etiqueta de emoción que refleje el sentimiento \
de TU respuesta (no el del usuario). Formato: [emotion:TAG]
Tags válidos: happy, excited, sad, empathy, confused, surprised, love, cool, \
greeting, neutral, curious, worried, playful
Ejemplo: [emotion:empathy] Lo siento mucho, espero que te mejores pronto.

INSTRUCCIONES DE RESPUESTA (OBLIGATORIO):
- Da respuestas cortas de máximo un párrafo, a menos que el usuario pida \
  explícitamente una respuesta completa y detallada.
- Tus respuestas serán leídas en voz alta por un sistema Text-to-Speech. \
  Por eso es CRUCIAL seguir estas reglas:
  * Escribe los números completamente en palabras: "quinientos" en lugar de "500", \
    "tres mil" en lugar de "3.000" o "3,000".
  * Escribe los símbolos como palabras: "más" en lugar de "+", "por ciento" \
    en lugar de "%", "euros" en lugar de "€".
  * No uses fórmulas matemáticas, tablas, listas con viñetas, asteriscos, \
    guiones decorativos, separadores de miles ni ninguna notación que suene \
    extraño al ser leída linealmente.
  * Redacta en prosa fluida y natural, como si hablaras directamente con alguien.
  * Si necesitas enumerar elementos, hazlo con "primero", "segundo", "y por último" \
    en lugar de "1.", "2.", "3.".
  * Evita acrónimos poco comunes sin explicarlos. Pronuncia las siglas como \
    palabras o explícalas: "la Inteligencia Artificial" en vez de solo "la IA".
- Habla siempre en el idioma que usa el usuario."""


# ── Creación del agente ───────────────────────────────────────────────────────


def create_agent():
    """
    Crea y devuelve el agente DeepAgents sobre Gemini Flash Lite.

    Usa tools=[] — arquitectura extensible para futuras versiones.
    Devuelve el agente listo para llamar con run_agent_stream().
    """
    try:
        from deepagents import create_deep_agent  # type: ignore[import-untyped]

        model = get_model()
        agent = create_deep_agent(
            model=model,
            tools=[],
            system_prompt=SYSTEM_PROMPT,
        )
        return agent
    except Exception:
        # Si deepagents falla (p.ej. en tests sin API key), devolvemos None.
        # run_agent_stream maneja este caso usando el modelo directamente.
        return None


# ── Streaming del agente ──────────────────────────────────────────────────────


async def run_agent_stream(
    user_input: str,
    history: list[dict],
    session_id: str = "",
    user_id: str = "unknown",
    agent=None,
) -> AsyncIterator[str]:
    """
    Ejecuta el agente y hace streaming de los tokens de texto generados.

    Parámetros:
        user_input: El texto del usuario (transcripción de voz o texto directo).
        history:    Historial de la sesión como lista de {role, content}.
        session_id: Identificador de sesión (para logging).
        user_id:    Identificador del usuario (puede incluirse en el contexto).
        agent:      Agente DeepAgents creado por create_agent(). Si es None,
                    se usa el modelo Gemini directamente (sin harness de agente).

    Yields:
        Fragmentos de texto (str) a medida que el LLM los genera.
        El primer fragmento puede contener el emotion tag [emotion:TAG].
    """
    # Construir los mensajes incluyendo el historial
    messages: list = [SystemMessage(content=SYSTEM_PROMPT)]

    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_input))

    # Intentar stream via agente DeepAgents
    if agent is not None:
        try:
            async for chunk in _stream_via_agent(agent, messages, user_input, history):
                yield chunk
            return
        except Exception:
            pass  # fall through al modelo directo

    # Fallback: stream directo via modelo LangChain
    async for chunk in _stream_via_model(messages):
        yield chunk


async def _stream_via_agent(
    agent, messages: list, user_input: str, history: list[dict]
) -> AsyncIterator[str]:
    """Stream usando el harness DeepAgents (si está disponible)."""
    # deepagents puede exponer astream o ainvoke dependiendo de la versión
    if hasattr(agent, "astream"):
        async for event in agent.astream({"messages": messages}):
            # DeepAgents/LangGraph emite dicts con distintos formatos
            if isinstance(event, dict):
                for value in event.values():
                    if hasattr(value, "messages"):
                        for msg in value.messages:
                            if hasattr(msg, "content") and msg.content:
                                yield str(msg.content)
                    elif hasattr(value, "content") and value.content:
                        yield str(value.content)
            elif hasattr(event, "content") and event.content:
                yield str(event.content)
    elif hasattr(agent, "ainvoke"):
        result = await agent.ainvoke({"messages": messages})
        if isinstance(result, dict):
            for value in result.values():
                if hasattr(value, "messages") and value.messages:
                    last = value.messages[-1]
                    if hasattr(last, "content"):
                        yield str(last.content)
        elif hasattr(result, "content"):
            yield str(result.content)
    else:
        raise NotImplementedError("El agente no expone astream ni ainvoke")


async def _stream_via_model(messages: list) -> AsyncIterator[str]:
    """Stream directo usando ChatGoogleGenerativeAI (fallback sin agente)."""
    model = get_model()
    async for chunk in model.astream(messages):
        if hasattr(chunk, "content") and chunk.content:
            yield str(chunk.content)
