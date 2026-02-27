"""
WebSocket bridge: Telnyx Media Stream ↔ Gemini Live API.
Bidirectional real-time audio with transcoding.
"""

import asyncio
import base64
import json
import logging
import struct

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)
router = APIRouter()


def mulaw_to_pcm(mulaw_bytes: bytes) -> bytes:
    """Convert 8kHz mu-law to PCM (16-bit signed)."""
    BIAS = 0x84
    exp_lut = [0,132,396,924,1980,4092,8316,16764]
    result = bytearray(len(mulaw_bytes) * 2)
    for i, b in enumerate(mulaw_bytes):
        b = ~b & 0xFF
        sign = b & 0x80
        exp = (b >> 4) & 0x07
        mantissa = b & 0x0F
        sample = exp_lut[exp] + (mantissa << (exp + 3))
        if sign:
            sample = -sample
        struct.pack_into('<h', result, i * 2, max(-32768, min(32767, sample)))
    return bytes(result)


def pcm_to_mulaw(pcm_bytes: bytes) -> bytes:
    """Convert PCM (16-bit signed) to mu-law."""
    BIAS = 0x84
    CLIP = 32635
    exp_lut = [0,0,1,1,2,2,2,2,3,3,3,3,3,3,3,3,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,
               5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,
               6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,
               6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,
               7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,
               7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,
               7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,
               7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7]
    num_samples = len(pcm_bytes) // 2
    result = bytearray(num_samples)
    for i in range(num_samples):
        sample = struct.unpack_from('<h', pcm_bytes, i * 2)[0]
        sign = (sample >> 8) & 0x80
        if sign:
            sample = -sample
        sample = min(sample, CLIP) + BIAS
        exp = exp_lut[(sample >> 7) & 0xFF]
        mantissa = (sample >> (exp + 3)) & 0x0F
        result[i] = ~(sign | (exp << 4) | mantissa) & 0xFF
    return bytes(result)


def resample_pcm(pcm_bytes: bytes, from_rate: int, to_rate: int) -> bytes:
    """Simple linear resampling of PCM audio."""
    num_samples = len(pcm_bytes) // 2
    samples = struct.unpack(f'<{num_samples}h', pcm_bytes)
    ratio = to_rate / from_rate
    new_len = int(num_samples * ratio)
    result = []
    for i in range(new_len):
        src_idx = i / ratio
        idx = int(src_idx)
        frac = src_idx - idx
        if idx + 1 < num_samples:
            sample = int(samples[idx] * (1 - frac) + samples[idx + 1] * frac)
        else:
            sample = samples[min(idx, num_samples - 1)]
        result.append(max(-32768, min(32767, sample)))
    return struct.pack(f'<{len(result)}h', *result)


@router.websocket("/ws/calls/{call_id}")
async def call_audio_websocket(websocket: WebSocket, call_id: str):
    """Bidirectional bridge: Telnyx ↔ Gemini Live API."""
    await websocket.accept()
    log.warning("ws_connected call_id=%s", call_id)

    # Load agent config from DB for system prompt
    system_prompt = "You are a helpful AI sales agent. Keep responses short and natural."
    try:
        import uuid
        from backend.app.db.database import AsyncSessionLocal
        from backend.app.db.models import Call, AgentConfig
        from sqlalchemy import select
        from backend.app.services.llm.gemini import build_system_prompt

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Call).where(Call.id == uuid.UUID(call_id)))
            call = result.scalar_one_or_none()
            if call and call.agent_id:
                result = await db.execute(select(AgentConfig).where(AgentConfig.id == call.agent_id))
                agent = result.scalar_one_or_none()
                if agent:
                    system_prompt = build_system_prompt(
                        agent_name=agent.name,
                        company_name=agent.persona.split(",")[0] if agent.persona else agent.name,
                        persona=agent.persona, primary_goal=agent.primary_goal,
                        constraints=agent.constraints, escalation_policy=agent.escalation_policy,
                    )
                    log.warning("ws_agent_loaded call_id=%s agent=%s", call_id, agent.name)
    except Exception as exc:
        log.warning("ws_agent_load_error call_id=%s error=%s", call_id, str(exc))

    # Connect to Gemini Live API
    try:
        from google import genai
        from google.genai import types
        from backend.app.core.config import settings

        gemini_client = genai.Client(api_key=settings.gemini_api_key)

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=system_prompt)]
            ),
        )

        async with gemini_client.aio.live.connect(
            model="gemini-2.5-flash-native-audio-dialog",
            config=config,
        ) as gemini_session:
            log.warning("gemini_live_connected call_id=%s", call_id)

            # Send initial greeting prompt
            await gemini_session.send(
                input="The call has just been answered. Deliver your opening greeting. Be warm and natural.",
                end_of_turn=True,
            )

            async def receive_from_gemini():
                """Receive audio from Gemini Live → transcode → send to Telnyx."""
                try:
                    async for response in gemini_session.receive():
                        server_content = response.server_content
                        if server_content and server_content.model_turn:
                            for part in server_content.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    pcm_24k = part.inline_data.data
                                    # Downsample 24kHz → 8kHz
                                    pcm_8k = resample_pcm(pcm_24k, 24000, 8000)
                                    # Convert PCM → mu-law
                                    mulaw = pcm_to_mulaw(pcm_8k)
                                    # Send to Telnyx
                                    payload = base64.b64encode(mulaw).decode()
                                    await websocket.send_json({
                                        "event": "media",
                                        "media": {"payload": payload}
                                    })
                except Exception as exc:
                    log.warning("gemini_receive_error call_id=%s error=%s", call_id, str(exc))

            async def receive_from_telnyx():
                """Receive audio from Telnyx → transcode → send to Gemini Live."""
                try:
                    while True:
                        raw = await websocket.receive_text()
                        data = json.loads(raw)

                        if data.get("event") == "media":
                            payload = data["media"]["payload"]
                            mulaw = base64.b64decode(payload)
                            # Convert mu-law → PCM
                            pcm_8k = mulaw_to_pcm(mulaw)
                            # Upsample 8kHz → 24kHz
                            pcm_24k = resample_pcm(pcm_8k, 8000, 24000)
                            # Send to Gemini
                            await gemini_session.send(
                                input={"data": pcm_24k, "mime_type": "audio/pcm"}
                            )
                        elif data.get("event") == "start":
                            log.warning("ws_stream_start call_id=%s", call_id)
                        elif data.get("event") == "stop":
                            log.warning("ws_stream_stop call_id=%s", call_id)
                            break

                except WebSocketDisconnect:
                    log.warning("ws_disconnected call_id=%s", call_id)
                except Exception as exc:
                    log.warning("telnyx_receive_error call_id=%s error=%s", call_id, str(exc))

            await asyncio.gather(receive_from_gemini(), receive_from_telnyx())

    except Exception as exc:
        log.warning("gemini_live_error call_id=%s error=%s", call_id, str(exc))
        import traceback
        log.warning("traceback: %s", traceback.format_exc())
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        log.warning("ws_closed call_id=%s", call_id)