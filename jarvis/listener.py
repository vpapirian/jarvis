"""
Microphone capture.

Uses `speech_recognition` purely for its battle-tested phrase segmentation
(it listens continuously, uses an energy threshold to detect when you start
and stop talking, and hands back one clean audio clip per phrase). We do NOT
use its online recognizers -- transcription is done locally by
transcriber.py (faster-whisper), so no audio ever leaves your machine.
"""
import io
import logging

import speech_recognition as sr

from .config import config

log = logging.getLogger("jarvis.listener")


class Listener:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # Let the recognizer figure out pause/phrase boundaries dynamically
        # instead of a fixed energy threshold -- adapts to your room's noise.
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8  # seconds of silence = end of phrase

        device_index = None
        if config.input_device_index.strip():
            device_index = int(config.input_device_index)

        self.microphone = sr.Microphone(device_index=device_index)

        with self.microphone as source:
            log.info("Calibrating microphone for ambient noise (stay quiet for a sec)...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1.5)
        log.info("Microphone ready.")

    def listen_once(self, timeout=None, phrase_time_limit=20) -> bytes | None:
        """
        Blocks until a phrase is spoken (or `timeout` seconds pass with no
        speech at all), then returns 16-bit mono WAV bytes of that phrase.
        Returns None on timeout.
        """
        with self.microphone as source:
            try:
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )
            except sr.WaitTimeoutError:
                return None
        return audio.get_wav_data()

    @staticmethod
    def wav_bytes_to_buffer(wav_bytes: bytes) -> io.BytesIO:
        return io.BytesIO(wav_bytes)
