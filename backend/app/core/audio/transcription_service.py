import os
import tempfile
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from fastapi import UploadFile, HTTPException, status

logger = logging.getLogger(__name__)

# Allowed audio mime types and extensions
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".webm", ".ogg", ".m4a", ".mp4", ".aac"}
ALLOWED_MIME_TYPES = {
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/webm", "audio/ogg", "audio/mpeg", "audio/mp3",
    "audio/m4a", "audio/x-m4a", "audio/mp4", "audio/aac",
    "application/octet-stream"
}
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB max


class AudioTranscriptionService:
    """
    Local speech-to-text service using faster-whisper with lazy model loading.
    Configured for CPU execution with INT8 quantization for low memory and fast startup.
    """
    _instance: Optional["AudioTranscriptionService"] = None
    _model = None
    _model_lock = asyncio.Lock()

    def __init__(self, model_size: str = "tiny"):
        self.model_size = model_size
        self.device = "cpu"
        self.compute_type = "int8"

    @classmethod
    def get_instance(cls) -> "AudioTranscriptionService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _get_or_load_model(self):
        """Lazy loader for faster-whisper model."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info(
                    f"Loading faster-whisper model '{self.model_size}' (device={self.device}, compute_type={self.compute_type})..."
                )
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=None
                )
                logger.info("faster-whisper model loaded successfully.")
            except ImportError:
                logger.error("faster-whisper package is not installed.")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Local speech-to-text package (faster-whisper) is not available on this server."
                )
            except Exception as e:
                logger.error(f"Failed to load faster-whisper model: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Speech transcription model initialization failed: {str(e)}"
                )
        return self._model

    async def transcribe_audio_file(self, file: UploadFile) -> Dict[str, Any]:
        """
        Validates, saves to a temporary secure location, transcribes, and cleanly unlinks audio.
        """
        # 1. Validate file extension
        filename = file.filename or "recording.webm"
        _, ext = os.path.splitext(filename.lower())
        if not ext:
            ext = ".webm"

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        # 2. Validate MIME type
        content_type = (file.content_type or "").lower()
        if content_type and content_type not in ALLOWED_MIME_TYPES:
            # Allow fallback if extension matches
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid audio Content-Type '{content_type}'."
                )

        temp_path = None
        try:
            # 3. Read content and enforce size limits
            content = await file.read()
            if not content or len(content) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Audio file is empty. Please record or upload a valid audio consultation."
                )

            if len(content) > MAX_AUDIO_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Audio file exceeds maximum size of {MAX_AUDIO_BYTES // (1024 * 1024)} MB."
                )

            # 4. Write to temporary file
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name

            # 5. Acquire lock for sequential CPU-friendly transcription
            async with self._model_lock:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self._run_transcription, temp_path)
                return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during transcription: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Audio transcription failed: {str(e)}"
            )
        finally:
            # Always delete the temporary raw audio file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception as unlink_err:
                    logger.warning(f"Failed to remove temporary audio file {temp_path}: {unlink_err}")

    def _run_transcription(self, file_path: str) -> Dict[str, Any]:
        """Synchronous helper running inside threadpool executor."""
        model = self._get_or_load_model()
        segments, info = model.transcribe(
            file_path,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        segment_texts = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                segment_texts.append(text)

        full_transcript = " ".join(segment_texts).strip()
        if not full_transcript:
            full_transcript = "No audible dialogue detected in the recording."

        return {
            "transcript": full_transcript,
            "language": getattr(info, "language", "en"),
            "duration": getattr(info, "duration", None)
        }


# Singleton accessor
def get_transcription_service() -> AudioTranscriptionService:
    return AudioTranscriptionService.get_instance()
