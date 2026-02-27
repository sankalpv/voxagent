"""
Google Cloud Speech-to-Text streaming transcription.
Uses the telephony-optimised model for 8kHz μ-law audio from Telnyx.

Audio flow:
  Telnyx WebSocket → base64 μ-law chunks → this module → transcript strings
"""

import asyncio
import logging
from collections.abc import AsyncIterator

from google.cloud.speech_v2 import SpeechAsyncClient
from google.cloud.speech_v2.types import cloud_speech

from backend.app.core.config import settings

log = logging.getLogger(__name__)

# Recognition config is built once per language and reused
_RECOGNITION_CONFIG = cloud_speech.RecognitionConfig(
    explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
        encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.MULAW,
        sample_rate_hertz=8000,
        audio_channel_count=1,
    ),
    language_codes=[settings.stt_language_code],
    model=settings.stt_model,
    features=cloud_speech.RecognitionFeatures(
        enable_automatic_punctuation=True,
        enable_voice_activity_events=True,
    ),
)

_STREAMING_CONFIG = cloud_speech.StreamingRecognitionConfig(
    config=_RECOGNITION_CONFIG,
    streaming_features=cloud_speech.StreamingRecognitionFeatures(
        enable_voice_activity_events=True,
        interim_results=True,
    ),
)


async def _audio_request_generator(
    audio_queue: asyncio.Queue,
    project: str,
) -> AsyncIterator[cloud_speech.StreamingRecognizeRequest]:
    recognizer = f"projects/{project}/locations/global/recognizers/_"
    # First request: config only
    yield cloud_speech.StreamingRecognizeRequest(
        recognizer=recognizer,
        streaming_config=_STREAMING_CONFIG,
    )
    # Subsequent requests: audio only
    while True:
        chunk = await audio_queue.get()
        if chunk is None:
            break
        yield cloud_speech.StreamingRecognizeRequest(audio=chunk)


class StreamingSTT:
    """
    Wraps a single Google STT streaming session for one phone call.

    Usage:
        async with StreamingSTT() as stt:
            stt.feed_audio(mulaw_bytes)        # call from audio handler
            async for transcript in stt.transcripts():
                handle(transcript)
    """

    def __init__(self) -> None:
        self._audio_queue: asyncio.Queue = asyncio.Queue()
        self._transcript_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None

    async def __aenter__(self) -> "StreamingSTT":
        self._running = True
        self._task = asyncio.create_task(self._run())
        return self

    async def __aexit__(self, *_) -> None:
        await self.stop()

    def feed_audio(self, mulaw_bytes: bytes) -> None:
        """Push a chunk of μ-law audio into the STT pipeline (non-blocking)."""
        if self._running:
            self._audio_queue.put_nowait(mulaw_bytes)

    async def stop(self) -> None:
        self._running = False
        await self._audio_queue.put(None)  # signal generator to stop
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()

    async def _run(self) -> None:
        project = settings.google_cloud_project
        if not project:
            log.error("GOOGLE_CLOUD_PROJECT not set — STT disabled")
            return
        try:
            client = SpeechAsyncClient()
            generator = _audio_request_generator(self._audio_queue, project)
            async for response in await client.streaming_recognize(requests=generator):
                for result in response.results:
                    if result.is_final:
                        transcript = result.alternatives[0].transcript.strip()
                        if transcript:
                            await self._transcript_queue.put(transcript)
                    # Voice activity: speech ended without a full utterance (silence)
                    if result.HasField("voice_activity_event"):
                        event = result.voice_activity_event
                        if event == cloud_speech.VoiceActivityEvent.SPEECH_ACTIVITY_END:
                            # Flush partial transcript if any
                            pass
        except Exception as exc:
            log.exception("STT stream error: %s", exc)
        finally:
            await self._transcript_queue.put(None)  # signal consumers we're done

    async def transcripts(self) -> AsyncIterator[str]:
        """Async iterator yielding final transcript strings."""
        while True:
            item = await self._transcript_queue.get()
            if item is None:
                break
            yield item
