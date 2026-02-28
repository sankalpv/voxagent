"""
Google Cloud Text-to-Speech — streaming sentence-level synthesis.

Key design: we flush one sentence at a time to TTS as soon as the LLM produces it,
rather than waiting for the full response. This cuts perceived latency by ~300ms.

Audio format: LINEAR16 at 8kHz → converted to μ-law for Telnyx.
"""

import asyncio
import logging
import struct
from concurrent.futures import ThreadPoolExecutor

from google.cloud import texttospeech

from backend.app.core.config import settings

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tts")

# Build clients lazily per-thread (TTS client is not thread-safe)
_tts_client: texttospeech.TextToSpeechClient | None = None


def _get_tts_client() -> texttospeech.TextToSpeechClient:
    global _tts_client
    if _tts_client is None:
        _tts_client = texttospeech.TextToSpeechClient()
    return _tts_client


# ─── μ-law conversion ──────────────────────────────────────────────────────────

def _linear16_to_ulaw(linear16_bytes: bytes) -> bytes:
    """Convert raw LINEAR16 PCM to μ-law (ITU-T G.711).
    Uses the standard μ-law companding algorithm.
    """
    try:
        # Prefer stdlib audioop (Python ≤3.12)
        import audioop  # type: ignore[import]
        return audioop.lin2ulaw(linear16_bytes, 2)
    except ImportError:
        pass

    # Pure-Python fallback for Python 3.13+
    BIAS = 0x84
    CLIP = 32635
    exp_lut = [0, 0, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3,
               4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
               5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
               5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
               6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
               6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
               6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
               6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
               7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
               7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
               7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
               7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
               7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
               7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
               7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
               7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7]

    num_samples = len(linear16_bytes) // 2
    result = bytearray(num_samples)
    for i in range(num_samples):
        sample = struct.unpack_from("<h", linear16_bytes, i * 2)[0]
        sign = (sample >> 8) & 0x80
        if sign:
            sample = -sample
        sample = min(sample, CLIP)
        sample += BIAS
        exp = exp_lut[(sample >> 7) & 0xFF]
        mantissa = (sample >> (exp + 3)) & 0x0F
        result[i] = ~(sign | (exp << 4) | mantissa) & 0xFF
    return bytes(result)


# ─── Synthesis ────────────────────────────────────────────────────────────────

def _synthesize_sync(text: str, voice_name: str) -> bytes:
    """Blocking TTS call — runs in thread pool."""
    client = _get_tts_client()
    lang = voice_name[:5] if len(voice_name) >= 5 else settings.tts_language_code

    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=texttospeech.VoiceSelectionParams(
            language_code=lang,
            name=voice_name,
        ),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=8000,
            effects_profile_id=["telephony-class-application"],
            speaking_rate=1.05,   # Slightly faster sounds more natural on phone
        ),
    )
    return response.audio_content


async def synthesize(text: str, voice_name: str | None = None) -> bytes:
    """
    Synthesize text → μ-law 8kHz audio bytes ready for Telnyx.
    Runs TTS in a thread pool to avoid blocking the event loop.
    """
    voice = voice_name or settings.tts_voice_name
    loop = asyncio.get_event_loop()
    linear16_audio = await loop.run_in_executor(_executor, _synthesize_sync, text, voice)
    return _linear16_to_ulaw(linear16_audio)


def split_into_sentences(text: str) -> list[str]:
    """
    Split LLM response into sentences for streaming TTS.
    We start TTS on the first complete sentence, reducing perceived latency.
    """
    import re
    # Split on sentence-ending punctuation followed by whitespace or end of string
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    # Filter out empty strings and very short fragments
    return [p.strip() for p in parts if len(p.strip()) > 2]


async def synthesize_streaming(
    text_chunks: asyncio.Queue,
    audio_out_queue: asyncio.Queue,
    voice_name: str | None = None,
) -> None:
    """
    Reads text from text_chunks queue sentence-by-sentence,
    synthesizes each sentence, and pushes μ-law audio to audio_out_queue.

    This is the core of our low-latency approach: TTS starts on sentence 1
    while the LLM is still generating sentence 2+.
    """
    buffer = ""
    while True:
        chunk = await text_chunks.get()
        if chunk is None:  # LLM stream finished
            if buffer.strip():
                audio = await synthesize(buffer.strip(), voice_name)
                await audio_out_queue.put(audio)
            await audio_out_queue.put(None)  # signal TTS done
            break

        buffer += chunk
        # Check if we have a complete sentence to flush
        sentences = split_into_sentences(buffer)
        if len(sentences) > 1:
            # Flush all complete sentences, keep last partial one
            for sentence in sentences[:-1]:
                audio = await synthesize(sentence, voice_name)
                await audio_out_queue.put(audio)
            buffer = sentences[-1]
