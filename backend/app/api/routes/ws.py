"""
WebSocket endpoint for real-time audio streaming.

Telnyx forks call audio to this WebSocket. We:
1. Receive μ-law audio from the caller
2. Feed it to Google STT for transcription
3. Process transcripts through the voice agent (LLM)
4. Synthesize responses via TTS
5. Send μ-law audio back to the caller

This is the beating heart of the real-time voice pipeline.

Telnyx WebSocket media format:
  Inbound: {"event": "media", "media": {"payload": "<base64 μ-law>", "track": "inbound"}}
  Outbound: {"event": "media", "media": {"payload": "<base64 μ-law>"}}
"""

import asyncio
import base64
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.services.memory.short_term import get_session, update_session

log = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/calls/{call_id}")
async def call_audio_websocket(websocket: WebSocket, call_id: str):
    """
    WebSocket handler for a single call's audio stream.
    Launched when Telnyx starts media streaming after call.answered.
    """
    await websocket.accept()
    log.info("ws_connected", call_id=call_id)

    # Get the call session from Redis
    session = await get_session(call_id)
    if not session:
        log.error("ws_no_session", call_id=call_id)
        await websocket.close(code=1008, reason="No session found")
        return

    # Update session status
    await update_session(call_id, status="listening")

    # Create queues for the pipeline
    audio_in_queue: asyncio.Queue[bytes | None] = asyncio.Queue()     # STT input
    text_out_queue: asyncio.Queue[str | None] = asyncio.Queue()       # LLM output
    audio_out_queue: asyncio.Queue[bytes | None] = asyncio.Queue()    # TTS output

    # Track if we should keep running
    running = True
    stream_id = None  # Telnyx stream ID for sending audio back

    async def receive_audio():
        """Receive audio from Telnyx WebSocket and feed to STT."""
        nonlocal running, stream_id
        try:
            while running:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                event = msg.get("event", "")

                if event == "media":
                    media = msg.get("media", {})
                    track = media.get("track", "")

                    # Only process inbound audio (caller's voice)
                    if track == "inbound":
                        payload = media.get("payload", "")
                        if payload:
                            audio_bytes = base64.b64decode(payload)
                            await audio_in_queue.put(audio_bytes)

                elif event == "start":
                    # Stream started — save stream ID for sending audio back
                    stream_id = msg.get("stream_id")
                    log.info("ws_stream_started", call_id=call_id, stream_id=stream_id)

                elif event == "stop":
                    log.info("ws_stream_stopped", call_id=call_id)
                    running = False
                    break

                elif event == "mark":
                    # Audio playback mark — TTS chunk finished playing
                    log.debug("ws_mark", call_id=call_id, name=msg.get("mark", {}).get("name"))

        except WebSocketDisconnect:
            log.info("ws_disconnected", call_id=call_id)
        except Exception as exc:
            log.exception("ws_receive_error", call_id=call_id, error=str(exc))
        finally:
            running = False
            await audio_in_queue.put(None)  # Signal STT to stop

    async def send_audio():
        """Read synthesized audio from TTS queue and send to Telnyx."""
        nonlocal running
        chunk_index = 0
        try:
            while running:
                audio_bytes = await audio_out_queue.get()
                if audio_bytes is None:
                    continue  # TTS stream ended for this turn, but call continues

                # Encode to base64 and send as Telnyx media event
                payload = base64.b64encode(audio_bytes).decode()
                media_msg = {
                    "event": "media",
                    "media": {
                        "payload": payload,
                    },
                }
                try:
                    await websocket.send_text(json.dumps(media_msg))
                    chunk_index += 1
                except Exception:
                    break

                # Send a mark after each chunk to track playback
                mark_msg = {
                    "event": "mark",
                    "mark": {"name": f"chunk_{chunk_index}"},
                }
                try:
                    await websocket.send_text(json.dumps(mark_msg))
                except Exception:
                    break

        except Exception as exc:
            log.exception("ws_send_error", call_id=call_id, error=str(exc))
        finally:
            running = False

    async def run_voice_agent():
        """Run the voice agent pipeline: STT → LLM → TTS."""
        nonlocal running
        try:
            from backend.app.agents.voice_agent import VoiceAgent

            agent = VoiceAgent(
                call_id=call_id,
                audio_in_queue=audio_in_queue,
                audio_out_queue=audio_out_queue,
            )
            await agent.run()
        except asyncio.CancelledError:
            log.info("voice_agent_cancelled", call_id=call_id)
        except Exception as exc:
            log.exception("voice_agent_error", call_id=call_id, error=str(exc))
        finally:
            running = False

    # Register the agent task for cancellation on hangup
    from backend.app.api.routes.webhooks.telnyx import register_agent_task

    # Run all three pipeline stages concurrently
    agent_task = asyncio.create_task(run_voice_agent())
    register_agent_task(call_id, agent_task)

    try:
        await asyncio.gather(
            receive_audio(),
            send_audio(),
            agent_task,
            return_exceptions=True,
        )
    except Exception as exc:
        log.exception("ws_pipeline_error", call_id=call_id, error=str(exc))
    finally:
        running = False
        # Ensure queues are drained
        await audio_in_queue.put(None)
        await audio_out_queue.put(None)

        try:
            await websocket.close()
        except Exception:
            pass

        log.info("ws_closed", call_id=call_id)