"""Live voice round trip. Run inside the local-voice server container."""

import asyncio
import json
from urllib.request import Request, urlopen

import opuslib_next
import websockets


def speech_input():
    request = Request('http://piper:5000/synthesize',
                      data=json.dumps({'text': 'What is two plus two? Please answer in one short sentence.'}).encode(),
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=60) as response:
        assert response.headers['X-Audio-Format'] == 'pcm-s16le-16000-mono'
        return response.read()


async def main():
    pcm = await asyncio.to_thread(speech_input)
    encoder = opuslib_next.Encoder(16000, 1, opuslib_next.APPLICATION_AUDIO)
    decoder = opuslib_next.Decoder(16000, 1)
    transcript = None
    sentences = []
    audio_packets = 0
    audio_samples = 0
    async with websockets.connect('ws://127.0.0.1:8000/xiaozhi/v1/',
                                  additional_headers={'Device-Id': '02:00:00:00:99:01',
                                                      'Client-Id': 'local-voice-smoke'},
                                  open_timeout=15) as socket:
        await socket.send(json.dumps({'type': 'hello', 'version': 1, 'transport': 'websocket',
                                      'features': {'emoji': False},
                                      'audio_params': {'format': 'opus', 'sample_rate': 16000,
                                                       'channels': 1, 'frame_duration': 60}}))
        hello = json.loads(await asyncio.wait_for(socket.recv(), 15))
        assert hello['type'] == 'hello', hello
        print('HELLO_OK', flush=True)
        await asyncio.sleep(3)
        await socket.send(json.dumps({'type': 'listen', 'state': 'start', 'mode': 'manual'}))
        for start in range(0, len(pcm), 1920):
            frame = pcm[start:start + 1920].ljust(1920, b'\x00')
            await socket.send(encoder.encode(frame, 960))
            await asyncio.sleep(0.06)
        await asyncio.sleep(0.5)
        await socket.send(json.dumps({'type': 'listen', 'state': 'stop'}))
        async def collect():
            nonlocal transcript, audio_packets, audio_samples
            while True:
                message = await socket.recv()
                if isinstance(message, bytes):
                    decoded = decoder.decode(message, 960)
                    audio_packets += 1
                    audio_samples += len(decoded) // 2
                    continue
                event = json.loads(message)
                print('EVENT', json.dumps(event, ensure_ascii=False), flush=True)
                if event.get('type') == 'stt':
                    transcript = event.get('text')
                if event.get('type') == 'tts' and event.get('state') == 'sentence_start':
                    sentences.append(event.get('text', ''))
                if event.get('type') == 'tts' and event.get('state') == 'stop':
                    break
        await asyncio.wait_for(collect(), 150)
    assert transcript, 'No ASR transcript returned'
    assert sentences, 'No assistant response returned'
    assert audio_packets > 0, 'No playable Opus audio returned'
    print('PASS', json.dumps({'transcript': transcript, 'reply': ' '.join(sentences),
                              'audio_packets': audio_packets,
                              'audio_seconds': round(audio_samples / 16000, 2)}), flush=True)


asyncio.run(main())
