"""
Generic webhook tool — push data to any HTTP endpoint.

This is the Phase 1 CRM integration: any CRM that accepts webhooks
(which is all of them) can receive call data in real-time.

The agent can invoke this tool to push call outcome, notes, or
any structured data to a pre-configured webhook URL.
"""

import logging

import httpx

from backend.app.services.tools.base import register_tool

log = logging.getLogger(__name__)


async def _send_webhook(
    call_id: str,
    tenant_id: str,
    webhook_url: str = "",
    event_type: str = "call_update",
    data: dict | None = None,
    **kwargs,
) -> dict:
    """
    Send data to an HTTP webhook endpoint.

    This is the universal CRM connector — works with:
    - Salesforce (via Web-to-Lead or Flow)
    - HubSpot (via workflow webhooks)
    - Pipedrive (via webhooks)
    - Zapier/Make/n8n (via webhook triggers)
    - Any custom endpoint
    """
    if not webhook_url:
        return {
            "success": False,
            "error": "No webhook URL provided. Configure a webhook URL in the agent settings.",
        }

    payload = {
        "event_type": event_type,
        "call_id": call_id,
        "tenant_id": tenant_id,
        "data": data or {},
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            success = 200 <= resp.status_code < 300
            log.info(
                "webhook_sent",
                call_id=call_id,
                url=webhook_url,
                status=resp.status_code,
                success=success,
            )

            return {
                "success": success,
                "status_code": resp.status_code,
                "message": "Data sent successfully" if success else f"Webhook returned {resp.status_code}",
            }

    except httpx.TimeoutException:
        log.warning("webhook_timeout", call_id=call_id, url=webhook_url)
        return {
            "success": False,
            "error": "Webhook request timed out",
        }
    except Exception as exc:
        log.exception("webhook_error", call_id=call_id, url=webhook_url, error=str(exc))
        return {
            "success": False,
            "error": str(exc),
        }


# ─── Register the tool ────────────────────────────────────────────────────────

register_tool(
    name="send_webhook",
    description=(
        "Send data to an external webhook URL (e.g., CRM, Zapier, custom endpoint). "
        "Use this to push call outcomes, notes, or other structured data to external systems "
        "during or after the call."
    ),
    parameters={
        "type_": "OBJECT",
        "properties": {
            "webhook_url": {
                "type_": "STRING",
                "description": "The HTTP URL to send the webhook POST to",
            },
            "event_type": {
                "type_": "STRING",
                "description": "Type of event (e.g., 'meeting_booked', 'call_completed', 'callback_requested')",
            },
            "data": {
                "type_": "OBJECT",
                "description": "Arbitrary JSON data to include in the webhook payload",
                "properties": {},
            },
        },
        "required": ["webhook_url"],
    },
    func=_send_webhook,
)