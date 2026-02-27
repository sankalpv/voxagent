"""
Voice Agent — the real-time conversation orchestrator.

This is THE core of the platform. One VoiceAgent instance runs per active call.

Pipeline per turn:
  1. STT streams μ-law audio → final transcript (~200ms)
  2. LLM generates response with optional tool calls (~300ms)
  3. TTS synthesizes sentence-by-sentence (~150ms per sentence)
  Total: ~700ms first-audio latency

Key design decisions:
- Sentence-level TTS flushing: start speaking sentence 1 while LLM generates sentence 2
- Interruption handling: if caller speaks while agent is speaking, cancel TTS and listen
- Sliding context window: last 20 turns to avoid context overflow
- Tool calls: LLM can invoke tools mid-conversation (book meeting, lookup CRM, etc.)
- Graceful ending: agent detects conversation end and hangs up
"""

import asyncio
import logging
import time
from datetime import datetime

from backend.app.services.llm.gemini import (
    ToolDefinition,
    complete,
    stream_complete,
)
from backend.app.services.memory.short_term import (
    CallSession,
    ConversationTurn,
    append_turn,
    get_recent_turns,
    get_session,
    set_speaking,
    update_session,
)
from backend.app.services.stt.google_stt import StreamingSTT
from backend.app.services.tts.google_tts import synthesize, synthesize_streaming

log = logging.getLogger(__name__)

# Maximum turns before we end the call (safety limit)
MAX_TURNS = 100
# Silence timeout: if no speech detected for this long, agent prompts or ends call
SILENCE_TIMEOUT_SECONDS = 15
# Maximum call duration
MAX_CALL_DURATION_SECONDS = 600


