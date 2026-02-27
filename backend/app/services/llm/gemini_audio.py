"""
Gemini Native Audio — generates speech directly from the model.
Uses gemini-2.5-flash-native-audio-latest for Gemini Live Chat quality.
"""

import asyncio
import base64
import logging
import struct
from typing import Optional

from backend.app.core.config import settings

log = logging.getLogger(__name__)


async def generate_audio_response(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
) -> tuple[str, bytes | None]:
    """
    Generate a text response AND audio using Gemini Native Audio.
    Returns (text_response, audio_bytes_or_None).
    Audio is PCM 24kHz mono that needs conversion to 8kHz mulaw for Telnyx.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _generate_sync, system_prompt, conversation_history, user_message)


def _generate_sync(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
) -> tuple[str, bytes | None]:
    """Blocking call to Gemini native audio model."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)

        # Build contents
        contents = []
        for turn in conversation_history:
            role = "user" if turn["role"] == "user" else "model"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=turn["content"])]
            ))
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)]
        ))

        response = client.models.generate_content(
            model="gemini-2.5-flash-native-audio-latest",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                    )
                ),
            ),
        )

        # Extract audio and text
        audio_bytes = None
        text = ""

        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    audio_bytes = part.inline_data.data
                    log.warning("native_audio: got %d bytes of audio", len(audio_bytes))
                if part.text:
                    text = part.text

        # If we got audio but no text, generate a text-only response for logging
        if audio_bytes and not text:
            text = "[audio response]"

        return text, audio_bytes

    except Exception as exc:
        log.warning("native_audio_error: %s", str(exc))
        import traceback
        log.warning("native_audio_traceback: %s", traceback.format_exc())
        return "", None


def pcm_to_mulaw_8k(pcm_24k_bytes: bytes) -> bytes:
    """Convert PCM 24kHz to 8kHz μ-law for Telnyx."""
    # Downsample from 24kHz to 8kHz (take every 3rd sample)
    num_samples = len(pcm_24k_bytes) // 2
    samples = struct.unpack(f"<{num_samples}h", pcm_24k_bytes)
    downsampled = samples[::3]  # 24000/3 = 8000 Hz

    # Convert to μ-law
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

    result = bytearray(len(downsampled))
    for i, sample in enumerate(downsampled):
        sign = (sample >> 8) & 0x80
        if sign:
            sample = -sample
        sample = min(sample, CLIP)
        sample += BIAS
        exp = exp_lut[(sample >> 7) & 0xFF]
        mantissa = (sample >> (exp + 3)) & 0x0F
        result[i] = ~(sign | (exp << 4) | mantissa) & 0xFF
    return bytes(result)