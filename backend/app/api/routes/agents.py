"""
Agent Configuration CRUD API.

Agents are configured entirely through natural language — no flowcharts, no decision trees.
The system_prompt, persona, primary_goal, constraints, and escalation_policy fields
define the complete call logic.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import TenantDep
from backend.app.db.database import get_db
from backend.app.db.models import AgentConfig, Tenant

log = logging.getLogger(__name__)
router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    system_prompt: str = Field(..., min_length=10, description="The full system prompt — this IS the call logic")
    persona: str = Field(default="", description="Natural language persona description")
    primary_goal: str = Field(default="", description="What the agent should achieve on each call")
    constraints: str = Field(default="", description="Rules and boundaries in natural language")
    escalation_policy: str = Field(default="", description="When/how to escalate or end the call")
    voice_name: str = Field(default="en-US-Journey-D", description="Google TTS voice name")
    language_code: str = Field(default="en-US")
    enabled_tools: list[str] = Field(default_factory=list, description="Tool names this agent can use")
    voicemail_script: str | None = Field(default=None, description="Script for voicemail; AI-generated if null")
    max_call_duration_seconds: int = Field(default=600, ge=30, le=3600)


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    system_prompt: str | None = None
    persona: str | None = None
    primary_goal: str | None = None
    constraints: str | None = None
    escalation_policy: str | None = None
    voice_name: str | None = None
    language_code: str | None = None
    enabled_tools: list[str] | None = None
    voicemail_script: str | None = None
    max_call_duration_seconds: int | None = None
    is_active: bool | None = None


class AgentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    is_active: bool
    system_prompt: str
    persona: str
    primary_goal: str
    constraints: str
    escalation_policy: str
    voice_name: str
    language_code: str
    enabled_tools: list[str]
    voicemail_script: str | None
    max_call_duration_seconds: int
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreateRequest,
    tenant: TenantDep,
    db: AsyncSession = Depends(get_db),
):
    """Create a new AI agent configuration for this tenant."""
    agent = AgentConfig(
        tenant_id=tenant.id,
        name=body.name,
        system_prompt=body.system_prompt,
        persona=body.persona,
        primary_goal=body.primary_goal,
        constraints=body.constraints,
        escalation_policy=body.escalation_policy,
        voice_name=body.voice_name,
        language_code=body.language_code,
        enabled_tools=body.enabled_tools,
        voicemail_script=body.voicemail_script,
        max_call_duration_seconds=body.max_call_duration_seconds,
    )
    db.add(agent)
    await db.flush()
    await db.refresh(agent)
    return _to_response(agent)


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    tenant: TenantDep,
    db: AsyncSession = Depends(get_db),
    active_only: bool = True,
):
    """List all agent configurations for this tenant."""
    query = select(AgentConfig).where(AgentConfig.tenant_id == tenant.id)
    if active_only:
        query = query.where(AgentConfig.is_active == True)
    query = query.order_by(AgentConfig.created_at.desc())
    result = await db.execute(query)
    agents = result.scalars().all()
    return [_to_response(a) for a in agents]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    tenant: TenantDep,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific agent configuration."""
    agent = await _get_agent_or_404(agent_id, tenant.id, db)
    return _to_response(agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    body: AgentUpdateRequest,
    tenant: TenantDep,
    db: AsyncSession = Depends(get_db),
):
    """Update an agent configuration. Only provided fields are updated."""
    agent = await _get_agent_or_404(agent_id, tenant.id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)

    await db.flush()
    await db.refresh(agent)
    return _to_response(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    tenant: TenantDep,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete an agent by marking it inactive."""
    agent = await _get_agent_or_404(agent_id, tenant.id, db)
    agent.is_active = False
    await db.flush()


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_agent_or_404(
    agent_id: UUID, tenant_id: UUID, db: AsyncSession
) -> AgentConfig:
    result = await db.execute(
        select(AgentConfig).where(
            AgentConfig.id == agent_id,
            AgentConfig.tenant_id == tenant_id,
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


def _to_response(agent: AgentConfig) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        tenant_id=agent.tenant_id,
        name=agent.name,
        is_active=agent.is_active,
        system_prompt=agent.system_prompt,
        persona=agent.persona,
        primary_goal=agent.primary_goal,
        constraints=agent.constraints,
        escalation_policy=agent.escalation_policy,
        voice_name=agent.voice_name,
        language_code=agent.language_code,
        enabled_tools=agent.enabled_tools or [],
        voicemail_script=agent.voicemail_script,
        max_call_duration_seconds=agent.max_call_duration_seconds,
        created_at=agent.created_at.isoformat() if agent.created_at else "",
        updated_at=agent.updated_at.isoformat() if agent.updated_at else "",
    )