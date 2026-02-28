"""
Telnyx webhook handlers.

Processes call lifecycle events from Telnyx:
- call.initiated     → update DB status
- call.answered      → start audio streaming, launch voice agent
- call.hangup        → cleanup session, finalize call record
- call.machine.detection → handle voicemail
- streaming.started  → confirm audio pipeline is active
- streaming.stopped  → audio pipeline ended
"""

import asyncio
import base64
import logging
from datetime import datetime

from fastapi import APIRouter, Request
from sqlalchemy import update

from backend.app.db.database import AsyncSessionLocal
from backend.app.db.models import Call, CallOutcome, CallStatus
from backend.app.services.memory.short_term import (
    delete_session,
    get_call_id_by_control,
    get_session,
    map_control_id,
    update_session,
)
from backend.app.services.telephony.telnyx_handler import (
    hangup,
    start_streaming,
)

log = logging.getLogger(__name__)
router = APIRouter()

# Track active voice agent tasks per call so we can cancel on hangup
_active_agents: dict[str, asyncio.Task] = {}


@router.post("")
async def telnyx_webhook(request: Request):
    """
    Main Telnyx webhook endpoint.
    Receives all call events and dispatches to the appropriate handler.
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "invalid_json"}

    data = body.get("data", {})
    event_type = data.get("event_type", "")
    payload = data.get("payload", {})

    log.info("telnyx_event", event_type=event_type, call_control_id=payload.get("call_control_id", ""))

    # Dispatch to handler
    handler = _EVENT_HANDLERS.get(event_type)
    if handler:
        try:
            await handler(payload)
        except Exception as exc:
            log.exception("webhook_handler_error", event_type=event_type, error=str(exc))
    else:
        log.debug("unhandled_telnyx_event", event_type=event_type)

    # Always return 200 to Telnyx (they retry on non-2xx)
    return {"status": "ok"}


# ─── Event Handlers ───────────────────────────────────────────────────────────

async def _handle_call_initiated(payload: dict) -> None:
    """Call has been initiated (ringing on the other end)."""
    call_control_id = payload.get("call_control_id")
    client_state = payload.get("client_state", "")

    # Decode our call_id from client_state
    call_id = _decode_client_state(client_state)
    if not call_id:
        log.warning("call_initiated_no_client_state", control_id=call_control_id)
        return

    # Map control ID to our call ID
    if call_control_id:
        await map_control_id(call_control_id, call_id)

    # Update DB
    await _db_update_call(call_id, status=CallStatus.initiated)
    log.info("call_initiated", call_id=call_id, control_id=call_control_id)


async def _handle_call_answered(payload: dict) -> None:
    """
    Call was answered by a human. This is the critical moment:
    1. Start media streaming (audio fork to our WebSocket)
    2. The WebSocket handler will launch the voice agent
    """
    call_control_id = payload.get("call_control_id")
    client_state = payload.get("client_state", "")
    call_id = _decode_client_state(client_state)

    if not call_id:
        call_id = await get_call_id_by_control(call_control_id)

    if not call_id:
        log.error("call_answered_unknown", control_id=call_control_id)
        return

    # Update DB
    await _db_update_call(
        call_id,
        status=CallStatus.answered,
        answered_at=datetime.utcnow(),
        telnyx_call_control_id=call_control_id,
    )

    # Start media streaming → this triggers our WebSocket to receive audio
    success = await start_streaming(call_control_id, call_id)
    if success:
        log.info("streaming_started", call_id=call_id)
    else:
        log.error("streaming_start_failed", call_id=call_id)
        await hangup(call_control_id)


async def _handle_call_hangup(payload: dict) -> None:
    """Call ended — cleanup session, finalize call record."""
    call_control_id = payload.get("call_control_id")
    client_state = payload.get("client_state", "")
    call_id = _decode_client_state(client_state) or await get_call_id_by_control(call_control_id)

    if not call_id:
        log.warning("hangup_unknown_call", control_id=call_control_id)
        return

    hangup_cause = payload.get("hangup_cause", "unknown")

    # Cancel active voice agent task
    task = _active_agents.pop(call_id, None)
    if task and not task.done():
        task.cancel()
        log.info("voice_agent_cancelled", call_id=call_id)

    # Get session for final transcript
    session = await get_session(call_id)
    transcript = ""
    if session:
        transcript = _build_transcript(session.conversation_history)

    # Update DB with final state
    await _db_update_call(
        call_id,
        status=CallStatus.completed,
        ended_at=datetime.utcnow(),
        transcript=transcript,
    )

    # Cleanup Redis session
    await delete_session(call_id)

    log.info("call_completed", call_id=call_id, hangup_cause=hangup_cause)

    # Trigger post-call processing (async)
    asyncio.create_task(_post_call_processing(call_id))


async def _handle_machine_detection(payload: dict) -> None:
    """
    Answering machine detected.
    - If 'machine': leave voicemail or hang up
    - If 'human': proceed with normal conversation
    """
    call_control_id = payload.get("call_control_id")
    client_state = payload.get("client_state", "")
    call_id = _decode_client_state(client_state) or await get_call_id_by_control(call_control_id)

    result = payload.get("result", "")

    if result in ("machine", "fax"):
        log.info("machine_detected", call_id=call_id, result=result)

        # Update status
        if call_id:
            await _db_update_call(
                call_id,
                status=CallStatus.voicemail,
                outcome=CallOutcome.voicemail_left,
            )
            await update_session(call_id, status="ended")

        # TODO: Play voicemail script, then hangup
        # For now, just hang up
        if call_control_id:
            await hangup(call_control_id)

    elif result == "human":
        log.info("human_detected", call_id=call_id)
        # Normal flow — streaming should already be starting from call.answered


async def _handle_streaming_started(payload: dict) -> None:
    """Media streaming has started — audio pipeline is now active."""
    call_control_id = payload.get("call_control_id")
    call_id = await get_call_id_by_control(call_control_id)
    log.info("streaming_confirmed", call_id=call_id, control_id=call_control_id)


async def _handle_streaming_stopped(payload: dict) -> None:
    """Media streaming has stopped."""
    call_control_id = payload.get("call_control_id")
    call_id = await get_call_id_by_control(call_control_id)
    log.info("streaming_stopped", call_id=call_id, control_id=call_control_id)


async def _handle_call_bridge(payload: dict) -> None:
    """Call was transferred/bridged to another number."""
    call_control_id = payload.get("call_control_id")
    call_id = await get_call_id_by_control(call_control_id)
    log.info("call_bridged", call_id=call_id)
    if call_id:
        await _db_update_call(call_id, outcome=CallOutcome.transferred_to_human)


async def _handle_recording_saved(payload: dict) -> None:
    """Recording is available."""
    call_control_id = payload.get("call_control_id")
    call_id = await get_call_id_by_control(call_control_id)
    recording_url = payload.get("recording_urls", {}).get("mp3", "")

    if call_id and recording_url:
        await _db_update_call(call_id, recording_url=recording_url)
        log.info("recording_saved", call_id=call_id, url=recording_url)


# ─── Event dispatcher ─────────────────────────────────────────────────────────

_EVENT_HANDLERS = {
    "call.initiated": _handle_call_initiated,
    "call.answered": _handle_call_answered,
    "call.hangup": _handle_call_hangup,
    "call.machine.detection.ended": _handle_machine_detection,
    "streaming.started": _handle_streaming_started,
    "streaming.stopped": _handle_streaming_stopped,
    "call.bridged": _handle_call_bridge,
    "recording.saved": _handle_recording_saved,
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _decode_client_state(client_state: str) -> str | None:
    """Decode our call_id from base64 client_state."""
    if not client_state:
        return None
    try:
        return base64.b64decode(client_state).decode()
    except Exception:
        return None


def _build_transcript(conversation_history: list[dict]) -> str:
    """Build a readable transcript from conversation turns."""
    lines = []
    for turn in conversation_history:
        role = turn.get("role", "unknown").upper()
        content = turn.get("content", "")
        lines.append(f"[{role}]: {content}")
    return "\n".join(lines)


async def _db_update_call(call_id: str, **fields) -> None:
    """Update call fields in the database."""
    try:
        import uuid
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Call)
                .where(Call.id == uuid.UUID(call_id))
                .values(**fields)
            )
            await db.commit()
    except Exception as exc:
        log.exception("db_update_call_error", call_id=call_id, error=str(exc))


async def _post_call_processing(call_id: str) -> None:
    """
    Post-call async processing:
    - Generate AI summary
    - Classify outcome
    - Detect sentiment
    - Push to CRM webhook
    """
    try:
        import uuid
        from backend.app.services.llm.gemini import complete

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(Call).where(Call.id == uuid.UUID(call_id))
            )
            call = result.scalar_one_or_none()
            if not call or not call.transcript:
                return

            # Generate AI summary
            summary_prompt = """Analyze this sales call transcript and provide:
