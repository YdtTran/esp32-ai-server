"""Download only the selected revision-pinned voice into a persistent volume."""
import hashlib
from pathlib import Path
from urllib.request import urlopen

REVISION = "c10ece1aade47bb51c153c893d14e5bf8e5b7117"
VOICE = "en_US-ljspeech-medium.onnx"
HASHES = {
    VOICE: "6f52a751e2349abe7a76735eb09dc1875298c77ea2342ffd2fef79ff81b87f22",
    VOICE + ".json": "141d612cc0a95ed7efc1ca936b845c2364967f2e9217c5dbfcf69fc4d6c65860",
}


def ensure_voice(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    for name, digest in HASHES.items():
        target = root / name
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            continue
        url = (f"https://huggingface.co/rhasspy/piper-voices/resolve/{REVISION}"
               f"/en/en_US/ljspeech/medium/{name}")
        temporary = target.with_suffix(target.suffix + ".part")
        checksum = hashlib.sha256()
        try:
            with urlopen(url, timeout=60) as response, temporary.open("wb") as output:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > 70 * 1024 * 1024:
                        raise ValueError("Voice download exceeded 70 MiB")
                    checksum.update(chunk)
                    output.write(chunk)
            if checksum.hexdigest() != digest:
                raise ValueError(f"Voice checksum mismatch: {name}")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return root / VOICE
