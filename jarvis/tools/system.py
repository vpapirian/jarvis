"""
General-purpose system control: run arbitrary shell commands and launch
applications. This is what gives Jarvis "do anything" capability -- combined
with Claude's own knowledge, it can figure out the right command for almost
any request (open an app, check disk space, install a package, kill a
process, query system info, etc).

Safety: a small pattern list flags commands that are destructive/irreversible
(deleting files, formatting drives, shutting the PC down, killing processes,
editing the registry...). When config.confirm_dangerous_commands is True
(the default), those commands are NOT run silently -- the caller must supply
a confirm_callback (main.py wires this up to "Jarvis speaks the command out
loud and listens for you to say yes/confirm") that returns True/False.
Set CONFIRM_DANGEROUS_COMMANDS=false in .env to disable this and let it run
everything immediately -- only do that if you're comfortable with that risk.
"""
import logging
import re
import subprocess

from ..config import config

log = logging.getLogger("jarvis.tools.system")

_DANGEROUS_PATTERNS = [
    r"\bdel\b", r"\berase\b", r"\brd\b", r"\brmdir\b", r"remove-item",
    r"\bformat\b", r"diskpart", r"\bshutdown\b", r"restart-computer",
    r"stop-computer", r"taskkill", r"stop-process", r"reg\s+delete",
    r"reg\s+add", r"netsh", r"bcdedit", r"cipher\s+/w", r"\brm\b",
    r"mkfs", r">\s*/dev/", r"Remove-Item", r"\bdrop\b", r"truncate",
]
_DANGEROUS_RE = re.compile("|".join(_DANGEROUS_PATTERNS), re.IGNORECASE)


def is_dangerous(command: str) -> bool:
    return bool(_DANGEROUS_RE.search(command))


def run_command(command: str, working_dir: str | None = None, confirm_callback=None) -> dict:
    """
    Runs `command` in a Windows shell (cmd.exe) and returns stdout/stderr/
    return code. If the command looks destructive and confirmation is
    required, calls confirm_callback(command) first and aborts if it
    returns False (or if no callback was supplied).
    """
    needs_confirm = config.confirm_all_commands or (
        config.confirm_dangerous_commands and is_dangerous(command)
    )
    if needs_confirm:
        if confirm_callback is None or not confirm_callback(command):
            return {
                "ran": False,
                "reason": "Not confirmed by user -- command was not executed.",
            }

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_dir or None,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {
            "ran": True,
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {"ran": False, "reason": "Command timed out after 60 seconds."}
    except Exception as e:  # noqa: BLE001
        return {"ran": False, "reason": f"Failed to run command: {e}"}


def open_application(name: str) -> dict:
    """
    Launches an application by name (e.g. "notepad", "chrome", "spotify",
    "calc") or opens a file/folder path. Uses the same resolution Win+R
    would (PATH + registered App Paths).
    """
    try:
        subprocess.Popen(f'start "" "{name}"', shell=True)
        return {"opened": True, "name": name}
    except Exception as e:  # noqa: BLE001
        return {"opened": False, "reason": str(e)}
