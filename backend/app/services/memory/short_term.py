"""
Short-term call session memory backed by Redis.
Stores conversation history, call state, and tool results for the duration of a call.
TTL: 1 hour (well beyond the longest realistic call).
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis

from backend.app.core.config import settings


@dataclass
class ConversationTurn:
    role: str   # "user" | "agent" | "system"
    content: str
    turn_index: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    tool_calls: list | None = None
    tool_results: dict | None = None
    latency_ms: int | None = None


@dataclass
class CallSession:
    call_id: str
    tenant_id: str
    agent_config_id: str
    contact_phone: str
    system_prompt: str
    voice_name: str
    enabled_tools: list[str]
    status: str = "greeting"       # greeting|listening|processing|speaking|ended
    is_agent_speaking: bool = False
    turn_count: int = 0
    conversation_history: list[dict] = field(default_factory=list)
    tool_results_pending: dict = field(default_factory=dict)
    contact_metadata: dict = field(default_factory=dict)
    call_start_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())


_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _session_key(call_id: str) -> str:
    return f"session:{call_id}"


async def create_session(session: CallSession) -> None:
    redis = await get_redis()
    key = _session_key(session.call_id)
    await redis.setex(key, 3600, json.dumps(asdict(session)))


async def get_session(call_id: str) -> CallSession | None:
    redis = await get_redis()
    raw = await redis.get(_session_key(call_id))
    if not raw:
        return None
    data = json.loads(raw)
    # Deserialize nested ConversationTurn list
    session = CallSession(**{k: v for k, v in data.items()})
    return session


async def update_session(call_id: str, **updates: Any) -> CallSession | None:
    redis = await get_redis()
    key = _session_key(call_id)
    raw = await redis.get(key)
    if not raw:
        return None
    data = json.loads(raw)
    data.update(updates)
    await redis.setex(key, 3600, json.dumps(data))
    return CallSession(**data)


async def append_turn(call_id: str, turn: ConversationTurn) -> None:
    redis = await get_redis()
    key = _session_key(call_id)
    raw = await redis.get(key)
    if not raw:
        return
    data = json.loads(raw)
    data["conversation_history"].append(asdict(turn))
    data["turn_count"] = data.get("turn_count", 0) + 1
    await redis.setex(key, 3600, json.dumps(data))


async def get_recent_turns(call_id: str, n: int = 20) -> list[ConversationTurn]:
    session = await get_session(call_id)
    if not session:
        return []
    history = session.conversation_history[-n:]
    return [ConversationTurn(**t) for t in history]


async def delete_session(call_id: str) -> None:
    redis = await get_redis()
    await redis.delete(_session_key(call_id))


async def set_speaking(call_id: str, is_speaking: bool) -> None:
    await update_session(call_id, is_agent_speaking=is_speaking)


# ─── Map Telnyx call_control_id → our call_id ─────────────────────────────────

async def map_control_id(telnyx_control_id: str, call_id: str) -> None:
    redis = await get_redis()
    await redis.setex(f"ctrl:{telnyx_control_id}", 7200, call_id)


async def get_call_id_by_control(telnyx_control_id: str) -> str | None:
    redis = await get_redis()
    return await redis.get(f"ctrl:{telnyx_control_id}")
