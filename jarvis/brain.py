"""
The "brain": sends what you said to Claude, along with a broad set of tools,
and runs Claude's tool-use loop until it produces a final spoken reply.

Claude already carries broad general knowledge and reasoning on its own --
for anything that isn't a concrete action (questions, explanations, advice,
"what's the capital of...", "explain quantum computing", etc) it just
answers directly with no tool call at all. The tools below are what let it
additionally *do* things on your PC: run commands, manage files, control
the browser, and control Spotify.
"""
import logging

import anthropic

from .config import config
from .tools import browser, files, spotify, system

log = logging.getLogger("jarvis.brain")

SYSTEM_PROMPT = f"""You are {config.assistant_name}, a spoken voice assistant running \
locally on the user's Windows PC, in the style of Iron Man's J.A.R.V.I.S. \
You hear the user through speech-to-text and your replies are read aloud \
with text-to-speech, so:
- Keep replies short, natural, and conversational -- a sentence or two \
unless the user clearly wants detail. No markdown, no bullet points, no \
headers: plain spoken sentences only.
- You have real tools that act on the user's actual computer (running \
commands, managing files, opening browser tabs, controlling Spotify). Use \
them whenever the user asks you to *do* something, don't just describe how.
- When you take an action, always acknowledge it in-character, naming the \
specific thing you did -- e.g. "Yes sir, opening Chrome now," "Right away, \
skipping to the next track," "Done -- Notepad is open." Address the user \
as "sir" the way J.A.R.V.I.S. does. Keep it to one short sentence; don't \
also restate the acknowledgment separately from the result -- one line \
that both confirms and reports what happened is enough. If a tool call \
fails, say so plainly in the same in-character voice rather than staying \
silent about it.
- For anything that's a question rather than an action, just answer it \
directly from your own knowledge -- you don't need a tool for that.
- If a request is ambiguous about *which* application, file, or song, make \
the most reasonable choice yourself rather than peppering the user with \
questions -- this is a voice interface, back-and-forth clarification is \
costly. Only ask when truly necessary.
- If a tool call fails or comes back with an error, briefly tell the user \
what went wrong in plain language instead of silently giving up.
- A little dry wit is fine, but don't overdo it.
"""

TOOLS = [
    {
        "name": "run_command",
        "description": (
            "Run a Windows shell (cmd.exe) command and return its output. "
            "Use this for anything not covered by a more specific tool: "
            "checking system info, managing processes, installing things, "
            "querying disk space, etc. Destructive-looking commands "
            "(deleting files, shutting down, killing processes...) will "
            "prompt the user for a spoken confirmation before running."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command to run."},
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory to run it from.",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "open_application",
        "description": "Open/launch an application by name (e.g. 'notepad', 'chrome', 'spotify', 'calc'), or open a file/folder path with its default app.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the text content of a file.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write (or append) text content to a file, creating folders as needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "append": {"type": "boolean", "description": "Append instead of overwrite. Default false."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_dir",
        "description": "List the contents of a folder.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Defaults to current directory."}},
        },
    },
    {
        "name": "open_browser_tab",
        "description": "Open a URL in a new browser tab.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "web_search",
        "description": "Open a Google search for a query in a new browser tab.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "spotify_play",
        "description": "Play a song/artist on Spotify (searches and plays the best match), or resume playback if no query is given.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "e.g. 'Blinding Lights by The Weeknd'. Omit to just resume."}},
        },
    },
    {"name": "spotify_pause", "description": "Pause Spotify playback.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "spotify_next", "description": "Skip to the next Spotify track.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "spotify_previous", "description": "Go back to the previous Spotify track.", "input_schema": {"type": "object", "properties": {}}},
    {
        "name": "spotify_set_volume",
        "description": "Set Spotify playback volume.",
        "input_schema": {
            "type": "object",
            "properties": {"level": {"type": "integer", "description": "0-100"}},
            "required": ["level"],
        },
    },
    {"name": "spotify_now_playing", "description": "Get the currently playing Spotify track.", "input_schema": {"type": "object", "properties": {}}},
]


class Brain:
    def __init__(self, confirm_callback=None):
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self.history = []
        self.confirm_callback = confirm_callback

    def _dispatch(self, name: str, tool_input: dict) -> dict:
        try:
            if name == "run_command":
                return system.run_command(
                    tool_input["command"],
                    tool_input.get("working_dir"),
                    confirm_callback=self.confirm_callback,
                )
            if name == "open_application":
                return system.open_application(tool_input["name"])
            if name == "read_file":
                return files.read_file(tool_input["path"])
            if name == "write_file":
                return files.write_file(
                    tool_input["path"], tool_input["content"], tool_input.get("append", False)
                )
            if name == "list_dir":
                return files.list_dir(tool_input.get("path", "."))
            if name == "open_browser_tab":
                return browser.open_browser_tab(tool_input["url"])
            if name == "web_search":
                return browser.web_search(tool_input["query"])
            if name == "spotify_play":
                return spotify.spotify_play(tool_input.get("query", ""))
            if name == "spotify_pause":
                return spotify.spotify_pause()
            if name == "spotify_next":
                return spotify.spotify_next()
            if name == "spotify_previous":
                return spotify.spotify_previous()
            if name == "spotify_set_volume":
                return spotify.spotify_set_volume(tool_input["level"])
            if name == "spotify_now_playing":
                return spotify.spotify_now_playing()
            return {"ok": False, "reason": f"Unknown tool '{name}'"}
        except Exception as e:  # noqa: BLE001
            log.exception("Tool %s failed", name)
            return {"ok": False, "reason": str(e)}

    def respond(self, user_text: str) -> str:
        """Sends user_text to Claude, runs any tool calls, returns the final spoken reply."""
        self.history.append({"role": "user", "content": user_text})
        # Keep the transcript from growing unbounded.
        self.history = self.history[-40:]

        while True:
            response = self.client.messages.create(
                model=config.claude_model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=self.history,
            )
            self.history.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                final_text = "".join(
                    block.text for block in response.content if block.type == "text"
                ).strip()
                return final_text

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                log.info("Tool call: %s(%s)", block.name, block.input)
                result = self._dispatch(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    }
                )
            self.history.append({"role": "user", "content": tool_results})
