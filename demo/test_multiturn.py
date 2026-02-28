#!/usr/bin/env python3
"""
Local multi-turn test for Gemini Live API.
Simulates the exact production flow to debug the post-greeting silence issue.

Tests:
1. Connect → send greeting prompt → receive audio → turn_complete
2. After turn_complete, does the receive iterator survive?
3. Send a text follow-up → does Gemini respond with more audio?
4. Send simulated audio (sine wave PCM) at 16kHz → does Gemini detect speech?
5. Send simulated audio at 24kHz → does Gemini detect speech?

Usage:
    source .venv/bin/activate
    python demo/test_multiturn.py
"""

import asyncio
import math
import os
import struct
import sys
import time


def load_api_key():
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('GEMINI_API_KEY=') and not line.startswith('#'):
                    return line.split('=', 1)[1].strip()
    return os.environ.get('GEMINI_API_KEY', '')


def generate_sine_pcm(duration_secs: float, sample_rate: int, frequency: int = 440) -> bytes:
    """Generate a sine wave as PCM 16-bit LE audio."""
    num_samples = int(duration_secs * sample_rate)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        sample = int(16000 * math.sin(2 * math.pi * frequency * t))
        samples.append(max(-32768, min(32767, sample)))
    return struct.pack(f'<{len(samples)}h', *samples)


def generate_speech_like_pcm(duration_secs: float, sample_rate: int) -> bytes:
    """Generate speech-like audio (multiple frequencies) as PCM."""
    num_samples = int(duration_secs * sample_rate)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        # Mix of fundamental + harmonics to simulate speech
        sample = int(
            4000 * math.sin(2 * math.pi * 150 * t) +   # fundamental ~150Hz
            3000 * math.sin(2 * math.pi * 300 * t) +   # 1st harmonic
            2000 * math.sin(2 * math.pi * 600 * t) +   # 2nd harmonic
            1000 * math.sin(2 * math.pi * 1200 * t) +  # 3rd harmonic
            500 * math.sin(2 * math.pi * 2400 * t)     # 4th harmonic
        )
        samples.append(max(-32768, min(32767, sample)))
    return struct.pack(f'<{len(samples)}h', *samples)


