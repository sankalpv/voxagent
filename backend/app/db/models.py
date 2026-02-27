"""
SQLAlchemy ORM models. Multi-tenant with row-level security enforced at the DB level
(see migrations/001_initial.sql). Application code always filters by tenant_id.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON, BigInteger, Boolean, DateTime, ForeignKey,
    Integer, Numeric, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────

class CallStatus(str, PyEnum):
    pending = "pending"
    initiated = "initiated"
    ringing = "ringing"
    answered = "answered"
    voicemail = "voicemail"
    completed = "completed"
    failed = "failed"
    no_answer = "no_answer"


class CallOutcome(str, PyEnum):
    meeting_booked = "meeting_booked"
    not_interested = "not_interested"
    callback_requested = "callback_requested"
    bad_number = "bad_number"
    voicemail_left = "voicemail_left"
    no_answer = "no_answer"
    transferred_to_human = "transferred_to_human"
    unknown = "unknown"


class CallDirection(str, PyEnum):
    outbound = "outbound"
    inbound = "inbound"


# ─── Tenant ───────────────────────────────────────────────────────────────────

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(50), default="standard")  # economy|standard|premium
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    agents: Mapped[list["AgentConfig"]] = relationship("AgentConfig", back_populates="tenant")
    calls: Mapped[list["Call"]] = relationship("Call", back_populates="tenant")


# ─── Agent Configuration ──────────────────────────────────────────────────────

class AgentConfig(Base):
    """
    Domain-agnostic agent configuration. Everything the agent needs to know
    about its persona, goal, and behaviour is expressed in natural language prompts.
    No flowcharts, no decision trees.
    """
    __tablename__ = "agent_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Natural language configuration — the entire call logic lives here
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    persona: Mapped[str] = mapped_column(Text, default="")
    primary_goal: Mapped[str] = mapped_column(Text, default="")
    constraints: Mapped[str] = mapped_column(Text, default="")
    escalation_policy: Mapped[str] = mapped_column(Text, default="")

    # Voice settings
    voice_name: Mapped[str] = mapped_column(String(100), default="en-US-Journey-D")
    language_code: Mapped[str] = mapped_column(String(20), default="en-US")

    # Tools enabled for this agent (list of tool names)
    enabled_tools: Mapped[list] = mapped_column(JSON, default=list)

    # Optional voicemail script (AI-generated if null)
    voicemail_script: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    max_call_duration_seconds: Mapped[int] = mapped_column(Integer, default=600)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="agents")
    calls: Mapped[list["Call"]] = relationship("Call", back_populates="agent")


# ─── Contact ──────────────────────────────────────────────────────────────────

class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    extra_data: Mapped[dict] = mapped_column("metadata", JSON, default=dict)  # arbitrary CRM data
    is_dnc: Mapped[bool] = mapped_column(Boolean, default=False)  # Do Not Call
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    calls: Mapped[list["Call"]] = relationship("Call", back_populates="contact")


# ─── Call ─────────────────────────────────────────────────────────────────────

class Call(Base):
    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_configs.id"), nullable=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)

    # Telnyx identifiers
    telnyx_call_control_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    telnyx_call_leg_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    direction: Mapped[str] = mapped_column(String(20), default=CallDirection.outbound)
    to_number: Mapped[str] = mapped_column(String(50), nullable=False)
    from_number: Mapped[str] = mapped_column(String(50), nullable=False)

    status: Mapped[str] = mapped_column(String(50), default=CallStatus.pending)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Post-call intelligence
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)  # positive|neutral|negative

    # Cost tracking (in USD)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)

    # Recording
    recording_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="calls")
    agent: Mapped["AgentConfig | None"] = relationship("AgentConfig", back_populates="calls")
    contact: Mapped["Contact | None"] = relationship("Contact", back_populates="calls")
    events: Mapped[list["CallEvent"]] = relationship("CallEvent", back_populates="call", order_by="CallEvent.created_at")


# ─── CallEvent (turn-by-turn log) ─────────────────────────────────────────────

class CallEvent(Base):
    """One row per conversation turn. Builds the full transcript."""
    __tablename__ = "call_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id"), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | agent | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tool_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    call: Mapped["Call"] = relationship("Call", back_populates="events")
