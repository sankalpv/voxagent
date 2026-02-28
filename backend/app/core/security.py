"""
API authentication and tenant resolution.

Two auth schemes:
1. X-API-Key header → tenant API key (for external callers / CRM integrations)
2. Internal service key → for Telnyx webhooks and inter-service calls

Every authenticated request gets a resolved tenant_id attached to the request state.
"""

import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.db.database import get_db
from backend.app.db.models import Tenant

log = logging.getLogger(__name__)


async def resolve_tenant(
    request: Request,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """
    Resolve the calling tenant from their API key.
    Attaches tenant to request.state for downstream use.
    """
    result = await db.execute(
        select(Tenant).where(Tenant.api_key == x_api_key, Tenant.is_active == True)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key",
        )

    # Set tenant on request state for RLS and downstream access
    request.state.tenant_id = tenant.id
    request.state.tenant = tenant

    # Set PostgreSQL session variable for row-level security
    await db.execute(
        __import__("sqlalchemy").text(
            f"SET LOCAL app.current_tenant_id = '{tenant.id}'"
        )
    )

    return tenant


async def verify_internal_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> bool:
    """
    Verify the internal service API key (for Telnyx webhooks, etc.).
    This doesn't resolve a tenant — the tenant comes from the webhook payload.
    """
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )
    return True


async def verify_telnyx_webhook(request: Request) -> dict:
    """
    Verify and parse a Telnyx webhook event.
    In production, you'd verify the Telnyx webhook signature here.
    For now, we parse the JSON body directly.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    # Telnyx wraps events in {"data": {"event_type": ..., "payload": {...}}}
    data = body.get("data", {})
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing event data",
        )

    return data


# Type aliases for dependency injection
TenantDep = Annotated[Tenant, Depends(resolve_tenant)]