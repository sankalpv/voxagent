"""
WebSocket endpoint for real-time audio streaming.
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
    await websocket.accept()
    log.warning("ws_connected call_id=%s", call_id)

    # Get the call session from Redis
    session = None
    try:
        session = await get_session(call_id)
        log.warning("ws_session call_id=%s found=%s", call_id, session is not None)
    except Exception as exc:
        log.warning("ws_session_error call_id=%s error=%s", call_id, str(exc))

    if not session:
        log.warning("ws_no_session call_id=%s", call_id)

    # Try to update session
    try:
        if session:
            await update_session(call_id, status="listening")
    except Exception:
        pass

    audio_in_queue: asyncio.Queue = asyncio.Queue()
    audio_out_queue: asyncio.Queue = asyncio.Queue()
    running = True

    async def receive_audio():
        nonlocal running
        try:
            while running:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                event = msg.get("event", "")

                if event == "media":
                    media = msg.get("media", {})
                    track = media.get("track", "")
                    if track == "inbound":
                        payload = media.get("payload", "")
                        if payload:
                            audio_bytes = base64.b64decode(payload)
                            await audio_in_queue.put(audio_bytes)

                elif event == "start":
                    log.warning("ws_stream_start call_id=%s", call_id)

                elif event == "stop":
                    log.warning("ws_stream_stop call_id=%s", call_id)
                    running = False
                    break

        except WebSocketDisconnect:
            log.warning("ws_disconnected call_id=%s", call_id)
        except Exception as exc:
            log.warning("ws_receive_error call_id=%s error=%s", call_id, str(exc))
        finally:
            running = False
            await audio_in_queue.put(None)

    async def send_audio():
        nonlocal running
        chunk_index = 0
        try:
            while running:
                audio_bytes = await audio_out_queue.get()
                if audio_bytes is None:
                    continue

                payload = base64.b64encode(audio_bytes).decode()
                media_msg = {"event": "media", "media": {"payload": payload}}
                try:
                    await websocket.send_text(json.dumps(media_msg))
                    chunk_index += 1
                except Exception:
                    break

                mark_msg = {"event": "mark", "mark": {"name": "chunk_%d" % chunk_index}}
                try:
                    await websocket.send_text(json.dumps(mark_msg))
                except Exception:
                    break

        except Exception as exc:
            log.warning("ws_send_error call_id=%s error=%s", call_id, str(exc))
        finally:
            running = False

    async def run_voice_agent():
        nonlocal running
        try:
            log.warning("voice_agent_starting call_id=%s", call_id)
            from backend.app.agents.voice_agent import VoiceAgent

            agent = VoiceAgent(
                call_id=call_id,
                audio_in_queue=audio_in_queue,
                audio_out_queue=audio_out_queue,
            )
            await agent.run()
            log.warning("voice_agent_finished call_id=%s", call_id)
        except asyncio.CancelledError:
            log.warning("voice_agent_cancelled call_id=%s", call_id)
        except Exception as exc:
            log.warning("voice_agent_error call_id=%s error=%s type=%s", call_id, str(exc), type(exc).__name__)
            import traceback
            log.warning("voice_agent_traceback: %s", traceback.format_exc())
        finally:
            running = False

    from backend.app.api.routes.webhooks.telnyx import register_agent_task
    agent_task = asyncio.create_task(run_voice_agent())
    register_agent_task(call_id, agent_task)

    try:
        results = await asyncio.gather(
            receive_audio(),
            send_audio(),
            agent_task,
            return_exceptions=True,
        )
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                log.warning("ws_task_%d_error: %s %s", i, type(r).__name__, str(r))
    except Exception as exc:
        log.warning("ws_pipeline_error call_id=%s error=%s", call_id, str(exc))
    finally:
        running = False
        await audio_in_queue.put(None)
        await audio_out_queue.put(None)
        try:
            await websocket.close()
        except Exception:
            pass
        log.warning("ws_closed call_id=%s", call_id)