"""
Calls API — Initiate outbound calls and query call history.

POST /api/v1/calls         → Initiate an outbound call
GET  /api/v1/calls         → List calls for this tenant
GET  /api/v1/calls/{id}    → Get a specific call with events
"""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.core.security import TenantDep
from backend.app.db.database import get_db
from backend.app.db.models import (
    AgentConfig, Call, CallDirection, CallEvent, CallStatus, Contact,
)

log = logging.getLogger(__name__)
router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class InitiateCallRequest(BaseModel):
    agent_id: UUID = Field(..., description="Agent configuration to use for this call")
    to_number: str = Field(..., pattern=r"^\+\d{10,15}$", description="E.164 phone number to call")
    contact_id: UUID | None = Field(default=None, description="Optional contact record to associate")
    contact_metadata: dict | None = Field(default=None, description="Ad-hoc metadata about the contact")


class CallResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    agent_id: UUID | None
    contact_id: UUID | None
    direction: str
    to_number: str
    from_number: str
    status: str
    outcome: str | None
    started_at: str | None
    answered_at: str | None
    ended_at: str | None
    duration_seconds: int | None
    transcript: str | None
    ai_summary: str | None
    sentiment: str | None
    cost_usd: float | None
    recording_url: str | None
    created_at: str

    model_config = {"from_attributes": True}


class CallEventResponse(BaseModel):
    id: UUID
    turn_index: int
    role: str
    content: str
    tool_calls: list | None
    tool_results: dict | None
    latency_ms: int | None
    created_at: str

    model_config = {"from_attributes": True}


class CallDetailResponse(CallResponse):
    events: list[CallEventResponse] = []


class CallListResponse(BaseModel):
    calls: list[CallResponse]
    total: int
    page: int
    page_size: int


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("", response_model=CallResponse, status_code=status.HTTP_201_CREATED)
async def initiate_call(
    body: InitiateCallRequest,
    tenant: TenantDep,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate an outbound AI call.

    1. Validates the agent config exists and belongs to this tenant
    2. Checks DNC list
    3. Creates a Call record in 'pending' status
    4. Triggers the Telnyx outbound call (async)

    The actual conversation happens via the Telnyx webhook → WebSocket pipeline.
    """
    # Validate agent exists
    agent = await _get_agent_or_404(body.agent_id, tenant.id, db)

    # Check DNC list
    from backend.app.services.tools.dnc import check_dnc
    is_dnc = await check_dnc(tenant.id, body.to_number, db)
    if is_dnc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Number {body.to_number} is on the Do Not Call list",
        )

    # Resolve or create contact
    contact_id = body.contact_id
    if not contact_id and body.to_number:
        contact = await _find_or_create_contact(
            tenant.id, body.to_number, body.contact_metadata or {}, db
        )
        contact_id = contact.id

    # Create call record
    from backend.app.core.config import settings
    call = Call(
        tenant_id=tenant.id,
        agent_id=body.agent_id,
        contact_id=contact_id,
        direction=CallDirection.outbound,
        to_number=body.to_number,
        from_number=settings.telnyx_from_number,
        status=CallStatus.pending,
        started_at=datetime.utcnow(),
    )
    db.add(call)
    await db.flush()
    await db.refresh(call)

    # Trigger the outbound call via Telnyx (non-blocking)
    import asyncio
    from backend.app.services.telephony.telnyx_handler import initiate_outbound_call
    asyncio.create_task(
        initiate_outbound_call(
            call_id=str(call.id),
            to_number=body.to_number,
            agent_config=agent,
            contact_metadata=body.contact_metadata,
        )
    )

    log.info(
        "call_initiated",
        call_id=str(call.id),
        to_number=body.to_number,
        agent=agent.name,
    )

    return _call_to_response(call)


@router.get("", response_model=CallListResponse)
async def list_calls(
    tenant: TenantDep,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    direction: str | None = None,
):
    """List calls for this tenant with pagination and optional filters."""
    query = select(Call).where(Call.tenant_id == tenant.id)

    if status_filter:
        query = query.where(Call.status == status_filter)
    if direction:
        query = query.where(Call.direction == direction)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(Call.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    calls = result.scalars().all()

    return CallListResponse(
        calls=[_call_to_response(c) for c in calls],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{call_id}", response_model=CallDetailResponse)
async def get_call(
    call_id: UUID,
    tenant: TenantDep,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific call with all conversation events."""
    result = await db.execute(
        select(Call)
        .options(selectinload(Call.events))
        .where(Call.id == call_id, Call.tenant_id == tenant.id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    events = [
        CallEventResponse(
            id=e.id,
            turn_index=e.turn_index,
            role=e.role,
            content=e.content,
            tool_calls=e.tool_calls,
            tool_results=e.tool_results,
            latency_ms=e.latency_ms,
            created_at=e.created_at.isoformat() if e.created_at else "",
        )
        for e in sorted(call.events, key=lambda e: e.turn_index)
    ]

    resp = _call_to_response(call)
    return CallDetailResponse(**resp.model_dump(), events=events)


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_agent_or_404(
    agent_id: UUID, tenant_id: UUID, db: AsyncSession
) -> AgentConfig:
    result = await db.execute(
        select(AgentConfig).where(
            AgentConfig.id == agent_id,
            AgentConfig.tenant_id == tenant_id,
            AgentConfig.is_active == True,
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found or inactive")
    return agent


async def _find_or_create_contact(
    tenant_id: UUID, phone: str, metadata: dict, db: AsyncSession
) -> Contact:
    result = await db.execute(
        select(Contact).where(
            Contact.tenant_id == tenant_id,
            Contact.phone_number == phone,
        )
    )
    contact = result.scalar_one_or_none()
    if contact:
        return contact

    contact = Contact(
        tenant_id=tenant_id,
        phone_number=phone,
        first_name=metadata.get("first_name"),
        last_name=metadata.get("last_name"),
        email=metadata.get("email"),
        company=metadata.get("company"),
        extra_data=metadata,
    )
    db.add(contact)
    await db.flush()
    await db.refresh(contact)
    return contact


def _call_to_response(call: Call) -> CallResponse:
    return CallResponse(
        id=call.id,
        tenant_id=call.tenant_id,
        agent_id=call.agent_id,
        contact_id=call.contact_id,
        direction=call.direction,
        to_number=call.to_number,
        from_number=call.from_number,
        status=call.status,
        outcome=call.outcome,
        started_at=call.started_at.isoformat() if call.started_at else None,
        answered_at=call.answered_at.isoformat() if call.answered_at else None,
        ended_at=call.ended_at.isoformat() if call.ended_at else None,
        duration_seconds=call.duration_seconds,
        transcript=call.transcript,
        ai_summary=call.ai_summary,
        sentiment=call.sentiment,
        cost_usd=float(call.cost_usd) if call.cost_usd else None,
        recording_url=call.recording_url,
        created_at=call.created_at.isoformat() if call.created_at else "",
    )