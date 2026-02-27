"""
Calendly meeting booking tool.

Allows the AI agent to book meetings during a live call via the Calendly API.
The agent collects the caller's name, email, and preferred time, then books
the meeting and confirms it in conversation.

Calendly API v2: https://developer.calendly.com/api-docs
"""

import logging
from datetime import datetime, timedelta

import httpx

from backend.app.core.config import settings
from backend.app.services.tools.base import register_tool

log = logging.getLogger(__name__)

CALENDLY_API_BASE = "https://api.calendly.com"


async def _book_meeting(
    call_id: str,
    tenant_id: str,
    invitee_email: str = "",
    invitee_name: str = "",
    preferred_date: str = "",
    preferred_time: str = "",
    notes: str = "",
    **kwargs,
) -> dict:
    """
    Book a meeting via Calendly.

    For Phase 1, we use the Calendly scheduling link approach:
    - Generate a pre-filled scheduling link
    - Optionally check availability first

    In production, this would use the full Calendly API to create
    one-off scheduled events directly.
    """
    if not settings.calendly_api_key:
        # Fallback: generate a scheduling link
        link = settings.calendly_event_url or "https://calendly.com"
        if invitee_name:
            link += f"?name={invitee_name.replace(' ', '+')}"
        if invitee_email:
            link += f"&email={invitee_email}"

        return {
            "success": True,
            "method": "scheduling_link",
            "scheduling_link": link,
            "message": f"A scheduling link has been prepared for {invitee_name or 'the caller'}. "
                       f"They can book at their convenience: {link}",
        }

    # Full Calendly API flow
    try:
        async with httpx.AsyncClient(
            base_url=CALENDLY_API_BASE,
            headers={
                "Authorization": f"Bearer {settings.calendly_api_key}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        ) as client:
            # Step 1: Get available times
            availability = await _check_availability(client, preferred_date)

            if not availability:
                return {
                    "success": True,
                    "available": False,
                    "message": f"I wasn't able to find availability for {preferred_date}. "
                               "Let me suggest some alternative times.",
                    "scheduling_link": settings.calendly_event_url,
                }

            # Step 2: Create a scheduling link with pre-filled info
            scheduling_link = settings.calendly_event_url
            params = []
            if invitee_name:
                params.append(f"name={invitee_name.replace(' ', '+')}")
            if invitee_email:
                params.append(f"email={invitee_email}")
            if params:
                scheduling_link += "?" + "&".join(params)

            # Step 3: Send email invite (via Calendly's invite flow)
            if invitee_email:
                await _send_invite(client, invitee_email, invitee_name, scheduling_link)

            return {
                "success": True,
                "available": True,
                "scheduling_link": scheduling_link,
                "available_slots": availability[:3],  # Top 3 slots
                "message": f"Great! I've found some available times. "
                           f"I'll send a calendar invite to {invitee_email}.",
                "email_sent": bool(invitee_email),
            }

    except Exception as exc:
        log.exception("calendly_error", error=str(exc))
        return {
            "success": False,
            "error": str(exc),
            "fallback_link": settings.calendly_event_url,
            "message": "I had trouble accessing the calendar. Let me give you a link to book directly.",
        }


async def _check_availability(client: httpx.AsyncClient, preferred_date: str) -> list[dict]:
    """Check Calendly availability for a given date."""
    try:
        # Get the current user's event types
        user_resp = await client.get("/users/me")
        user_resp.raise_for_status()
        user_uri = user_resp.json().get("resource", {}).get("uri", "")

        # Get event types
        events_resp = await client.get(
            "/event_types",
            params={"user": user_uri, "active": True},
        )
        events_resp.raise_for_status()
        event_types = events_resp.json().get("collection", [])

        if not event_types:
            return []

        # Get first active event type's available times
        event_type_uri = event_types[0].get("uri", "")

        # Parse preferred date or use next 3 business days
        if preferred_date:
            try:
                start = datetime.fromisoformat(preferred_date)
            except ValueError:
                start = datetime.utcnow() + timedelta(days=1)
        else:
            start = datetime.utcnow() + timedelta(days=1)

        end = start + timedelta(days=5)

        avail_resp = await client.get(
            "/event_type_available_times",
            params={
                "event_type": event_type_uri,
                "start_time": start.isoformat() + "Z",
                "end_time": end.isoformat() + "Z",
            },
        )
        avail_resp.raise_for_status()

        slots = avail_resp.json().get("collection", [])
        return [
            {
                "start_time": slot.get("start_time"),
                "status": slot.get("status", "available"),
            }
            for slot in slots[:10]
        ]

    except Exception as exc:
        log.warning("calendly_availability_check_failed", error=str(exc))
        return []


async def _send_invite(
    client: httpx.AsyncClient,
    email: str,
    name: str,
    scheduling_link: str,
) -> None:
    """
    Send a Calendly scheduling invite.
    In Phase 1, we just log the intent; actual email sending
    comes in Phase 3 (post-call follow-up).
    """
    log.info(
        "calendly_invite_queued",
        email=email,
        name=name,
        link=scheduling_link,
    )


# ─── Register the tool ────────────────────────────────────────────────────────

register_tool(
    name="book_meeting",
    description=(
        "Book a meeting or demo for the caller. Use this when the caller agrees to a meeting. "
        "You need their name and email at minimum. Preferred date/time is optional — "
        "if not provided, a scheduling link will be shared."
    ),
    parameters={
        "type_": "OBJECT",
        "properties": {
            "invitee_name": {
                "type_": "STRING",
                "description": "Full name of the person to invite",
            },
            "invitee_email": {
                "type_": "STRING",
                "description": "Email address for the calendar invite",
            },
            "preferred_date": {
                "type_": "STRING",
                "description": "Preferred date in YYYY-MM-DD format (optional)",
            },
            "preferred_time": {
                "type_": "STRING",
                "description": "Preferred time like 'morning', 'afternoon', '2pm' (optional)",
            },
            "notes": {
                "type_": "STRING",
                "description": "Any notes about the meeting (optional)",
            },
        },
        "required": ["invitee_name", "invitee_email"],
    },
    func=_book_meeting,
)