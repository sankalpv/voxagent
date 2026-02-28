#!/usr/bin/env python3
"""
Quick test: Verify Gemini Live API (bidiGenerateContent) works with your API key.

Usage:
    pip install google-genai
    python demo/test_gemini_live.py

Tests:
1. Connects to gemini-2.5-flash-native-audio-latest via Live API
2. Sends a text prompt
3. Receives audio response
4. Reports success/failure
"""

import asyncio
import os
import sys
import struct

# Load API key from .env file
def load_api_key():
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('GEMINI_API_KEY=') and not line.startswith('#'):
                    return line.split('=', 1)[1].strip()
    # Fallback to environment variable
    return os.environ.get('GEMINI_API_KEY', '')


async def test_gemini_live():
    api_key = load_api_key()
    if not api_key:
        print("❌ No GEMINI_API_KEY found in .env or environment")
        sys.exit(1)

    print(f"🔑 API key: {api_key[:10]}...{api_key[-4:]}")
    print()

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("❌ google-genai not installed. Run: pip install google-genai")
        sys.exit(1)

    model = "gemini-2.5-flash-native-audio-latest"
    print(f"🤖 Model: {model}")
    print(f"📡 Connecting to Gemini Live API (bidiGenerateContent)...")
    print()

    client = genai.Client(api_key=api_key)

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
            )
        ),
        system_instruction=types.Content(
            parts=[types.Part.from_text(
                text="You are a friendly AI assistant. Keep responses very short — one sentence max."
            )]
        ),
    )

    total_audio_bytes = 0
    text_response = ""
    turn_complete = False

    try:
        async with client.aio.live.connect(model=model, config=config) as session:
            print("✅ Connected to Gemini Live API!")
            print()

            # Send a text prompt
            prompt = "Hello! Just say hi back in one short sentence."
            print(f"📤 Sending prompt: \"{prompt}\"")
            await session.send(input=prompt, end_of_turn=True)

            # Receive response
            print("📥 Receiving response...")
            async for response in session.receive():
                server_content = response.server_content

                if server_content:
                    if server_content.model_turn:
                        for part in server_content.model_turn.parts:
                            if part.inline_data and part.inline_data.data:
                                chunk_size = len(part.inline_data.data)
                                total_audio_bytes += chunk_size
                                mime = part.inline_data.mime_type or "unknown"
                                # Print progress dots
                                print(f"  🔊 Audio chunk: {chunk_size} bytes ({mime})")
                            if part.text:
                                text_response += part.text
                                print(f"  💬 Text: {part.text}")

                    if server_content.turn_complete:
                        turn_complete = True
                        break

            print()
            print("=" * 60)
            print("📊 RESULTS")
            print("=" * 60)
            print(f"  ✅ Connection:    SUCCESS")
            print(f"  ✅ Turn complete: {turn_complete}")
            print(f"  🔊 Audio received: {total_audio_bytes:,} bytes")
            if total_audio_bytes > 0:
                # Audio is PCM 24kHz 16-bit mono
                duration_secs = total_audio_bytes / (24000 * 2)
                print(f"  ⏱️  Audio duration: ~{duration_secs:.1f}s (24kHz PCM)")
            if text_response:
                print(f"  💬 Text response: {text_response}")
            print()

            if total_audio_bytes > 0:
                print("🎉 SUCCESS! Gemini Live API is working correctly.")
                print("   The model accepts bidiGenerateContent and returns audio.")
            else:
                print("⚠️  Connected but received no audio. The model may not have generated speech.")

    except Exception as exc:
        print()
        print(f"❌ ERROR: {exc}")
        print()
        import traceback
        traceback.print_exc()
        print()
        print("Common issues:")
        print("  - Model not available for your API key")
        print("  - Invalid API key")
        print("  - Network connectivity issue")
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 60)
    print("  Gemini Live API Test — bidiGenerateContent")
    print("=" * 60)
    print()
    asyncio.run(test_gemini_live())