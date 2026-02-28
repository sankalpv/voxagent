#!/usr/bin/env python3
"""
Definitive test: Does Gemini Live API respond to audio input (not silence) 
in pure send_realtime_input mode (no send_client_content)?

This simulates what happens in a real phone call:
- Caller picks up and says "Hello?" (generates noise/speech-like audio)
- Gemini should detect voice activity and respond

We test with:
1. Pure silence → expect NO response (VAD won't trigger)
2. Speech-like audio → expect a response (VAD should trigger)
"""
import asyncio, math, struct, time, os, sys

def load_key():
    with open(os.path.join(os.path.dirname(__file__), '..', '.env')) as f:
        for line in f:
            if line.startswith('GEMINI_API_KEY='):
                return line.split('=',1)[1].strip()
    return ''

def make_speech_audio(duration: float, rate: int = 16000) -> bytes:
    """Generate speech-like audio at the given sample rate."""
    n = int(duration * rate)
    samples = []
    for i in range(n):
        t = i / rate
        # Simulate speech with fundamental + harmonics + amplitude modulation
        envelope = 0.5 + 0.5 * math.sin(2 * math.pi * 3 * t)  # ~3Hz modulation
        sample = int(envelope * (
            6000 * math.sin(2 * math.pi * 150 * t) +
            4000 * math.sin(2 * math.pi * 300 * t) +
            2000 * math.sin(2 * math.pi * 600 * t) +
            1000 * math.sin(2 * math.pi * 1200 * t)
        ))
        samples.append(max(-32768, min(32767, sample)))
    return struct.pack(f'<{n}h', *samples)

async def test_with_audio(label: str, audio_data: bytes, chunk_size: int = 640):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=load_key())
    config = types.LiveConnectConfig(
        response_modalities=['AUDIO'],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name='Kore')
            )
        ),
        system_instruction=types.Content(
            parts=[types.Part.from_text(
                text='You are a phone receptionist. Greet callers warmly. Keep responses very short.'
            )]
        ),
    )

    print(f'\n{"="*50}')
    print(f'TEST: {label}')
    print(f'{"="*50}')

    async with client.aio.live.connect(model='gemini-2.5-flash-native-audio-latest', config=config) as session:
        # Send audio in chunks
        chunks_sent = 0
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i+chunk_size]
            if len(chunk) < 2:
                continue
            await session.send_realtime_input(
                media=types.Blob(data=chunk, mime_type='audio/pcm;rate=16000')
            )
            chunks_sent += 1
            if chunks_sent % 25 == 0:
                await asyncio.sleep(0.01)  # pace the sending
        
        print(f'  Sent {chunks_sent} chunks ({len(audio_data)} bytes, {len(audio_data)/(16000*2):.1f}s)')
        print(f'  Waiting for response (10s timeout)...')

        audio_response = 0
        text_response = ""
        start = time.time()
        got_turn_complete = False

        async for r in session.receive():
            sc = r.server_content
            if sc and sc.model_turn:
                for p in sc.model_turn.parts:
                    if p.inline_data and p.inline_data.data:
                        audio_response += len(p.inline_data.data)
                        if audio_response < 5000:
                            print(f'  🔊 Audio chunk: {len(p.inline_data.data)} bytes')
                    if p.text:
                        text_response += p.text
            if sc and sc.turn_complete:
                got_turn_complete = True
                break
            if time.time() - start > 10:
                print(f'  ⏰ Timeout after 10s')
                break

        elapsed = time.time() - start
        print(f'  Response: {audio_response} bytes audio, "{text_response[:80]}" text')
        print(f'  Turn complete: {got_turn_complete}, Elapsed: {elapsed:.1f}s')

        if audio_response > 0:
            print(f'  ✅ Gemini responded to {label}!')
        else:
            print(f'  ❌ No response to {label}')

        return audio_response > 0

async def main():
    print('Gemini Live API — Pure Audio Mode Test')
    print('Testing if Gemini responds to audio via send_realtime_input only')
    print('(No send_client_content used)')

    # Test 1: Speech-like audio (should trigger VAD)
    speech = make_speech_audio(3.0, 16000)  # 3 seconds of speech-like audio
    result1 = await test_with_audio('Speech-like audio (3s)', speech)

    # Test 2: Silence (should NOT trigger VAD)  
    silence = bytes(16000 * 2 * 3)  # 3 seconds of silence
    result2 = await test_with_audio('Pure silence (3s)', silence)

    print(f'\n{"="*50}')
    print('SUMMARY')
    print(f'{"="*50}')
    print(f'  Speech audio → {"✅ Response" if result1 else "❌ No response"}')
    print(f'  Pure silence → {"✅ Response" if result2 else "❌ No response (expected)"}')
    
    if result1 and not result2:
        print(f'\n  ✅ PERFECT: Gemini responds to speech, ignores silence.')
        print(f'  This means real phone calls WILL work (caller says "hello")')
    elif result1:
        print(f'\n  ✅ Speech triggers response. Pure audio mode works!')
    else:
        print(f'\n  ❌ Gemini does not respond to speech in pure audio mode.')
        print(f'  Need to use send_client_content for greeting.')

asyncio.run(main())