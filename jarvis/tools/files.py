"""
File read/write/list tools. If config.files_root is set, every path is
restricted to that folder (safer default for voice-driven file edits). Leave
FILES_ROOT blank in .env to allow any path on disk.
"""
from pathlib import Path

from ..config import config


def _resolve(path: str) -> Path:
    p = Path(path).expanduser()
    if config.files_root:
        root = Path(config.files_root).expanduser().resolve()
        candidate = (root / p).resolve() if not p.is_absolute() else p.resolve()
        if root not in candidate.parents and candidate != root:
            raise PermissionError(
                f"Path '{path}' is outside the allowed files root '{root}'."
            )
        return candidate
    return p.resolve()


def read_file(path: str, max_chars: int = 8000) -> dict:
    try:
        p = _resolve(path)
        text = p.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > max_chars
        return {"ok": True, "content": text[:max_chars], "truncated": truncated}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)}


def write_file(path: str, content: str, append: bool = False) -> dict:
    try:
        p = _resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(p, mode, encoding="utf-8") as f:
            f.write(content)
        return {"ok": True, "path": str(p)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)}


def list_dir(path: str = ".") -> dict:
    try:
        p = _resolve(path)
        entries = sorted(e.name + ("/" if e.is_dir() else "") for e in p.iterdir())
        return {"ok": True, "entries": entries}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": str(e)}
