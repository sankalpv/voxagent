"""
Integration tests for Gemini Live API.

These tests verify the actual Gemini connection works correctly:
- Multi-turn text conversation (session survives past turn_complete)
- Audio output format (24kHz PCM)
- Greeting generation produces audio
- Audio input at 16kHz is accepted

Requires GEMINI_API_KEY in .env. Skip with: pytest -m "not integration"
"""

import asyncio
import math
import struct
import time
import pytest


@pytest.mark.integration
class TestGeminiLiveConnection:
    """Test basic Gemini Live API connectivity."""

    @pytest.mark.asyncio
    async def test_connect_and_receive_greeting(self, gemini_api_key):
        """Connect to Gemini Live, send greeting prompt, receive audio."""
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
                parts=[types.Part.from_text(text="You are a friendly assistant. Keep responses very short.")]
            ),
        )

        async with client.aio.live.connect(
            model="gemini-2.5-flash-native-audio-latest",
            config=config,
        ) as session:
            # Send greeting prompt
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="Say hello in one sentence.")]
                ),
                turn_complete=True,
            )

            # Collect response
            audio_bytes = 0
            turn_complete = False

            async for response in session.receive():
                sc = response.server_content
                if sc and sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            audio_bytes += len(part.inline_data.data)
                if sc and sc.turn_complete:
                    turn_complete = True
                    break

            assert audio_bytes > 0, "Greeting should produce audio"
            assert turn_complete, "Should receive turn_complete"

    @pytest.mark.asyncio
    async def test_multiturn_text_survives_turn_complete(self, gemini_api_key):
        """Verify session survives past first turn_complete (critical regression test)."""
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
                parts=[types.Part.from_text(text="You are a friendly assistant. Keep responses very short.")]
            ),
        )

        async with client.aio.live.connect(
            model="gemini-2.5-flash-native-audio-latest",
            config=config,
        ) as session:
            # Turn 1: greeting
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part.from_text(text="Say hello.")]),
                turn_complete=True,
            )
            t1_audio = 0
            t1_responses = 0
            async for response in session.receive():
                t1_responses += 1
                sc = response.server_content
                if sc and sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            t1_audio += len(part.inline_data.data)
                if sc and sc.turn_complete:
                    break

            assert t1_audio > 0, f"Turn 1 should produce audio (got {t1_responses} responses)"

            # Small delay to let the session settle between turns
            await asyncio.sleep(0.5)

            # Turn 2: follow-up (MUST still work after turn_complete)
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part.from_text(text="What is 2 plus 2?")]),
                turn_complete=True,
            )
            t2_audio = 0
            t2_text = ""
            t2_responses = 0
            async for response in session.receive():
                t2_responses += 1
                sc = response.server_content
                if sc and sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            t2_audio += len(part.inline_data.data)
                        if part.text:
                            t2_text += part.text
                if sc and sc.turn_complete:
                    break

            # Turn 2 must produce audio OR text (session must survive)
            assert t2_audio > 0 or len(t2_text) > 0, \
                f"Turn 2 should produce audio or text (got {t2_responses} responses, audio={t2_audio}, text='{t2_text}')"

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
                parts=[types.Part.from_text(text="You are a friendly assistant.")]
            ),
        )

        async with client.aio.live.connect(
            model="gemini-2.5-flash-native-audio-latest",
            config=config,
        ) as session:
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part.from_text(text="Say yes.")]),
                turn_complete=True,
            )

            mime_types = set()
            async for response in session.receive():
                sc = response.server_content
                if sc and sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data:
                            if part.inline_data.mime_type:
                                mime_types.add(part.inline_data.mime_type)
                if sc and sc.turn_complete:
                    break

            # Gemini outputs PCM at 24kHz
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
            # First do the greeting to establish the session
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part.from_text(text="Hello.")]),
                turn_complete=True,
            )
            async for response in session.receive():
                sc = response.server_content
                if sc and sc.turn_complete:
                    break

            # Now send audio at 16kHz — should NOT raise an error
            silence_16k = bytes(640)  # 20ms of silence at 16kHz (320 samples * 2 bytes)
            try:
                await session.send_realtime_input(
                    media=types.Blob(data=silence_16k, mime_type="audio/pcm;rate=16000")
                )
                audio_accepted = True
            except Exception as exc:
                audio_accepted = False
                pytest.fail(f"send_realtime_input with 16kHz PCM failed: {exc}")

            assert audio_accepted, "16kHz PCM audio input should be accepted"