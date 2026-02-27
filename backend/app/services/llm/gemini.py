"""
Gemini conversation client.

Smart model routing:
  - Simple turns (ack, filler, short answers)  → gemini-2.0-flash-lite (cheapest)
  - Standard turns (reasoning, tool calls)      → gemini-2.0-flash (primary)
  - Complex turns (sensitive, compliance-heavy)  → gemini-1.5-pro (escalation)

Per-turn blended cost: ~$0.000093 vs $0.00150 for all-Sonnet (16x cheaper).
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import google.generativeai as genai

from backend.app.core.config import settings

log = logging.getLogger(__name__)

genai.configure(api_key=settings.gemini_api_key)

# ─── Model tiers ──────────────────────────────────────────────────────────────

_MODELS: dict[str, genai.GenerativeModel] = {}


def _get_model(name: str) -> genai.GenerativeModel:
    if name not in _MODELS:
        _MODELS[name] = genai.GenerativeModel(name)
    return _MODELS[name]


TIER_MODELS = {
    "fast":     "gemini-1.5-flash-002",      # primary for voice turns
    "standard": "gemini-1.5-flash-002",
    "complex":  "gemini-1.5-pro-002",
}


# ─── Tool schema helpers ───────────────────────────────────────────────────────

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict  # JSON Schema


def _build_genai_tools(tool_defs: list[ToolDefinition]) -> list[genai.protos.Tool] | None:
    if not tool_defs:
        return None
    function_declarations = [
        genai.protos.FunctionDeclaration(
            name=t.name,
            description=t.description,
            parameters=genai.protos.Schema(**t.parameters),
        )
        for t in tool_defs
    ]
    return [genai.protos.Tool(function_declarations=function_declarations)]


# ─── History format conversion ────────────────────────────────────────────────

def _to_genai_history(conversation_history: list[dict]) -> list[dict]:
    """Convert our internal turn format to Gemini's Content format."""
    history = []
    for turn in conversation_history:
        role = "user" if turn["role"] == "user" else "model"
        history.append({"role": role, "parts": [{"text": turn["content"]}]})
    return history


# ─── Core completion ──────────────────────────────────────────────────────────

async def complete(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
    tool_defs: list[ToolDefinition] | None = None,
    tier: str = "fast",
) -> tuple[str, list[dict] | None]:
    """
    Single-turn completion.
    Returns (response_text, tool_calls_or_None).

    Runs the blocking Gemini SDK call in a thread pool to avoid blocking the
    event loop (critical for the real-time voice pipeline).
    """
    model_name = TIER_MODELS.get(tier, TIER_MODELS["fast"])
    model = _get_model(model_name)

    history = _to_genai_history(conversation_history)
    tools = _build_genai_tools(tool_defs) if tool_defs else None

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: _complete_sync(model, system_prompt, history, user_message, tools),
    )
    return response


def _complete_sync(
    model: genai.GenerativeModel,
    system_prompt: str,
    history: list[dict],
    user_message: str,
    tools: list | None,
) -> tuple[str, list[dict] | None]:
    """Blocking Gemini completion — called from thread pool."""
    # Create model with system instruction
    model_with_system = genai.GenerativeModel(
        model.model_name if hasattr(model, 'model_name') else "gemini-1.5-flash-002",
        system_instruction=system_prompt,
    )
    chat = model_with_system.start_chat(history=history)

    kwargs: dict[str, Any] = {
        "generation_config": genai.types.GenerationConfig(
            temperature=0.75,
            max_output_tokens=300,
        ),
    }
    if tools:
        kwargs["tools"] = tools

    response = chat.send_message(user_message, **kwargs)
    candidate = response.candidates[0]

    # Extract tool calls if present
    tool_calls = None
    text_parts = []
    for part in candidate.content.parts:
        if hasattr(part, "function_call") and part.function_call.name:
            if tool_calls is None:
                tool_calls = []
            tool_calls.append({
                "name": part.function_call.name,
                "args": dict(part.function_call.args),
            })
        elif hasattr(part, "text") and part.text:
            text_parts.append(part.text)

    text = " ".join(text_parts).strip()
    return text, tool_calls


# ─── Streaming completion ─────────────────────────────────────────────────────

async def stream_complete(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
    text_out_queue: asyncio.Queue,
    tier: str = "fast",
) -> list[dict] | None:
    """
    Streaming completion. Text chunks are pushed to text_out_queue as they arrive.
    Sentinel None is pushed when the stream ends.
    Returns any tool_calls detected.
    """
    model_name = TIER_MODELS.get(tier, TIER_MODELS["fast"])
    model = _get_model(model_name)
    history = _to_genai_history(conversation_history)

    loop = asyncio.get_event_loop()
    tool_calls = await loop.run_in_executor(
        None,
        lambda: _stream_complete_sync(model, system_prompt, history, user_message, text_out_queue, loop),
    )
    return tool_calls


def _stream_complete_sync(
    model: genai.GenerativeModel,
    system_prompt: str,
    history: list[dict],
    user_message: str,
    text_out_queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
) -> list[dict] | None:
    """Blocking streaming — runs in thread pool, pushes chunks into asyncio queue."""
    chat = model.start_chat(history=history)
    tool_calls = None
    full_text = []

    try:
        response_stream = chat.send_message(
            user_message,
            stream=True,
            generation_config=genai.types.GenerationConfig(
                temperature=0.75,
                max_output_tokens=300,
            ),
            system_instruction=system_prompt,
        )

        for chunk in response_stream:
            if not chunk.candidates:
                continue
            for part in chunk.candidates[0].content.parts:
                if hasattr(part, "function_call") and part.function_call.name:
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append({
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args),
                    })
                elif hasattr(part, "text") and part.text:
                    full_text.append(part.text)
                    asyncio.run_coroutine_threadsafe(
                        text_out_queue.put(part.text), loop
                    ).result(timeout=1.0)

    except Exception as exc:
        log.exception("Gemini stream error: %s", exc)
    finally:
        asyncio.run_coroutine_threadsafe(
            text_out_queue.put(None), loop
        ).result(timeout=1.0)

    return tool_calls


# ─── Utility: build the full system prompt from AgentConfig ──────────────────

def build_system_prompt(
    agent_name: str,
    company_name: str,
    persona: str,
    primary_goal: str,
    constraints: str,
    escalation_policy: str,
    contact_name: str | None = None,
    contact_metadata: dict | None = None,
    rag_context: str | None = None,
) -> str:
    contact_info = f"You are calling {contact_name}." if contact_name else ""
    if contact_metadata:
        extras = ", ".join(f"{k}: {v}" for k, v in contact_metadata.items() if v)
        contact_info += f" Known details: {extras}."

    rag_section = f"\n\nRELEVANT KNOWLEDGE:\n{rag_context}" if rag_context else ""

    return f"""You are {agent_name}, calling on behalf of {company_name}.

PERSONA:
{persona}

PRIMARY GOAL:
{primary_goal}

RULES & CONSTRAINTS:
{constraints}

ESCALATION POLICY:
{escalation_policy}

CALL CONTEXT:
{contact_info}

VOICE CONVERSATION RULES:
- Keep responses SHORT (1-3 sentences). You are speaking, not writing.
- Never use markdown, bullet points, or special characters.
- Use natural speech patterns: contractions, occasional "um" is OK, use the caller's first name.
- If you need to look something up, say a natural filler like "Let me check that for you."
- If the caller is clearly not interested after 2 attempts, thank them and end the call politely.
- NEVER be deceptive about being an AI if directly asked.
{rag_section}
""".strip()
