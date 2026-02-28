#!/usr/bin/env python3
"""
Test: Can send_realtime_input work AFTER send_client_content?
This tests the hybrid approach: text greeting → audio conversation.
"""
import asyncio, time, os, sys

def load_key():
    with open(os.path.join(os.path.dirname(__file__), '..', '.env')) as f:
        for line in f:
            if line.startswith('GEMINI_API_KEY='):
                return line.split('=',1)[1].strip()
    return ''

async def test():
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
            parts=[types.Part.from_text(text='You are a phone assistant. Keep responses short.')]
        ),
    )

    async with client.aio.live.connect(model='gemini-2.5-flash-native-audio-latest', config=config) as session:
        # Step 1: send_client_content for greeting
        print('1. Sending greeting via send_client_content...')
        await session.send_client_content(
            turns=types.Content(role='user', parts=[types.Part.from_text(text='Say hello briefly.')]),
            turn_complete=True,
        )

        # Step 2: Receive greeting (wait for turn_complete)
        greeting_bytes = 0
        async for r in session.receive():
            sc = r.server_content
            if sc and sc.model_turn:
                for p in sc.model_turn.parts:
                    if p.inline_data and p.inline_data.data:
                        greeting_bytes += len(p.inline_data.data)
            if sc and sc.turn_complete:
                break
        print(f'2. Greeting received: {greeting_bytes} bytes ({greeting_bytes/(24000*2):.1f}s audio)')

        # Step 3: Send silence via send_realtime_input
        print('3. Sending 16kHz silence via send_realtime_input...')
        silence = bytes(3200)  # 100ms
        for i in range(30):  # 3 seconds
            await session.send_realtime_input(
                media=types.Blob(data=silence, mime_type='audio/pcm;rate=16000')
            )
            await asyncio.sleep(0.05)

        # Step 4: Wait for response
        print('4. Waiting for Gemini response to audio (8s timeout)...')
        audio_response = 0
        start = time.time()
        async for r in session.receive():
            sc = r.server_content
            if sc and sc.model_turn:
                for p in sc.model_turn.parts:
                    if p.inline_data and p.inline_data.data:
                        audio_response += len(p.inline_data.data)
                        print(f'   Audio chunk: {len(p.inline_data.data)} bytes')
            if sc and sc.turn_complete:
                print('   turn_complete')
                break
            if time.time() - start > 8:
                print('   TIMEOUT after 8s — no response')
                break

        print(f'\n5. RESULTS:')
        print(f'   Greeting: {greeting_bytes} bytes ✅' if greeting_bytes > 0 else f'   Greeting: FAILED ❌')
        if audio_response > 0:
            print(f'   Audio response: {audio_response} bytes ✅')
            print(f'   → send_realtime_input WORKS after send_client_content')
        else:
            print(f'   Audio response: 0 bytes')
            print(f'   → send_realtime_input may NOT work after send_client_content')
            print(f'   → Gemini silence: probably normal (silence input = no speech detected)')

asyncio.run(test())