"""Text-to-speech. Audio is generated in advance so the VR show runs without internet."""
import asyncio
from pathlib import Path
import shutil
import struct
import wave

from .config import Settings


class TTSError(Exception):
    pass


def _silent_wav(path: Path, seconds: float = 1.0, rate: int = 16000) -> None:
    """Offline stub: writes a short silent WAV (used in tests and when no TTS is available)."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<h", 0) * int(seconds * rate))


async def synthesize(settings: Settings, text: str, lang: str, out_dir: Path, name: str) -> tuple[Path, str, str]:
    """Return (file path, voice, mime type)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    voice = settings.voice_ru if lang == "ru" else settings.voice_en

    if settings.tts_provider == "edge":
        try:
            import edge_tts  # optional dependency, see requirements.txt
        except ImportError as exc:
            raise TTSError("edge-tts is not installed") from exc
        path = out_dir / f"{name}.mp3"
        try:
            await edge_tts.Communicate(text, voice).save(str(path))
        except Exception as exc:  # network or service error
            raise TTSError(f"TTS service failed: {exc}") from exc
        # Unreal imports WAV, not MP3: convert when ffmpeg is available (it is in the Docker image).
        if shutil.which("ffmpeg"):
            wav = path.with_suffix(".wav")
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "48000", str(wav))
            if await proc.wait() == 0:
                path.unlink(missing_ok=True)
                return wav, voice, "audio/wav"
        return path, voice, "audio/mpeg"

    path = out_dir / f"{name}.wav"
    _silent_wav(path)
    return path, "silent", "audio/wav"