1. A 2-3 sentence summary
2. Call outcome (meeting_booked, not_interested, callback_requested, bad_number, voicemail_left, no_answer, transferred_to_human, unknown)
3. Sentiment (positive, neutral, negative)

Respond in this exact JSON format:
{"summary": "...", "outcome": "...", "sentiment": "..."}"""

            response_text, _ = await complete(
                system_prompt=summary_prompt,
                conversation_history=[],
                user_message=call.transcript,
                tier="fast",
            )

            # Parse the response
            import json
            try:
                analysis = json.loads(response_text)
                await db.execute(
                    update(Call)
                    .where(Call.id == uuid.UUID(call_id))
                    .values(
                        ai_summary=analysis.get("summary", response_text),
                        outcome=analysis.get("outcome", "unknown"),
                        sentiment=analysis.get("sentiment", "neutral"),
                    )
                )
                await db.commit()
                log.info("post_call_analysis_complete", call_id=call_id)
            except json.JSONDecodeError:
                await db.execute(
                    update(Call)
                    .where(Call.id == uuid.UUID(call_id))
                    .values(ai_summary=response_text)
                )
                await db.commit()

    except Exception as exc:
        log.exception("post_call_processing_error", call_id=call_id, error=str(exc))


def register_agent_task(call_id: str, task: asyncio.Task) -> None:
    """Register an active voice agent task so it can be cancelled on hangup."""
    _active_agents[call_id] = task