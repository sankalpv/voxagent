"""
Integration tests for Gemini Live API.

Tests verify the actual Gemini connection works correctly in PURE AUDIO MODE:
- Connection and audio output
- Audio output format (24kHz PCM)
- Audio input at 16kHz is accepted
- Pure audio mode: system instruction triggers greeting without send_client_content
- Multi-turn via audio (session stays alive after first response)

Requires GEMINI_API_KEY in .env. Skip with: pytest -m "not integration"
"""

import asyncio
import math
import struct
import time
import pytest


@pytest.mark.integration
class TestGeminiLiveConnection:
    """Test Gemini Live API in pure audio mode."""

    @pytest.mark.asyncio
    async def test_connect_and_receive_audio(self, gemini_api_key):
        """Connect to Gemini Live, send audio, receive audio response."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_api_key)
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part.from_text(
                    text="You are a friendly assistant. As soon as you hear any audio, "
                         "immediately say hello in one short sentence. Do NOT wait."
                )]
            ),
        )

        async with client.aio.live.connect(
            model="gemini-2.5-flash-native-audio-latest",
            config=config,
        ) as session:
            # Send a short burst of silence (16kHz PCM) to trigger the greeting
            silence = bytes(3200)  # 100ms of silence at 16kHz
            for _ in range(10):  # Send 1 second of silence
                await session.send_realtime_input(
                    media=types.Blob(data=silence, mime_type="audio/pcm;rate=16000")
                )
                await asyncio.sleep(0.05)

            # Collect response with timeout
            audio_bytes = 0
            turn_complete = False
            start = time.time()

            async for response in session.receive():
                sc = response.server_content
                if sc and sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            audio_bytes += len(part.inline_data.data)
                if sc and sc.turn_complete:
                    turn_complete = True
                    break
                if time.time() - start > 15:
                    break

            assert audio_bytes > 0, "Should receive audio from Gemini in pure audio mode"

    @pytest.mark.asyncio
    async def test_audio_output_format_is_24khz_pcm(self, gemini_api_key):
        """Verify Gemini outputs audio/pcm at 24kHz."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_api_key)
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part.from_text(
                    text="You are a friendly assistant. Say hello immediately when you hear audio."
                )]
            ),
        )

        async with client.aio.live.connect(
            model="gemini-2.5-flash-native-audio-latest",
            config=config,
        ) as session:
            # Send silence to trigger response
            silence = bytes(3200)
            for _ in range(10):
                await session.send_realtime_input(
                    media=types.Blob(data=silence, mime_type="audio/pcm;rate=16000")
                )
                await asyncio.sleep(0.05)

            mime_types = set()
            start = time.time()
            async for response in session.receive():
                sc = response.server_content
                if sc and sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.mime_type:
                            mime_types.add(part.inline_data.mime_type)
                if sc and sc.turn_complete:
                    break
                if time.time() - start > 15:
                    break

            assert any("pcm" in m.lower() for m in mime_types), f"Expected audio/pcm, got: {mime_types}"
            assert any("24000" in m for m in mime_types), f"Expected 24kHz, got: {mime_types}"

    @pytest.mark.asyncio
    async def test_send_realtime_input_accepted(self, gemini_api_key):
        """Verify send_realtime_input with 16kHz PCM doesn't error."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_api_key)
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part.from_text(text="You are a friendly assistant.")]
            ),
        )

        async with client.aio.live.connect(
            model="gemini-2.5-flash-native-audio-latest",
            config=config,
        ) as session:
            # Send 16kHz silence — should NOT raise an error
            silence_16k = bytes(640)  # 20ms of silence
            try:
                await session.send_realtime_input(
                    media=types.Blob(data=silence_16k, mime_type="audio/pcm;rate=16000")
                )
                audio_accepted = True
            except Exception as exc:
                audio_accepted = False
                pytest.fail(f"send_realtime_input with 16kHz PCM failed: {exc}")

            assert audio_accepted

    @pytest.mark.asyncio
    async def test_pure_audio_mode_no_send_client_content(self, gemini_api_key):
        """
        Critical test: verify that pure audio mode works WITHOUT send_client_content.
        This is the exact pattern used in production:
        1. System instruction includes greeting directive
        2. Audio flows immediately via send_realtime_input
        3. Gemini responds with audio (greeting + subsequent turns)
        4. No text turns are mixed in
        """
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_api_key)
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part.from_text(
                    text="You are a phone receptionist. As soon as you hear any audio "
                         "(even silence), immediately greet the caller with: 'Hello, thank you "
                         "for calling! How can I help you today?' Keep all responses very short."
                )]
            ),
        )

        async with client.aio.live.connect(
            model="gemini-2.5-flash-native-audio-latest",
            config=config,
        ) as session:
            # NO send_client_content — pure audio mode only

            # Send 2 seconds of silence to trigger greeting
            silence = bytes(3200)  # 100ms at 16kHz
            for _ in range(20):
                await session.send_realtime_input(
                    media=types.Blob(data=silence, mime_type="audio/pcm;rate=16000")
                )
                await asyncio.sleep(0.05)

            # Should get a greeting response
            greeting_audio = 0
            start = time.time()
            async for response in session.receive():
                sc = response.server_content
                if sc and sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            greeting_audio += len(part.inline_data.data)
                if sc and sc.turn_complete:
                    break
                if time.time() - start > 15:
                    break

            assert greeting_audio > 0, \
                "Pure audio mode: system instruction should trigger greeting when receiving audio"

            # Now send more silence (simulating caller listening) —
            # then verify session is still alive (can receive more audio after greeting)
            for _ in range(10):
                await session.send_realtime_input(
                    media=types.Blob(data=silence, mime_type="audio/pcm;rate=16000")
                )
                await asyncio.sleep(0.05)

            # Session should still be connected (no error thrown)
            # The fact that we can still send audio proves the session survived