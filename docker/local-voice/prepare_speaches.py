"""Ensure the selected Whisper model is cached before starting Xiaozhi."""
import json
from urllib.request import Request, urlopen

model = "Systran/faster-distil-whisper-small.en"
endpoint = "http://speaches:8000/v1/models"
with urlopen(endpoint, timeout=30) as response:
    cached = json.load(response)["data"]
if any(item["id"] == model for item in cached):
    print(f"Whisper model ready: {model}")
else:
    print(f"Downloading Whisper model: {model}", flush=True)
    with urlopen(Request(f"{endpoint}/{model}", method="POST"), timeout=1800) as response:
        response.read()
    print(f"Whisper model ready: {model}")
