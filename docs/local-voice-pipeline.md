# Standalone local voice pipeline

This repository owns the Compose definitions, Piper service, prompt and voice
configuration. No other checkout, machine-specific source path, or pre-existing
Docker volume is required. The earlier IoT project served as a reference only.

The pipeline is Xiaozhi/Silero VAD → Speaches (faster-whisper) → Ollama → Piper
→ Xiaozhi Opus output. ESP32 devices use the Xiaozhi protocol/firmware.
The selected Whisper and Piper models support English. Voice inference uses no
cloud API keys. The separate vision endpoint retains the upstream configuration.

## Start

Requirements: Docker Compose v2+, an NVIDIA GPU with Docker GPU support, and
internet access for the first image/model downloads. This stack was tested on
Docker Desktop with an RTX 2050 (4 GB). Native Python is not required to run it.

Set `server.websocket` in `main/xiaozhi-server/config.local-voice.yaml` to
`ws://<PC-LAN-IP>:8000/xiaozhi/v1/`. The current deployment uses `10.127.9.237`;
change that value on another PC or network. Then run from this repository:

```powershell
docker compose -f compose.local-voice.yaml up -d --build
docker compose -f compose.local-voice.yaml ps -a
docker compose -f compose.local-voice.yaml logs --tail 80 server
```

Compose creates its own persistent volumes: `xiaozhi-local-voice_ollama-models`,
`xiaozhi-local-voice_speaches-hf-hub-cache`, and
`xiaozhi-local-voice_piper-voices`. Missing models are prepared automatically:

- `ollama-init` checks for `qwen3:1.7b` and pulls it if absent.
- `speaches-init` checks for `Systran/faster-distil-whisper-small.en` and
  downloads it through Speaches if absent.
- The repository's Piper service downloads and verifies its revision-pinned
  `en_US-ljspeech-medium` voice before reporting healthy.

The server waits for both model initialization jobs and Piper. Initialization
jobs exiting with status 0 are expected. Cached models persist across restarts.
For this PC's migration, existing model caches were copied once into these new
volumes; the original caches are preserved and are no longer mounted.

Set the ESP32 OTA URL to `http://<PC-LAN-IP>:8003/xiaozhi/ota/`.
WebSocket/OTA ports are 8000/8003. Local-only diagnostic ports are 11435 for
Ollama, 18000 for Speaches, and 15000 for Piper. Native Ollama on 11434 can keep
running. Device authentication retains the trusted-LAN upstream default.

The stack mounts its own `config.local-voice.yaml` override, preserving upstream
`config.yaml` and any `data/.config.yaml`. Intent tools and persistent memory
are disabled. The short English prompt avoids weather/location lookups and
Chinese wake-word recordings. The Piper adapter wraps validated PCM16 as WAV
before Xiaozhi encodes it for the device.

## Verify

```powershell
docker compose -f compose.local-voice.yaml config --quiet
python docker/local-voice/test_prepare_speaches.py
python main/xiaozhi-server/tests/test_piper_adapter.py
docker compose -f compose.local-voice.yaml exec -T server python tests/live_local_voice_smoke.py
```

The live smoke test uses the running services and a simulated WebSocket device.
It synthesizes a question, sends it as microphone Opus packets, and checks for
an ASR transcript, an assistant reply, decodable Opus speech and a TTS stop event.
It does not test physical ESP32 capture/playback or automatic VAD.

Verified on 2026-10-19 with the repository-owned service definitions and model
volumes: all four services healthy, both model jobs exited successfully, eight
unit tests passed, and the live test returned “2 plus 2 equals 4” with 36
decodable audio packets (2.16 seconds). No files or volumes from the reference
project were mounted.

Stop with `docker compose -f compose.local-voice.yaml down`. Models persist.
Adding `-v` deletes this stack's model volumes and requires downloading again.