class VoiceAgent:
    """
    Orchestrates a single AI phone call.

    Lifecycle:
    1. __init__: receives queues from WebSocket handler
    2. run(): main loop
       a. Deliver opening greeting
       b. Listen for caller speech (STT)
       c. Process transcript through LLM
       d. Handle tool calls if any
       e. Synthesize and send response (TTS)
       f. Repeat until call ends
    3. Cleanup on cancellation/hangup
    """

    def __init__(
        self,
        call_id: str,
        audio_in_queue: asyncio.Queue,
        audio_out_queue: asyncio.Queue,
    ):
        self.call_id = call_id
        self.audio_in_queue = audio_in_queue
        self.audio_out_queue = audio_out_queue
        self.session: CallSession | None = None
        self.turn_count = 0
        self.is_speaking = False
        self.should_end_call = False
        self.call_start = time.time()

    async def run(self) -> None:
        """Main agent loop."""
        log.warning("voice_agent_run_start call_id=%s", self.call_id)

        # Load session from Redis
        try:
            self.session = await get_session(self.call_id)
        except Exception as exc:
            log.warning("voice_agent_redis_error call_id=%s error=%s", self.call_id, str(exc))

        # If no Redis session, build one from the database
        if not self.session:
            log.warning("voice_agent_no_redis_session call_id=%s - loading from DB", self.call_id)
            try:
                self.session = await self._build_session_from_db()
            except Exception as exc:
                log.warning("voice_agent_db_session_error call_id=%s error=%s", self.call_id, str(exc))
                import traceback
                log.warning("traceback: %s", traceback.format_exc())

        if not self.session:
            log.warning("voice_agent_no_session call_id=%s - cannot proceed", self.call_id)
            return

        log.warning("voice_agent_started call_id=%s agent=%s", self.call_id, self.session.agent_config_id)

        try:
            # Step 1: Deliver opening greeting
            await self._deliver_greeting()

            # Step 2: Main conversation loop
            async with StreamingSTT() as stt:
                # Start feeding audio to STT in background
                stt_feeder = asyncio.create_task(self._feed_stt(stt))

                try:
                    # Listen for transcripts and process them
                    async for transcript in stt.transcripts():
                        if self.should_end_call:
                            break

                        if self._is_over_time():
                            await self._handle_timeout()
                            break

                        # Process this turn
                        await self._process_turn(transcript)
                        self.turn_count += 1

                        if self.turn_count >= MAX_TURNS:
                            log.warning("max_turns_reached", call_id=self.call_id)
                            await self._end_call("I appreciate your time. Let me wrap up here. Thank you for chatting with me today!")
                            break

                finally:
                    stt_feeder.cancel()
                    try:
                        await stt_feeder
                    except asyncio.CancelledError:
                        pass

        except asyncio.CancelledError:
            log.warning("voice_agent_cancelled call_id=%s", self.call_id)
        except Exception as exc:
            log.warning("voice_agent_run_error call_id=%s error=%s", self.call_id, str(exc))
            import traceback
            log.warning("traceback: %s", traceback.format_exc())
        finally:
            try:
                await update_session(self.call_id, status="ended")
            except Exception:
                pass
            log.warning("voice_agent_ended call_id=%s turns=%d duration=%.1fs", self.call_id, self.turn_count, time.time() - self.call_start)

    # ─── Build session from DB ────────────────────────────────────────────────

    async def _build_session_from_db(self) -> CallSession | None:
        """Build a CallSession from the database when Redis doesn't have one."""
        import uuid
        from backend.app.db.database import AsyncSessionLocal
        from backend.app.db.models import Call, AgentConfig
        from sqlalchemy import select
        from backend.app.services.llm.gemini import build_system_prompt

        async with AsyncSessionLocal() as db:
            # Get the call record
            result = await db.execute(
                select(Call).where(Call.id == uuid.UUID(self.call_id))
            )
            call = result.scalar_one_or_none()
            if not call or not call.agent_id:
                log.warning("_build_session: no call found for %s", self.call_id)
                return None

            # Get the agent config
            result = await db.execute(
                select(AgentConfig).where(AgentConfig.id == call.agent_id)
            )
            agent = result.scalar_one_or_none()
            if not agent:
                log.warning("_build_session: no agent found for call %s", self.call_id)
                return None

            system_prompt = build_system_prompt(
                agent_name=agent.name,
                company_name=agent.persona.split(",")[0] if agent.persona else agent.name,
                persona=agent.persona,
                primary_goal=agent.primary_goal,
                constraints=agent.constraints,
                escalation_policy=agent.escalation_policy,
            )

            session = CallSession(
                call_id=self.call_id,
                tenant_id=str(call.tenant_id),
                agent_config_id=str(agent.id),
                contact_phone=call.to_number,
                system_prompt=system_prompt,
                voice_name=agent.voice_name,
                enabled_tools=agent.enabled_tools or [],
            )
            log.warning("_build_session: built from DB for call %s agent %s", self.call_id, agent.name)
            return session

    # ─── Greeting ─────────────────────────────────────────────────────────────

    async def _deliver_greeting(self) -> None:
        """
        Generate and deliver the opening greeting.
        The LLM generates this based on the system prompt + context.
        """
        turn_start = time.time()

        greeting_text, tool_calls = await complete(
            system_prompt=self.session.system_prompt,
            conversation_history=[],
            user_message="[SYSTEM: The call has just been answered. Deliver your opening greeting. Be warm and natural.]",
            tier="fast",
        )

        if not greeting_text:
            greeting_text = "Hi there! Thanks for picking up. How are you doing today?"

        # Synthesize and send
        await self._speak(greeting_text)

        # Log the greeting turn
        latency = int((time.time() - turn_start) * 1000)
        await self._log_turn("agent", greeting_text, 0, latency)

        log.info("greeting_delivered", call_id=self.call_id, latency_ms=latency)

    # ─── Turn Processing ──────────────────────────────────────────────────────

    async def _process_turn(self, transcript: str) -> None:
        """
        Process a single conversation turn:
        1. Log the user's speech
        2. Get LLM response
        3. Handle any tool calls
        4. Speak the response
        """
        turn_start = time.time()
        turn_index = self.turn_count + 1

        log.info("turn_start", call_id=self.call_id, turn=turn_index, transcript=transcript[:100])

        # Log user turn
        await self._log_turn("user", transcript, turn_index)

        # Get conversation history (sliding window)
        recent_turns = await get_recent_turns(self.call_id, n=20)
        history = [
            {"role": t.role, "content": t.content}
            for t in recent_turns
        ]

        # Build tool definitions if agent has tools enabled
        tool_defs = self._get_tool_definitions()

        # Get LLM response
        response_text, tool_calls = await complete(
            system_prompt=self.session.system_prompt,
            conversation_history=history,
            user_message=transcript,
            tool_defs=tool_defs,
            tier="fast",
        )

        # Handle tool calls if present
        if tool_calls:
            response_text = await self._handle_tool_calls(
                tool_calls, response_text, history, transcript
            )

        # Check if LLM wants to end the call
        if self._should_end(response_text):
            self.should_end_call = True

        # Speak the response
        if response_text:
            await self._speak(response_text)

        # Log agent turn
        latency = int((time.time() - turn_start) * 1000)
        await self._log_turn(
            "agent", response_text or "", turn_index + 1, latency,
            tool_calls=tool_calls,
        )

        log.info(
            "turn_complete",
            call_id=self.call_id,
            turn=turn_index,
            latency_ms=latency,
            has_tools=bool(tool_calls),
        )

        # If call should end, initiate hangup
        if self.should_end_call:
            await self._initiate_hangup()

    # ─── Tool Handling ────────────────────────────────────────────────────────

    async def _handle_tool_calls(
        self,
        tool_calls: list[dict],
        current_response: str,
        history: list[dict],
        user_message: str,
    ) -> str:
        """
        Execute tool calls and get updated response from LLM.
        While tools run, the agent says a natural filler.
        """
        # Say a filler while tools execute
        if not current_response:
            filler = "Let me check that for you real quick."
            await self._speak(filler)

        # Execute each tool
        from backend.app.services.tools.base import execute_tool
        tool_results = {}
        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc.get("args", {})
            log.info("tool_call", call_id=self.call_id, tool=tool_name, args=tool_args)

            try:
                result = await execute_tool(
                    tool_name=tool_name,
                    args=tool_args,
                    call_id=self.call_id,
                    tenant_id=self.session.tenant_id,
                )
                tool_results[tool_name] = result
                log.info("tool_result", call_id=self.call_id, tool=tool_name, success=result.get("success", False))
            except Exception as exc:
                tool_results[tool_name] = {"success": False, "error": str(exc)}
                log.exception("tool_error", call_id=self.call_id, tool=tool_name)

        # Feed tool results back to LLM for final response
        tool_context = "\n".join(
            f"Tool '{name}' returned: {result}"
            for name, result in tool_results.items()
        )

        updated_history = history + [
            {"role": "user", "content": user_message},
            {"role": "agent", "content": current_response or filler},
            {"role": "system", "content": f"TOOL RESULTS:\n{tool_context}"},
        ]

        final_text, _ = await complete(
            system_prompt=self.session.system_prompt,
            conversation_history=updated_history,
            user_message="[SYSTEM: Incorporate the tool results naturally into your response. Don't mention 'tools' — just share the information conversationally.]",
            tier="standard",
        )

        return final_text or current_response

    def _get_tool_definitions(self) -> list[ToolDefinition] | None:
        """Build Gemini tool definitions from the agent's enabled tools."""
        if not self.session or not self.session.enabled_tools:
            return None

        from backend.app.services.tools.base import get_tool_definitions
        return get_tool_definitions(self.session.enabled_tools)

    # ─── Speech Output ────────────────────────────────────────────────────────

    async def _speak(self, text: str) -> None:
        """
        Speak text to the caller using Telnyx's speak command.
        This uses Telnyx's built-in TTS which plays directly to the caller.
        """
        if not text.strip():
            return

        self.is_speaking = True
        log.warning("speak call_id=%s text=%s", self.call_id, text[:100])

        try:
            # Use Telnyx speak command instead of WebSocket audio
            import uuid
            from backend.app.db.database import AsyncSessionLocal
            from backend.app.db.models import Call
            from sqlalchemy import select
            import httpx
            from backend.app.core.config import settings

            # Get Telnyx call control ID
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Call.telnyx_call_control_id).where(
                        Call.id == uuid.UUID(self.call_id)
                    )
                )
                control_id = result.scalar_one_or_none()

            if control_id:
                # Pause STT to prevent echo (agent hearing itself)
                self._stt_paused = True

                # Use Telnyx speak command
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        f"https://api.telnyx.com/v2/calls/{control_id}/actions/speak",
                        headers={
                            "Authorization": f"Bearer {settings.telnyx_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "payload": text,
                            "voice": "google.en-US-Neural2-F",
                            "language": "en-US",
                        },
                    )
                    log.warning("speak_result call_id=%s status=%d", self.call_id, resp.status_code)
                    # Wait for speech to finish (rough estimate: 180ms per word + buffer)
                    word_count = len(text.split())
                    await asyncio.sleep(max(2.0, word_count * 0.18 + 1.0))

                # Resume STT after speaking
                self._stt_paused = False
            else:
                log.warning("speak_no_control_id call_id=%s", self.call_id)

        except Exception as exc:
            log.warning("speak_error call_id=%s error=%s", self.call_id, str(exc))
        finally:
            self.is_speaking = False

    # ─── STT Audio Feeding ────────────────────────────────────────────────────

    async def _feed_stt(self, stt: StreamingSTT) -> None:
        """Continuously feed audio from the WebSocket queue to STT. Pauses during agent speech."""
        self._stt_paused = False
        try:
            while True:
                audio_bytes = await self.audio_in_queue.get()
                if audio_bytes is None:
                    await stt.stop()
                    break
                # Skip audio while agent is speaking (prevents echo feedback loop)
                if not getattr(self, '_stt_paused', False):
                    stt.feed_audio(audio_bytes)
        except asyncio.CancelledError:
            await stt.stop()

    # ─── Call Lifecycle ───────────────────────────────────────────────────────

    def _is_over_time(self) -> bool:
        """Check if call has exceeded maximum duration."""
        elapsed = time.time() - self.call_start
        max_duration = MAX_CALL_DURATION_SECONDS
        if self.session and self.session.enabled_tools:
            # Allow more time if tools are involved
            max_duration = min(max_duration, 900)
        return elapsed > max_duration

    async def _handle_timeout(self) -> None:
        """Handle call timeout — gracefully end the call."""
        await self._end_call(
            "I want to be respectful of your time. Thank you so much for speaking with me today. Have a great day!"
        )

    def _should_end(self, response_text: str) -> bool:
        """Check if the LLM response indicates the call should end."""
        if not response_text:
            return False
        end_signals = [
            "[END_CALL]",
            "[HANGUP]",
            "goodbye",
            "have a great day",
            "take care",
            "thank you for your time",
        ]
        lower = response_text.lower()
        # Check for explicit end markers
        for signal in end_signals[:2]:
            if signal.lower() in lower:
                return True
        # Check for natural endings (only if they're at the end of the response)
        for signal in end_signals[2:]:
            if lower.rstrip(".!").endswith(signal):
                return True
        return False

    async def _end_call(self, farewell: str) -> None:
        """Deliver farewell and signal call end."""
        await self._speak(farewell)
        self.should_end_call = True

    async def _initiate_hangup(self) -> None:
        """Tell Telnyx to hang up the call."""
        try:
            # Small delay to let the farewell audio finish playing
            await asyncio.sleep(2.0)

            from backend.app.services.memory.short_term import get_session
            session = await get_session(self.call_id)
            if not session:
                return

            # Find the Telnyx call control ID
            from backend.app.services.memory.short_term import get_redis
            redis = await get_redis()

            # We need to find the control_id for this call
            # Scan for the mapping (in production, store this in session)
            from backend.app.db.database import AsyncSessionLocal
            from backend.app.db.models import Call
            from sqlalchemy import select
            import uuid

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Call.telnyx_call_control_id).where(
                        Call.id == uuid.UUID(self.call_id)
                    )
                )
                control_id = result.scalar_one_or_none()

            if control_id:
                from backend.app.services.telephony.telnyx_handler import hangup
                await hangup(control_id)
                log.info("agent_initiated_hangup", call_id=self.call_id)

        except Exception as exc:
            log.exception("hangup_error", call_id=self.call_id, error=str(exc))

    # ─── Logging ──────────────────────────────────────────────────────────────

    async def _log_turn(
        self,
        role: str,
        content: str,
        turn_index: int,
        latency_ms: int | None = None,
        tool_calls: list | None = None,
    ) -> None:
        """Log a conversation turn to Redis session."""
        turn = ConversationTurn(
            role=role,
            content=content,
            turn_index=turn_index,
            latency_ms=latency_ms,
            tool_calls=tool_calls,
        )
        await append_turn(self.call_id, turn)