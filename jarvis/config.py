"""
Loads configuration from environment variables (via a .env file in the
project root) and exposes it as a single Config object.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    # --- Claude (the "brain") ---
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

    # --- Wake word / conversation behavior ---
    wake_word: str = os.getenv("WAKE_WORD", "jarvis").lower()
    follow_up_window_seconds: float = float(os.getenv("FOLLOW_UP_WINDOW_SECONDS", "12"))
    assistant_name: str = os.getenv("ASSISTANT_NAME", "Jarvis")

    # --- Speech-to-text (local faster-whisper) ---
    whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "small")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")  # "cpu" or "cuda"
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    input_device_index: str = os.getenv("INPUT_DEVICE_INDEX", "")  # blank = default mic

    # --- Text-to-speech ---
    tts_rate: int = int(os.getenv("TTS_RATE", "185"))
    tts_voice_substring: str = os.getenv("TTS_VOICE", "")  # e.g. "Zira", "David"

    # --- Spotify ---
    spotify_client_id: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    spotify_client_secret: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    spotify_redirect_uri: str = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

    # --- Safety ---
    # When True, Jarvis speaks the exact shell command it wants to run and
    # requires you to confirm ("yes" / "confirm" / "do it") before running
    # anything that matches a destructive-pattern list. Read-only / harmless
    # commands still run immediately either way.
    confirm_dangerous_commands: bool = _bool("CONFIRM_DANGEROUS_COMMANDS", True)
    # When True, EVERY run_command call requires spoken confirmation first.
    # Off by default -- turn on if you want maximum caution.
    confirm_all_commands: bool = _bool("CONFIRM_ALL_COMMANDS", False)
    # Root folder that read_file/write_file/list_dir are restricted to.
    # Leave blank to allow any path on disk.
    files_root: str = os.getenv("FILES_ROOT", "")

    def validate(self) -> list:
        problems = []
        if not self.anthropic_api_key:
            problems.append("ANTHROPIC_API_KEY is not set in .env")
        if not self.spotify_client_id or not self.spotify_client_secret:
            problems.append(
                "SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET not set -- Spotify tools will be disabled"
            )
        return problems


config = Config()
