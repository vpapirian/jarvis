from types import SimpleNamespace
from unittest import mock

import pytest

from jarvis import brain
from jarvis.brain import Brain, trim_history


def user(text):
    return {"role": "user", "content": text}


def assistant_tool_use(tool_id):
    return {"role": "assistant", "content": [SimpleNamespace(type="tool_use", id=tool_id)]}


def tool_result(tool_id):
    return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_id}]}


def assistant_text(text):
    return {"role": "assistant", "content": [SimpleNamespace(type="text", text=text)]}


def make_turn(i):
    return [user(f"q{i}"), assistant_tool_use(f"t{i}"), tool_result(f"t{i}"), assistant_text(f"a{i}")]


def test_short_history_is_unchanged():
    history = make_turn(0)
    assert trim_history(history, limit=40) == history


def test_trim_starts_on_a_plain_user_message():
    history = [m for i in range(20) for m in make_turn(i)]  # 80 messages
    trimmed = trim_history(history, limit=10)
    assert len(trimmed) <= 10
    assert trimmed[0]["role"] == "user" and isinstance(trimmed[0]["content"], str)


def test_trim_never_orphans_a_tool_result():
    history = [m for i in range(10) for m in make_turn(i)]
    for limit in range(1, 40):
        trimmed = trim_history(history, limit=limit)
        seen = set()
        for m in trimmed:
            if isinstance(m["content"], list):
                for block in m["content"]:
                    if isinstance(block, dict) and block["type"] == "tool_result":
                        assert block["tool_use_id"] in seen
                    elif getattr(block, "type", None) == "tool_use":
                        seen.add(block.id)


def test_trim_keeps_a_long_tool_loop_whole():
    history = [user("do lots")]
    for i in range(30):
        history += [assistant_tool_use(f"t{i}"), tool_result(f"t{i}")]
    trimmed = trim_history(history, limit=5)
    assert trimmed[0] == history[0]
    assert len(trimmed) == len(history)


@pytest.fixture
def jarvis_brain():
    with mock.patch.object(brain.anthropic, "Anthropic") as client_cls:
        b = Brain()
        b.client = client_cls.return_value
        yield b


def test_failed_request_restores_history(jarvis_brain):
    jarvis_brain.history = make_turn(0)
    before = list(jarvis_brain.history)
    tool_response = SimpleNamespace(
        stop_reason="tool_use",
        content=[SimpleNamespace(type="tool_use", id="x", name="list_dir", input={})],
    )
    # First call asks for a tool, the follow-up call fails.
    jarvis_brain.client.messages.create.side_effect = [tool_response, RuntimeError("API down")]
    with mock.patch.object(jarvis_brain, "_dispatch", return_value={"ok": True}):
        with pytest.raises(RuntimeError):
            jarvis_brain.respond("list my files")
    assert jarvis_brain.history == before


def test_successful_turn_is_recorded(jarvis_brain):
    jarvis_brain.client.messages.create.return_value = SimpleNamespace(
        stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Hello, sir.")]
    )
    assert jarvis_brain.respond("hi") == "Hello, sir."
    assert jarvis_brain.history[0] == user("hi")
    assert jarvis_brain.history[-1]["role"] == "assistant"
