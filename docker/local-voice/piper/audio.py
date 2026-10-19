"""Development speaker-pcm v1 validation and WAV conversion."""
import audioop
import io
import wave

SAMPLE_RATE = 16000
MAX_BYTES = SAMPLE_RATE * 2 * 60
FORMAT = "pcm-s16le-16000-mono"


def validate_pcm(pcm):
    if not pcm or len(pcm) % 2 or len(pcm) > MAX_BYTES:
        raise ValueError("Speaker PCM must contain 1..960000 complete PCM16 samples")
    return pcm


def wav_to_pcm(data):
    with wave.open(io.BytesIO(data), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
            raise ValueError("Piper must return mono PCM16 WAV")
        rate = audio.getframerate()
        if not 8000 <= rate <= 48000 or audio.getnframes() > rate * 60:
            raise ValueError("Piper WAV rate/duration exceeds prototype limits")
        frames = audio.readframes(audio.getnframes())
    if rate != SAMPLE_RATE:
        frames, _ = audioop.ratecv(frames, 2, 1, rate, SAMPLE_RATE, None)
    return validate_pcm(frames)
