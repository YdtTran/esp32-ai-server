"""Single CPU Piper worker with a bounded internal HTTP synthesis API."""
import argparse
import io
import json
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from audio import FORMAT, wav_to_pcm


def make_server(address, voice):
    busy = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def do_GET(self):
            self.send_response(200 if self.path == "/health" else 404)
            self.end_headers()

        def do_POST(self):
            if self.path != "/synthesize":
                self.send_error(404)
                return
            if not busy.acquire(blocking=False):
                self.send_error(503, "Piper is busy; no automatic retry")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("Request size must be 1..16384 bytes")
                payload = json.loads(self.rfile.read(length))
                text = payload.get("text") if isinstance(payload, dict) else None
                if not isinstance(text, str) or not text.strip() or len(text) > 2000:
                    raise ValueError("Text must contain 1..2000 characters")
                audio = io.BytesIO()
                with wave.open(audio, "wb") as wav:
                    voice.synthesize_wav(text, wav)
                pcm = wav_to_pcm(audio.getvalue())
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("X-Audio-Format", FORMAT)
                self.send_header("Content-Length", str(len(pcm)))
                self.end_headers()
                self.wfile.write(pcm)
            except (ValueError, TypeError, OSError, wave.Error) as exc:
                self.send_error(400, str(exc))
            except Exception:
                self.send_error(500, "Piper synthesis failed")
            finally:
                busy.release()

    return ThreadingHTTPServer(address, Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice-directory", default="/voices")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    from piper import PiperVoice
    from voice import ensure_voice
    voice = PiperVoice.load(str(ensure_voice(args.voice_directory)), use_cuda=False)
    with make_server(("0.0.0.0", args.port), voice) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
