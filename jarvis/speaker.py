"""
Offline text-to-speech (Windows SAPI5 via pyttsx3) -- Jarvis's voice.

Note: pyttsx3's SAPI5 driver on Windows has a well-known bug where reusing
one engine instance across multiple say()/runAndWait() calls works the
first time and then silently produces no audio afterward. The reliable
fix (used here) is to create a fresh engine for every single utterance
instead of keeping one around.
"""
import logging

import pyttsx3

from .config import config

log = logging.getLogger("jarvis.speaker")


class Speaker:
    def __init__(self):
        # Just sanity-check TTS works at all on this machine; this throwaway
        # engine is not reused for actual speech (see `say` below).
        probe = pyttsx3.init()
        probe.stop()

    def _new_engine(self):
        engine = pyttsx3.init()
        engine.setProperty("rate", config.tts_rate)
        if config.tts_voice_substring:
            wanted = config.tts_voice_substring.lower()
            for voice in engine.getProperty("voices"):
                if wanted in voice.name.lower():
                    engine.setProperty("voice", voice.id)
                    break
        return engine

    def say(self, text: str):
        if not text:
            return
        print(f"{config.assistant_name}: {text}")
        engine = self._new_engine()
        try:
            engine.say(text)
            engine.runAndWait()
        finally:
            engine.stop()
