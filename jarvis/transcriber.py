"""
Local speech-to-text using faster-whisper (CTranslate2 Whisper). Runs
entirely on your machine -- no audio or API key involved for STT.
"""
import logging

from faster_whisper import WhisperModel

from .config import config

log = logging.getLogger("jarvis.transcriber")


class Transcriber:
    def __init__(self):
        log.info(
            "Loading Whisper model '%s' (device=%s, compute=%s) -- first run "
            "downloads the model, this may take a minute...",
            config.whisper_model_size,
            config.whisper_device,
            config.whisper_compute_type,
        )
        self.model = WhisperModel(
            config.whisper_model_size,
            device=config.whisper_device,
            compute_type=config.whisper_compute_type,
        )
        log.info("Whisper model loaded.")

    def transcribe_wav_bytes(self, wav_bytes: bytes) -> str:
        import io

        buf = io.BytesIO(wav_bytes)
        segments, _info = self.model.transcribe(
            buf,
            language="en",
            vad_filter=True,
            beam_size=5,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text
