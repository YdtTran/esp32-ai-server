"""Run without the server dependency stack: python tests/test_piper_adapter.py."""

import asyncio
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
import wave


class ProviderBase:
    def __init__(self, config, delete_audio_file):
        self.tts_timeout = config.get("tts_timeout", 15)


# Isolate the adapter's HTTP/audio contract from unrelated audio/AI packages.
spec = importlib.util.spec_from_file_location(
    "piper_adapter", Path(__file__).resolve().parents[1] / "core/providers/tts/piper.py"
)
adapter = importlib.util.module_from_spec(spec)
with patch.dict("sys.modules", {
    "core.providers.tts.base": types.SimpleNamespace(TTSProviderBase=ProviderBase)
}):
    spec.loader.exec_module(adapter)


class PiperAdapterTest(unittest.TestCase):
    def setUp(self):
        self.pcm = b"\x00\x00\xff\x7f\x00\x80" * 160
        self.format = "pcm-s16le-16000-mono"
        self.status = 200
        self.requests = []
        case = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                case.requests.append((self.path, json.loads(
                    self.rfile.read(int(self.headers["Content-Length"]))
                )))
                self.send_response(case.status)
                self.send_header("X-Audio-Format", case.format)
                self.end_headers()
                self.wfile.write(case.pcm)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.provider = adapter.TTSProvider({
            "url": f"http://127.0.0.1:{self.server.server_port}/", "tts_timeout": 2,
        }, True)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()

    def test_pcm_becomes_playable_wav_and_preserves_samples(self):
        result = asyncio.run(self.provider.text_to_speak("Hello, café.", None))
        with wave.open(io.BytesIO(result), "rb") as audio:
            self.assertEqual((audio.getnchannels(), audio.getsampwidth(),
                              audio.getframerate()), (1, 2, 16000))
            self.assertEqual(audio.readframes(audio.getnframes()), self.pcm)
        self.assertEqual(self.requests, [("/synthesize", {"text": "Hello, café."})])

    def test_writes_wav_when_audio_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "speech.wav"
            asyncio.run(self.provider.text_to_speak("Hello.", str(output)))
            with wave.open(str(output), "rb") as audio:
                self.assertEqual(audio.readframes(audio.getnframes()), self.pcm)

    def test_rejects_unrecognized_format(self):
        self.format = "pcm-s16le-22050-mono"
        with self.assertRaisesRegex(ValueError, "unsupported"):
            asyncio.run(self.provider.text_to_speak("Hello.", None))

    def test_rejects_malformed_or_oversized_audio(self):
        for pcm in (b"", b"\x00", b"\x00" * (16000 * 2 * 60 + 2)):
            with self.subTest(length=len(pcm)):
                self.pcm = pcm
                with self.assertRaisesRegex(ValueError, "PCM16"):
                    asyncio.run(self.provider.text_to_speak("Hello.", None))

    def test_http_errors_propagate(self):
        self.status = 503
        with self.assertRaises(HTTPError):
            asyncio.run(self.provider.text_to_speak("Hello.", None))
        self.assertEqual(len(self.requests), 1)


if __name__ == "__main__":
    unittest.main()
