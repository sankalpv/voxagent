"""
Tool interface, registry, and dispatcher.

Tools are actions the AI agent can invoke mid-conversation:
- book_meeting     → Schedule via Calendly
- send_webhook     → Push data to any HTTP endpoint (generic CRM push)
- transfer_call    → Transfer to human agent
- end_call         → Gracefully end the call
- lookup_contact   → Look up contact info from DB

Tools are registered in the TOOL_REGISTRY. Agent configs specify which tools
are enabled via the `enabled_tools` field (list of tool names).

The LLM sees tool definitions as Gemini function declarations and can invoke
them naturally during conversation.
"""

import logging
from typing import Callable, Awaitable

from backend.app.services.llm.gemini import ToolDefinition

log = logging.getLogger(__name__)


# ─── Tool function type ───────────────────────────────────────────────────────

ToolFunc = Callable[..., Awaitable[dict]]


# ─── Tool Registry ────────────────────────────────────────────────────────────

class ToolSpec:
    """A registered tool with its definition and implementation."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        func: ToolFunc,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func

    def to_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )


# Global registry
TOOL_REGISTRY: dict[str, ToolSpec] = {}


def register_tool(
    name: str,
    description: str,
    parameters: dict,
    func: ToolFunc,
) -> None:
    """Register a tool in the global registry."""
    TOOL_REGISTRY[name] = ToolSpec(
        name=name,
        description=description,
        parameters=parameters,
        func=func,
    )
    log.debug("tool_registered", name=name)


# ─── Dispatcher ───────────────────────────────────────────────────────────────

async def execute_tool(
    tool_name: str,
    args: dict,
    call_id: str,
    tenant_id: str,
) -> dict:
    """
    Execute a tool by name with the given arguments.
    Returns a result dict with at minimum {"success": bool}.
    """
    spec = TOOL_REGISTRY.get(tool_name)
    if not spec:
        log.warning("unknown_tool", name=tool_name)
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    try:
        result = await spec.func(
            call_id=call_id,
            tenant_id=tenant_id,
            **args,
        )
        return result
    except Exception as exc:
        log.exception("tool_execution_error", tool=tool_name, error=str(exc))
        return {"success": False, "error": str(exc)}


def get_tool_definitions(enabled_tools: list[str]) -> list[ToolDefinition] | None:
    """Get Gemini-compatible tool definitions for the enabled tools."""
    defs = []
    for name in enabled_tools:
        spec = TOOL_REGISTRY.get(name)
        if spec:
            defs.append(spec.to_definition())
        else:
            log.warning("tool_not_found_in_registry", name=name)
    return defs if defs else None


# ─── Built-in Tools ───────────────────────────────────────────────────────────
# These are always available and registered on import.

async def _end_call_tool(call_id: str, tenant_id: str, reason: str = "conversation_complete", **kwargs) -> dict:
    """Signal the voice agent to end the call."""
    return {
        "success": True,
        "action": "end_call",
        "reason": reason,
        "message": "The call will be ended after the current response.",
    }


async def _transfer_call_tool(
    call_id: str,
    tenant_id: str,
    transfer_number: str = "",
    reason: str = "",
    **kwargs,
) -> dict:
    """Transfer the call to a human agent."""
    if not transfer_number:
        return {
            "success": False,
            "error": "No transfer number provided",
        }

    try:
        # Get the Telnyx call control ID
        from backend.app.db.database import AsyncSessionLocal
        from backend.app.db.models import Call
        from sqlalchemy import select
        import uuid

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Call.telnyx_call_control_id).where(
                    Call.id == uuid.UUID(call_id)
                )
            )
            control_id = result.scalar_one_or_none()

        if control_id:
            from backend.app.services.telephony.telnyx_handler import transfer_call
            success = await transfer_call(control_id, transfer_number)
            return {"success": success, "transferred_to": transfer_number}

        return {"success": False, "error": "No call control ID found"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _lookup_contact_tool(
    call_id: str,
    tenant_id: str,
    phone_number: str = "",
    **kwargs,
) -> dict:
    """Look up contact information from the database."""
    try:
        from backend.app.db.database import AsyncSessionLocal
        from backend.app.db.models import Contact
        from sqlalchemy import select
        import uuid

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Contact).where(
                    Contact.tenant_id == uuid.UUID(tenant_id),
                    Contact.phone_number == phone_number,
                )
            )
            contact = result.scalar_one_or_none()

        if contact:
            return {
                "success": True,
                "contact": {
                    "first_name": contact.first_name,
                    "last_name": contact.last_name,
                    "email": contact.email,
                    "company": contact.company,
                    "metadata": contact.extra_data,
                },
            }
        return {"success": True, "contact": None, "message": "No contact found for this number"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ─── Register built-in tools ──────────────────────────────────────────────────

register_tool(
    name="end_call",
    description="End the current call. Use this when the conversation has naturally concluded, the caller has asked to be removed, or the goal has been achieved.",
    parameters={
        "type_": "OBJECT",
        "properties": {
            "reason": {
                "type_": "STRING",
                "description": "Reason for ending the call (e.g., 'goal_achieved', 'not_interested', 'callback_requested')",
            },
        },
    },
    func=_end_call_tool,
)

register_tool(
    name="transfer_call",
    description="Transfer the call to a human agent or another phone number. Use when the caller requests to speak with a person, or when the situation requires human intervention.",
    parameters={
        "type_": "OBJECT",
        "properties": {
            "transfer_number": {
                "type_": "STRING",
                "description": "Phone number to transfer to (E.164 format, e.g., +14155551234)",
            },
            "reason": {
                "type_": "STRING",
                "description": "Reason for the transfer",
            },
        },
        "required": ["transfer_number"],
    },
    func=_transfer_call_tool,
)

register_tool(
    name="lookup_contact",
    description="Look up information about the person you're calling from the database. Use this to personalize the conversation.",
    parameters={
        "type_": "OBJECT",
        "properties": {
            "phone_number": {
                "type_": "STRING",
                "description": "Phone number to look up (E.164 format)",
            },
        },
        "required": ["phone_number"],
    },
    func=_lookup_contact_tool,
)


# ─── Import and register external tools ───────────────────────────────────────
# These are imported here so they auto-register when the module loads.

def _register_external_tools():
    """Import external tool modules to trigger their registration."""
    try:
        from backend.app.services.tools import calendar_tool  # noqa: F401
    except ImportError:
        log.debug("calendar_tool not available")

    try:
        from backend.app.services.tools import webhook_tool  # noqa: F401
    except ImportError:
        log.debug("webhook_tool not available")

    try:
        from backend.app.services.tools import rag_tool  # noqa: F401
    except ImportError:
        log.debug("rag_tool not available")


_register_external_tools()