import os
import tempfile

from openai import AsyncOpenAI

from app.core.config import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

ALLOWED_AUDIO_TYPES = {"audio/mpeg", "audio/mp4", "audio/wav", "audio/webm", "audio/x-m4a"}


async def transcribe_audio(file_content: bytes, content_type: str) -> str:
    ext_map = {
        "audio/mpeg": ".mp3",
        "audio/mp4": ".mp4",
        "audio/wav": ".wav",
        "audio/webm": ".webm",
        "audio/x-m4a": ".m4a",
    }
    ext = ext_map.get(content_type, ".mp3")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            response = await _client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
            )
        return response.text
    finally:
        os.unlink(tmp_path)