async def test_multiturn():
    api_key = load_api_key()
    if not api_key:
        print("❌ No GEMINI_API_KEY found")
        sys.exit(1)

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    model = "gemini-2.5-flash-native-audio-latest"

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
            )
        ),
        system_instruction=types.Content(
            parts=[types.Part.from_text(
                text="You are a friendly AI assistant on a phone call. Keep responses very short."
            )]
        ),
    )

    print(f"📡 Connecting to {model}...")

    async with client.aio.live.connect(model=model, config=config) as session:
        print("✅ Connected!")
        print()

        # ─── TEST 1: Greeting (text → audio) ────────────────────
        print("=" * 60)
        print("TEST 1: Send text prompt, receive audio greeting")
        print("=" * 60)

        await session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part.from_text(
                    text="The call has just been answered. Deliver your opening greeting. Be warm and natural."
                )]
            ),
            turn_complete=True,
        )

        greeting_audio_bytes = 0
        greeting_text = ""
        greeting_turn_complete = False

        async for response in session.receive():
            sc = response.server_content
            if sc and sc.model_turn:
                for part in sc.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        greeting_audio_bytes += len(part.inline_data.data)
                    if part.text:
                        greeting_text += part.text
            if sc and sc.turn_complete:
                greeting_turn_complete = True
                break

        print(f"  Audio: {greeting_audio_bytes:,} bytes (~{greeting_audio_bytes/(24000*2):.1f}s)")
        print(f"  Text: {greeting_text[:100] if greeting_text else '(none)'}")
        print(f"  Turn complete: {greeting_turn_complete}")
        print()

        # ─── TEST 2: Text follow-up after turn_complete ──────────
        print("=" * 60)
        print("TEST 2: Send text follow-up AFTER turn_complete")
        print("=" * 60)
        print("  (Does the session survive past the first turn?)")

        await session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part.from_text(
                    text="Hi, yes I'm interested! Tell me more."
                )]
            ),
            turn_complete=True,
        )

        t2_audio_bytes = 0
        t2_text = ""
        t2_turn_complete = False
        t2_start = time.time()

        async for response in session.receive():
            sc = response.server_content
            if sc and sc.model_turn:
                for part in sc.model_turn.parts:
                    if part.inline_data and part.inline_data.data:
                        t2_audio_bytes += len(part.inline_data.data)
                    if part.text:
                        t2_text += part.text
            if sc and sc.turn_complete:
                t2_turn_complete = True
                break

        t2_elapsed = time.time() - t2_start
        print(f"  Audio: {t2_audio_bytes:,} bytes (~{t2_audio_bytes/(24000*2):.1f}s)")
        print(f"  Text: {t2_text[:100] if t2_text else '(none)'}")
        print(f"  Turn complete: {t2_turn_complete}")
        print(f"  Latency: {t2_elapsed:.1f}s")
        print()

        # ─── TEST 3: Send audio at 24kHz via send_realtime_input ─
        print("=" * 60)
        print("TEST 3: Send speech-like audio at 24kHz via send_realtime_input")
        print("=" * 60)

        # Generate 2 seconds of speech-like audio at 24kHz
        audio_24k = generate_speech_like_pcm(2.0, 24000)
        print(f"  Generated {len(audio_24k):,} bytes of 24kHz PCM audio")

        # Send in small chunks (like Telnyx would)
        chunk_size = 960  # 20ms at 24kHz (480 samples * 2 bytes)
        chunks_sent = 0
        for i in range(0, len(audio_24k), chunk_size):
            chunk = audio_24k[i:i+chunk_size]
            await session.send_realtime_input(
                media=types.Blob(data=chunk, mime_type="audio/pcm;rate=24000")
            )
            chunks_sent += 1
            if chunks_sent % 20 == 0:
                await asyncio.sleep(0.01)  # Small delay to avoid overwhelming

        print(f"  Sent {chunks_sent} chunks")
        print("  Waiting for response (10s timeout)...")

        t3_audio_bytes = 0
        t3_text = ""
        t3_turn_complete = False
        t3_start = time.time()

        try:
            async for response in session.receive():
                sc = response.server_content
                if sc and sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            t3_audio_bytes += len(part.inline_data.data)
                            if t3_audio_bytes <= 1000:
                                print(f"    🔊 Audio chunk received! ({len(part.inline_data.data)} bytes)")
                        if part.text:
                            t3_text += part.text
                if sc and sc.turn_complete:
                    t3_turn_complete = True
                    break
                if time.time() - t3_start > 10:
                    print("  ⏰ Timeout after 10s")
                    break
        except Exception as exc:
            print(f"  ❌ Error: {exc}")

        t3_elapsed = time.time() - t3_start
        print(f"  Audio response: {t3_audio_bytes:,} bytes")
        print(f"  Text: {t3_text[:100] if t3_text else '(none)'}")
        print(f"  Turn complete: {t3_turn_complete}")
        print(f"  Elapsed: {t3_elapsed:.1f}s")
        print()

        # ─── TEST 4: Send audio at 16kHz ─────────────────────────
        print("=" * 60)
        print("TEST 4: Send speech-like audio at 16kHz via send_realtime_input")
        print("=" * 60)

        audio_16k = generate_speech_like_pcm(2.0, 16000)
        print(f"  Generated {len(audio_16k):,} bytes of 16kHz PCM audio")

        chunk_size_16k = 640  # 20ms at 16kHz
        chunks_sent = 0
        for i in range(0, len(audio_16k), chunk_size_16k):
            chunk = audio_16k[i:i+chunk_size_16k]
            await session.send_realtime_input(
                media=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
            )
            chunks_sent += 1
            if chunks_sent % 20 == 0:
                await asyncio.sleep(0.01)

        print(f"  Sent {chunks_sent} chunks")
        print("  Waiting for response (10s timeout)...")

        t4_audio_bytes = 0
        t4_text = ""
        t4_turn_complete = False
        t4_start = time.time()

        try:
            async for response in session.receive():
                sc = response.server_content
                if sc and sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and part.inline_data.data:
                            t4_audio_bytes += len(part.inline_data.data)
                            if t4_audio_bytes <= 1000:
                                print(f"    🔊 Audio chunk received! ({len(part.inline_data.data)} bytes)")
                        if part.text:
                            t4_text += part.text
                if sc and sc.turn_complete:
                    t4_turn_complete = True
                    break
                if time.time() - t4_start > 10:
                    print("  ⏰ Timeout after 10s")
                    break
        except Exception as exc:
            print(f"  ❌ Error: {exc}")

        t4_elapsed = time.time() - t4_start
        print(f"  Audio response: {t4_audio_bytes:,} bytes")
        print(f"  Text: {t4_text[:100] if t4_text else '(none)'}")
        print(f"  Turn complete: {t4_turn_complete}")
        print(f"  Elapsed: {t4_elapsed:.1f}s")
        print()

        # ─── SUMMARY ─────────────────────────────────────────────
        print("=" * 60)
        print("📊 SUMMARY")
        print("=" * 60)
        print(f"  Test 1 (text greeting):     {'✅' if greeting_audio_bytes > 0 else '❌'} {greeting_audio_bytes:,} bytes")
        print(f"  Test 2 (text follow-up):     {'✅' if t2_audio_bytes > 0 else '❌'} {t2_audio_bytes:,} bytes")
        print(f"  Test 3 (24kHz audio input):  {'✅' if t3_audio_bytes > 0 else '❌'} {t3_audio_bytes:,} bytes")
        print(f"  Test 4 (16kHz audio input):  {'✅' if t4_audio_bytes > 0 else '❌'} {t4_audio_bytes:,} bytes")
        print()

        if t2_audio_bytes == 0:
            print("⚠️  Multi-turn text is broken — receive iterator may be dying")
        if t3_audio_bytes == 0 and t4_audio_bytes == 0:
            print("⚠️  Neither 24kHz nor 16kHz audio triggers a response")
            print("   This suggests Gemini isn't detecting the synthetic audio as speech")
            print("   In production, real phone audio should work better")
        elif t3_audio_bytes > 0 and t4_audio_bytes == 0:
            print("✅ 24kHz works, 16kHz doesn't — keep using 24kHz")
        elif t4_audio_bytes > 0 and t3_audio_bytes == 0:
            print("✅ 16kHz works, 24kHz doesn't — switch to 16kHz")
        elif t3_audio_bytes > 0 and t4_audio_bytes > 0:
            print("✅ Both sample rates work!")


if __name__ == "__main__":
    print("=" * 60)
    print("  Gemini Live API — Multi-Turn Diagnostic Test")
    print("=" * 60)
    print()
    asyncio.run(test_multiturn())