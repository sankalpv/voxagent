"""
Telnyx telephony handler.

Manages the Telnyx Call Control API:
- Initiate outbound calls
- Answer inbound calls
- Start media streaming (WebSocket audio fork)
- Hangup, transfer, DTMF
- Send audio (TTS) to the call

Telnyx flow:
  1. POST /v2/calls → initiates outbound call
  2. Telnyx sends webhook: call.initiated → call.answered
  3. On answer: start_streaming → forks audio to our WebSocket
  4. Our WebSocket receives μ-law audio, sends back μ-law audio
  5. On hangup: webhook call.hangup → cleanup
"""

import asyncio
import base64
import logging
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.db.models import AgentConfig
from backend.app.services.memory.short_term import (
    CallSession,
    create_session,
    map_control_id,
)
from backend.app.services.llm.gemini import build_system_prompt

log = logging.getLogger(__name__)

TELNYX_API_BASE = "https://api.telnyx.com/v2"

_http_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=TELNYX_API_BASE,
            headers={
                "Authorization": f"Bearer {settings.telnyx_api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
    return _http_client


# ─── Outbound Call ────────────────────────────────────────────────────────────

async def initiate_outbound_call(
    call_id: str,
    to_number: str,
    agent_config: AgentConfig,
    contact_metadata: dict | None = None,
) -> dict | None:
    """
    Initiate an outbound call via Telnyx Call Control API.
    Creates a Redis session for the call and maps the Telnyx control ID.
    """
    client = await _get_client()

    # Build the webhook URL for this call's events
    webhook_url = f"{settings.public_base_url}/webhooks/telnyx"

    # Build system prompt from agent config
    contact_name = None
    if contact_metadata:
        first = contact_metadata.get("first_name", "")
        last = contact_metadata.get("last_name", "")
        contact_name = f"{first} {last}".strip() or None

    system_prompt = build_system_prompt(
        agent_name=agent_config.name,
        company_name=agent_config.persona.split(",")[0] if agent_config.persona else agent_config.name,
        persona=agent_config.persona,
        primary_goal=agent_config.primary_goal,
        constraints=agent_config.constraints,
        escalation_policy=agent_config.escalation_policy,
        contact_name=contact_name,
        contact_metadata=contact_metadata,
    )

    # Create session in Redis BEFORE the call so it's ready when webhooks arrive
    session = CallSession(
        call_id=call_id,
        tenant_id=str(agent_config.tenant_id),
        agent_config_id=str(agent_config.id),
        contact_phone=to_number,
        system_prompt=system_prompt,
        voice_name=agent_config.voice_name,
        enabled_tools=agent_config.enabled_tools or [],
        contact_metadata=contact_metadata or {},
    )
    await create_session(session)

    # Make the Telnyx API call
    payload = {
        "connection_id": settings.telnyx_connection_id,
        "to": to_number,
        "from": settings.telnyx_from_number,
        "webhook_url": webhook_url,
        "webhook_url_method": "POST",
        "answering_machine_detection": "detect_beep",
        "client_state": base64.b64encode(call_id.encode()).decode(),
        "record": "record-from-answer",
        "timeout_secs": 30,
    }

    try:
        resp = await client.post("/calls", json=payload)
        resp.raise_for_status()
        data = resp.json().get("data", {})

        telnyx_call_control_id = data.get("call_control_id")
        if telnyx_call_control_id:
            await map_control_id(telnyx_call_control_id, call_id)
            log.info(
                "telnyx_call_created call_id=%s control_id=%s to=%s",
                call_id, telnyx_call_control_id, to_number,
            )

        return data

    except httpx.HTTPStatusError as exc:
        log.error(
            "telnyx_call_failed call_id=%s status=%s body=%s",
            call_id, exc.response.status_code, exc.response.text,
        )
        # Update call status to failed
        await _update_call_status(call_id, "failed")
        return None
    except Exception as exc:
        log.exception("telnyx_call_error call_id=%s error=%s", call_id, str(exc))
        await _update_call_status(call_id, "failed")
        return None


# ─── Call Control Commands ────────────────────────────────────────────────────

async def answer_call(call_control_id: str, client_state: str = "") -> bool:
    """Answer an incoming call."""
    return await _call_command(call_control_id, "answer", {
        "client_state": client_state,
    })


async def start_streaming(call_control_id: str, call_id: str) -> bool:
    """
    Start media streaming — forks audio to our WebSocket endpoint.
    This is where the real-time audio pipeline begins.
    """
    stream_url = f"{settings.websocket_base_url}/ws/calls/{call_id}"
    return await _call_command(call_control_id, "streaming_start", {
        "stream_url": stream_url,
        "stream_track": "inbound_track",
        "enable_dialogflow": False,
    })


async def stop_streaming(call_control_id: str) -> bool:
    """Stop media streaming on a call."""
    return await _call_command(call_control_id, "streaming_stop", {})


async def hangup(call_control_id: str) -> bool:
    """Hang up the call."""
    return await _call_command(call_control_id, "hangup", {})


async def transfer_call(
    call_control_id: str,
    to_number: str,
    client_state: str = "",
) -> bool:
    """Transfer the call to a human agent or another number."""
    return await _call_command(call_control_id, "transfer", {
        "to": to_number,
        "client_state": client_state,
    })


async def send_dtmf(call_control_id: str, digits: str) -> bool:
    """Send DTMF tones."""
    return await _call_command(call_control_id, "send_dtmf", {
        "digits": digits,
    })


async def play_audio_url(call_control_id: str, audio_url: str) -> bool:
    """Play a pre-recorded audio URL on the call."""
    return await _call_command(call_control_id, "playback_start", {
        "audio_url": audio_url,
    })


# ─── Internal helpers ─────────────────────────────────────────────────────────

async def _call_command(
    call_control_id: str,
    command: str,
    payload: dict,
) -> bool:
    """Execute a Telnyx Call Control command."""
    client = await _get_client()
    url = f"/calls/{call_control_id}/actions/{command}"

    try:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        log.debug("telnyx_command command=%s control_id=%s", command, call_control_id)
        return True
    except httpx.HTTPStatusError as exc:
        log.error(
            "telnyx_command_failed command=%s control_id=%s status=%s body=%s",
            command, call_control_id, exc.response.status_code, exc.response.text,
        )
        return False
    except Exception as exc:
        log.exception("telnyx_command_error command=%s error=%s", command, str(exc))
        return False


async def _update_call_status(call_id: str, status_value: str) -> None:
    """Update call status in the database."""
    try:
        from backend.app.db.database import AsyncSessionLocal
        from backend.app.db.models import Call
        from sqlalchemy import update
        import uuid

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Call)
                .where(Call.id == uuid.UUID(call_id))
                .values(status=status_value)
            )
            await db.commit()
    except Exception as exc:
        log.exception("update_call_status_error call_id=%s error=%s", call_id, str(exc))
