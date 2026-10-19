"""Adapter for the local Piper /synthesize PCM16 endpoint."""

import asyncio
import io
import json
import wave
from urllib.request import Request, urlopen

from core.providers.tts.base import TTSProviderBase


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        self.url = config["url"].rstrip("/") + "/synthesize"
        self.audio_file_type = "wav"

    def _synthesize(self, text):
        request = Request(
            self.url,
            data=json.dumps({"text": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        max_bytes = 16000 * 2 * 60
        with urlopen(request, timeout=self.tts_timeout) as response:
            if response.headers.get("X-Audio-Format") != "pcm-s16le-16000-mono":
                raise ValueError("Piper returned an unsupported audio format")
            pcm = response.read(max_bytes + 1)
        if not pcm or len(pcm) % 2 or len(pcm) > max_bytes:
            raise ValueError("Piper returned empty, incomplete, or oversized PCM16 audio")

        output = io.BytesIO()
        with wave.open(output, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(pcm)
        return output.getvalue()

    async def text_to_speak(self, text, output_file):
        audio = await asyncio.to_thread(self._synthesize, text)
        if output_file:
            with open(output_file, "wb") as output:
                output.write(audio)
        else:
            return audio
