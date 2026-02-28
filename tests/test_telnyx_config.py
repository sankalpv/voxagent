"""
Telnyx configuration tests.

Verifies the streaming parameters are correct — these are the exact
settings that caused the echo loop and audio issues in production.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestStreamingConfig:
    """Verify Telnyx streaming_start parameters are correct."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_track_is_inbound_only(self):
        """
        stream_track MUST be 'inbound_track' — NOT 'both_tracks'.
        'both_tracks' causes an echo loop: agent's audio is fed back to Gemini.
        """
        from backend.app.services.telephony import telnyx_handler

        captured_payload = {}

        async def mock_call_command(control_id, command, payload):
            if command == "streaming_start":
                captured_payload.update(payload)
            return True

        with patch.object(telnyx_handler, '_call_command', side_effect=mock_call_command):
            await telnyx_handler.start_streaming("test_control_id", "test_call_id")

        assert captured_payload.get("stream_track") == "inbound_track", \
            "stream_track MUST be 'inbound_track' to avoid echo loop"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_bidirectional_mode_is_rtp(self):
        """
        stream_bidirectional_mode MUST be 'rtp' to enable sending audio back.
        Without this, Telnyx ignores all audio we send on the WebSocket.
        """
        from backend.app.services.telephony import telnyx_handler

        captured_payload = {}

        async def mock_call_command(control_id, command, payload):
            if command == "streaming_start":
                captured_payload.update(payload)
            return True

        with patch.object(telnyx_handler, '_call_command', side_effect=mock_call_command):
            await telnyx_handler.start_streaming("test_control_id", "test_call_id")

        assert captured_payload.get("stream_bidirectional_mode") == "rtp", \
            "stream_bidirectional_mode MUST be 'rtp' for audio to reach the caller"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_url_is_websocket(self):
        """Stream URL must be a WebSocket URL (wss:// or ws://)."""
        from backend.app.services.telephony import telnyx_handler

        captured_payload = {}

        async def mock_call_command(control_id, command, payload):
            if command == "streaming_start":
                captured_payload.update(payload)
            return True

        with patch.object(telnyx_handler, '_call_command', side_effect=mock_call_command):
            await telnyx_handler.start_streaming("test_control_id", "test_call_id")

        stream_url = captured_payload.get("stream_url", "")
        assert stream_url.startswith("ws://") or stream_url.startswith("wss://"), \
            f"Stream URL must be ws:// or wss://, got: {stream_url}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_stream_url_contains_call_id(self):
        """Stream URL must contain the call_id for routing."""
        from backend.app.services.telephony import telnyx_handler

        captured_payload = {}

        async def mock_call_command(control_id, command, payload):
            if command == "streaming_start":
                captured_payload.update(payload)
            return True

        with patch.object(telnyx_handler, '_call_command', side_effect=mock_call_command):
            await telnyx_handler.start_streaming("test_control_id", "my-test-call-id-123")

        stream_url = captured_payload.get("stream_url", "")
        assert "my-test-call-id-123" in stream_url, \
            f"Stream URL must contain call_id, got: {stream_url}"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_dialogflow_is_disabled(self):
        """Dialogflow integration must be disabled (we use our own AI)."""
        from backend.app.services.telephony import telnyx_handler

        captured_payload = {}

        async def mock_call_command(control_id, command, payload):
            if command == "streaming_start":
                captured_payload.update(payload)
            return True

        with patch.object(telnyx_handler, '_call_command', side_effect=mock_call_command):
            await telnyx_handler.start_streaming("test_control_id", "test_call_id")

        assert captured_payload.get("enable_dialogflow") is False, \
            "Dialogflow must be disabled"


class TestStreamingConfigCombination:
    """
    Verify the EXACT combination of streaming parameters.
    This is the configuration that works in production.
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_complete_streaming_config(self):
        """
        The complete streaming_start config must match exactly.
        Any deviation from these values has caused production issues:
        - both_tracks → echo loop (agent hears itself)
        - missing bidirectional_mode → caller hears nothing
        - wrong stream_url → WebSocket connection fails
        """
        from backend.app.services.telephony import telnyx_handler

        captured_payload = {}

        async def mock_call_command(control_id, command, payload):
            if command == "streaming_start":
                captured_payload.update(payload)
            return True

        with patch.object(telnyx_handler, '_call_command', side_effect=mock_call_command):
            await telnyx_handler.start_streaming("ctrl_123", "call_456")

        # Verify all required keys exist
        required_keys = {"stream_url", "stream_track", "stream_bidirectional_mode", "enable_dialogflow"}
        assert required_keys.issubset(captured_payload.keys()), \
            f"Missing keys: {required_keys - captured_payload.keys()}"

        # Verify exact values
        assert captured_payload["stream_track"] == "inbound_track"
        assert captured_payload["stream_bidirectional_mode"] == "rtp"
        assert captured_payload["enable_dialogflow"] is False
        assert "call_456" in captured_payload["stream_url"]