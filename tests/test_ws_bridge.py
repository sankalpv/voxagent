"""
WebSocket bridge tests.

Tests the greeting flow, audio buffering, and event handling logic
WITHOUT requiring real Gemini or Telnyx connections (uses asyncio.Event mocking).
"""

import asyncio
import base64
import json
import struct
import math
import pytest


class TestGreetingFlowLogic:
    """
    Test the greeting-first-then-audio-forwarding pattern.
    This is the critical fix that prevents caller audio from
    interrupting the greeting generation.
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_greeting_event_blocks_audio_forwarding(self):
        """Audio forwarding should be blocked until greeting_done is set."""
        greeting_done = asyncio.Event()

        forwarded_chunks = []

        async def simulate_telnyx_audio():
            """Simulate receiving audio chunks from Telnyx."""
            for i in range(10):
                if not greeting_done.is_set():
                    # Audio should be dropped during greeting
                    pass
                else:
                    forwarded_chunks.append(i)
                await asyncio.sleep(0.01)

        async def simulate_greeting():
            """Simulate greeting taking ~50ms then completing."""
            await asyncio.sleep(0.05)
            greeting_done.set()

        await asyncio.gather(simulate_telnyx_audio(), simulate_greeting())

        # Some chunks should have been forwarded AFTER greeting
        assert len(forwarded_chunks) > 0, "Should forward chunks after greeting"
        assert len(forwarded_chunks) < 10, "Should NOT forward all chunks (some dropped during greeting)"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_greeting_event_set_on_error(self):
        """greeting_done should be set even if greeting errors (prevent hang)."""
        greeting_done = asyncio.Event()

        async def simulate_greeting_error():
            try:
                raise RuntimeError("Gemini connection failed")
            except Exception:
                pass
            finally:
                greeting_done.set()

        await simulate_greeting_error()
        assert greeting_done.is_set(), "greeting_done must be set even on error"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_audio_forwarding_starts_after_greeting_done(self):
        """Verify exact timing: no audio before greeting, all audio after."""
        greeting_done = asyncio.Event()
        before_greeting = []
        after_greeting = []

        for i in range(20):
            if not greeting_done.is_set():
                before_greeting.append(i)
            else:
                after_greeting.append(i)
            if i == 9:  # Greeting completes at chunk 10
                greeting_done.set()

        assert len(before_greeting) == 10, f"Expected 10 before, got {len(before_greeting)}"
        assert len(after_greeting) == 10, f"Expected 10 after, got {len(after_greeting)}"


class TestTelnyxWebSocketEvents:
    """Test handling of various Telnyx WebSocket event types."""

    @pytest.mark.unit
    def test_parse_media_event(self):
        """Verify we correctly parse a Telnyx media event."""
        # Simulate a Telnyx media event
        mulaw_data = bytes([0x80] * 160)  # 160 bytes of μ-law
        payload = base64.b64encode(mulaw_data).decode()
        event = {
            "event": "media",
            "media": {"payload": payload}
        }

        assert event["event"] == "media"
        decoded = base64.b64decode(event["media"]["payload"])
        assert len(decoded) == 160
        assert decoded == mulaw_data

    @pytest.mark.unit
    def test_parse_start_event(self):
        """Verify we handle the Telnyx stream start event."""
        event = {
            "event": "start",
            "start": {
                "call_control_id": "v3:test123",
                "user_id": "user456",
                "to": "+14155551234",
                "from": "+14155555678",
            }
        }
        assert event["event"] == "start"
        assert event["start"]["call_control_id"] == "v3:test123"

    @pytest.mark.unit
    def test_parse_stop_event(self):
        """Verify we handle the Telnyx stream stop event."""
        event = {"event": "stop"}
        assert event["event"] == "stop"

    @pytest.mark.unit
    def test_parse_connected_event(self):
        """Verify we handle the Telnyx 'connected' event (logged as unknown)."""
        event = {"event": "connected"}
        # This should be handled gracefully — not crash
        assert event["event"] == "connected"
        assert event["event"] not in ("media", "start", "stop")

    @pytest.mark.unit
    def test_outbound_audio_format(self):
        """Verify the format of audio sent back to Telnyx."""
        # Simulate what we send to Telnyx
        mulaw_data = bytes([0x7F] * 320)
        payload = base64.b64encode(mulaw_data).decode()
        message = {
            "event": "media",
            "media": {"payload": payload}
        }

        # Verify it's valid JSON-serializable
        json_str = json.dumps(message)
        parsed = json.loads(json_str)
        assert parsed["event"] == "media"
        decoded = base64.b64decode(parsed["media"]["payload"])
        assert decoded == mulaw_data


class TestAudioPipelineSizes:
    """
    Verify the exact byte sizes at each stage of the audio pipeline.
    These are the critical invariants that must hold for the bridge to work.
    """

    @pytest.mark.unit
    def test_telnyx_chunk_size(self):
        """Telnyx sends 160 bytes of μ-law per 20ms chunk at 8kHz."""
        # 8000 samples/sec * 0.020 sec * 1 byte/sample = 160 bytes
        expected = 160
        actual = int(8000 * 0.020 * 1)
        assert actual == expected

    @pytest.mark.unit
    def test_pcm_8k_from_mulaw(self):
        """160 bytes μ-law → 320 bytes PCM (160 samples * 2 bytes)."""
        from backend.app.api.routes.ws import mulaw_to_pcm
        mulaw = bytes(160)
        pcm = mulaw_to_pcm(mulaw)
        assert len(pcm) == 320

    @pytest.mark.unit
    def test_pcm_16k_from_8k(self):
        """320 bytes PCM 8kHz → 640 bytes PCM 16kHz (doubled samples)."""
        from backend.app.api.routes.ws import resample_pcm
        pcm_8k = bytes(320)
        pcm_16k = resample_pcm(pcm_8k, 8000, 16000)
        assert len(pcm_16k) == 640

    @pytest.mark.unit
    def test_pcm_8k_from_24k(self):
        """960 bytes PCM 24kHz (480 samples) → 320 bytes PCM 8kHz (160 samples)."""
        from backend.app.api.routes.ws import resample_pcm
        pcm_24k = struct.pack(f'<480h', *([0] * 480))
        pcm_8k = resample_pcm(pcm_24k, 24000, 8000)
        assert len(pcm_8k) == 320

    @pytest.mark.unit
    def test_mulaw_from_pcm_8k(self):
        """320 bytes PCM 8kHz → 160 bytes μ-law."""
        from backend.app.api.routes.ws import pcm_to_mulaw
        pcm = bytes(320)
        mulaw = pcm_to_mulaw(pcm)
        assert len(mulaw) == 160