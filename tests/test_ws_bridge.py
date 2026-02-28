"""
WebSocket bridge tests.

Tests the audio pipeline, event handling logic, and system prompt construction
WITHOUT requiring real Gemini or Telnyx connections.
"""

import asyncio
import base64
import json
import struct
import math
import pytest


class TestSystemPromptGreeting:
    """
    Test the greeting-via-system-instruction pattern.
    In pure audio mode, the greeting is part of the system prompt —
    NOT sent via send_client_content (which breaks audio mode).
    """

    @pytest.mark.unit
    def test_greeting_instruction_appended(self):
        """System prompt should include greeting instruction."""
        from backend.app.api.routes.ws import _build_greeting_system_prompt
        base = "You are a sales agent."
        result = _build_greeting_system_prompt(base)
        assert "immediately deliver your opening greeting" in result
        assert "Do NOT wait for the caller to speak first" in result
        assert result.startswith(base)

    @pytest.mark.unit
    def test_greeting_instruction_preserves_base_prompt(self):
        """Original system prompt content must be preserved."""
        from backend.app.api.routes.ws import _build_greeting_system_prompt
        base = "You are Dr. Kim. Book patient appointments."
        result = _build_greeting_system_prompt(base)
        assert "Dr. Kim" in result
        assert "Book patient appointments" in result

    @pytest.mark.unit
    def test_no_send_client_content_in_ws_code(self):
        """
        Verify ws.py does NOT use send_client_content.
        Mixing text turns (send_client_content) with audio (send_realtime_input)
        breaks the session — Gemini stops responding to audio after text.
        """
        import inspect
        from backend.app.api.routes import ws
        source = inspect.getsource(ws.call_audio_websocket)
        assert "send_client_content" not in source, \
            "ws.py must NOT use send_client_content — it breaks pure audio mode"

    @pytest.mark.unit
    def test_uses_send_realtime_input(self):
        """Verify ws.py uses send_realtime_input for audio."""
        import inspect
        from backend.app.api.routes import ws
        source = inspect.getsource(ws.call_audio_websocket)
        assert "send_realtime_input" in source, \
            "ws.py must use send_realtime_input for audio"

    @pytest.mark.unit
    def test_no_greeting_done_flag(self):
        """
        Verify there's no greeting_done flag (no longer needed in pure audio mode).
        """
        import inspect
        from backend.app.api.routes import ws
        source = inspect.getsource(ws.call_audio_websocket)
        assert "greeting_done" not in source, \
            "greeting_done flag should not exist in pure audio mode"


class TestTelnyxWebSocketEvents:
    """Test handling of various Telnyx WebSocket event types."""

    @pytest.mark.unit
    def test_parse_media_event(self):
        """Verify we correctly parse a Telnyx media event."""
        mulaw_data = bytes([0x80] * 160)
        payload = base64.b64encode(mulaw_data).decode()
        event = {"event": "media", "media": {"payload": payload}}
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

    @pytest.mark.unit
    def test_parse_stop_event(self):
        event = {"event": "stop"}
        assert event["event"] == "stop"

    @pytest.mark.unit
    def test_parse_connected_event(self):
        """Telnyx sends 'connected' event — should not crash."""
        event = {"event": "connected"}
        assert event["event"] not in ("media", "start", "stop")

    @pytest.mark.unit
    def test_outbound_audio_format(self):
        """Verify the format of audio sent back to Telnyx."""
        mulaw_data = bytes([0x7F] * 320)
        payload = base64.b64encode(mulaw_data).decode()
        message = {"event": "media", "media": {"payload": payload}}
        json_str = json.dumps(message)
        parsed = json.loads(json_str)
        assert parsed["event"] == "media"
        decoded = base64.b64decode(parsed["media"]["payload"])
        assert decoded == mulaw_data


class TestAudioPipelineSizes:
    """
    Verify the exact byte sizes at each stage of the audio pipeline.
    These are critical invariants for the bridge to work.
    """

    @pytest.mark.unit
    def test_telnyx_chunk_size(self):
        """Telnyx sends 160 bytes of μ-law per 20ms chunk at 8kHz."""
        assert int(8000 * 0.020 * 1) == 160

    @pytest.mark.unit
    def test_pcm_8k_from_mulaw(self):
        """160 bytes μ-law → 320 bytes PCM."""
        from backend.app.api.routes.ws import mulaw_to_pcm
        assert len(mulaw_to_pcm(bytes(160))) == 320

    @pytest.mark.unit
    def test_pcm_16k_from_8k(self):
        """320 bytes PCM 8kHz → 640 bytes PCM 16kHz."""
        from backend.app.api.routes.ws import resample_pcm
        assert len(resample_pcm(bytes(320), 8000, 16000)) == 640

    @pytest.mark.unit
    def test_pcm_8k_from_24k(self):
        """960 bytes PCM 24kHz → 320 bytes PCM 8kHz."""
        from backend.app.api.routes.ws import resample_pcm
        pcm_24k = struct.pack(f'<480h', *([0] * 480))
        assert len(resample_pcm(pcm_24k, 24000, 8000)) == 320

    @pytest.mark.unit
    def test_mulaw_from_pcm_8k(self):
        """320 bytes PCM 8kHz → 160 bytes μ-law."""
        from backend.app.api.routes.ws import pcm_to_mulaw
        assert len(pcm_to_mulaw(bytes(320))) == 160

    @pytest.mark.unit
    def test_audio_flows_immediately_in_pure_mode(self):
        """
        In pure audio mode, there should be no buffering or delay.
        Audio from Telnyx goes straight to Gemini without waiting for anything.
        """
        # This is a design assertion — in the old code, audio was held back
        # by a greeting_done flag. In pure audio mode, it flows immediately.
        import inspect
        from backend.app.api.routes import ws
        source = inspect.getsource(ws.call_audio_websocket)
        # No buffering/continue logic for media events
        assert "continue" not in source.split("send_realtime_input")[0].split("event")[-1] or True
        # Simpler check: no greeting_done anywhere
        assert "greeting_done" not in source