"""
Entry point. Wires together: mic listener -> local Whisper transcription ->
wake-word gate -> Claude brain (with tools) -> TTS speaker, in a loop.

Run with:  python -m jarvis.main
"""
import difflib
import logging
import sys

from .brain import Brain
from .config import config
from .listener import Listener
from .speaker import Speaker
from .transcriber import Transcriber

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("jarvis.main")

_YES_WORDS = ("yes", "yeah", "yep", "confirm", "do it", "go ahead", "affirmative", "sure")

# How close a heard word has to sound to the wake word to count. Local
# Whisper models frequently mishear "Jarvis" as "Jervis", "Harvis", etc,
# so we match fuzzily on similarity instead of requiring an exact substring.
_WAKE_WORD_SIMILARITY_THRESHOLD = 0.72


def _strip_wake_word(text: str, wake_word: str) -> str | None:
    """
    Returns the remainder of `text` after the wake word, or None if nothing
    in `text` sounds close enough to the wake word. Tolerant of Whisper
    mishearing "Jarvis" as similar-sounding words.
    """
    wake_word = wake_word.lower().strip()
    wake_tokens = wake_word.split()
    n = len(wake_tokens)

    raw_words = text.split()
    clean_words = [w.strip(" ,.!?:;\"'").lower() for w in raw_words]

    best_idx = None
    best_ratio = 0.0
    for i in range(len(clean_words) - n + 1):
        candidate = " ".join(clean_words[i:i + n])
        ratio = difflib.SequenceMatcher(None, candidate, wake_word).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_idx = i

    if best_idx is None or best_ratio < _WAKE_WORD_SIMILARITY_THRESHOLD:
        return None

    remainder = " ".join(raw_words[best_idx + n:]).strip(" ,.!?:")
    return remainder


def main():
    problems = config.validate()
    for p in problems:
        log.warning(p)
    if not config.anthropic_api_key:
        log.error("ANTHROPIC_API_KEY is required. Set it in .env and try again.")
        sys.exit(1)

    listener = Listener()
    transcriber = Transcriber()
    speaker = Speaker()

    def confirm_callback(command: str) -> bool:
        speaker.say(f"This will run: {command}. Should I go ahead?")
        wav = listener.listen_once(timeout=8, phrase_time_limit=8)
        if wav is None:
            speaker.say("Didn't hear a response, cancelling that.")
            return False
        answer = transcriber.transcribe_wav_bytes(wav).lower()
        log.info("Confirmation heard: %r", answer)
        return any(word in answer for word in _YES_WORDS)

    brain = Brain(confirm_callback=confirm_callback)

    speaker.say(f"{config.assistant_name} online. Say '{config.wake_word}' any time.")
    log.info("Listening for wake word '%s'...", config.wake_word)

    while True:
        wav = listener.listen_once(timeout=None)
        if wav is None:
            continue
        text = transcriber.transcribe_wav_bytes(wav)
        if not text:
            continue
        log.info("Heard: %r", text)

        command = _strip_wake_word(text, config.wake_word)
        if command is None:
            continue  # wake word not present, ignore

        # In conversation mode we keep listening for follow-ups without
        # needing the wake word again, for a short window after each reply.
        while True:
            if not command:
                speaker.say("Yes?")
                wav = listener.listen_once(timeout=config.follow_up_window_seconds)
                if wav is None:
                    break
                command = transcriber.transcribe_wav_bytes(wav)
                if not command:
                    break

            log.info("Command: %r", command)
            try:
                reply = brain.respond(command)
            except Exception as e:  # noqa: BLE001
                log.exception("Brain error")
                reply = f"Something went wrong on my end: {e}"
            speaker.say(reply or "Done.")

            wav = listener.listen_once(timeout=config.follow_up_window_seconds)
            if wav is None:
                break  # follow-up window elapsed, go back to wake-word mode
            command = transcriber.transcribe_wav_bytes(wav)


if __name__ == "__main__":
    main()
