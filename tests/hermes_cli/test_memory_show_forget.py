"""``hermes memory show`` / ``hermes memory forget`` — deterministic single-entry
inspect/remove of the built-in store, no chat turn required.

Covers issue NousResearch/hermes-agent#135324. The CLI routes through the same
``MemoryStore`` the agent's memory tool uses, so entries/writes stay in step with
what the agent actually loads (same file lock, same whole-entry-exact-first match).
"""

from types import SimpleNamespace

import hermes_cli.main_agent_cmds as mac
from tools import memory_tool


def _write_store(tmp_path, memory_entries=(), user_entries=()):
    from tools.memory_tool_store import ENTRY_DELIMITER
    if memory_entries:
        (tmp_path / "MEMORY.md").write_text(
            ENTRY_DELIMITER.join(memory_entries), encoding="utf-8")
    if user_entries:
        (tmp_path / "USER.md").write_text(
            ENTRY_DELIMITER.join(user_entries), encoding="utf-8")


def _make_store(tmp_path, monkeypatch, memory_entries=(), user_entries=()):
    """Point get_memory_dir at tmp_path so load_on_disk_store() reads/writes there."""
    _write_store(tmp_path, memory_entries, user_entries)
    monkeypatch.setattr("tools.memory_tool.get_memory_dir", lambda: tmp_path)
    return tmp_path


def test_show_lists_memory_and_user_entries(tmp_path, monkeypatch, capsys):
    _make_store(
        tmp_path, monkeypatch,
        memory_entries=["Agent N is the mascot", "Never fabricate data"],
        user_entries=["Prefers concise replies"])
    mac._cmd_memory_show(SimpleNamespace(target="all"))
    out = capsys.readouterr().out
    assert "MEMORY.md" in out
    assert "Agent N is the mascot" in out
    assert "Never fabricate data" in out
    assert "USER.md" in out
    assert "Prefers concise replies" in out
    assert "forget" in out  # hints the remove command


def test_show_target_restricts_store(tmp_path, monkeypatch, capsys):
    _make_store(
        tmp_path, monkeypatch,
        memory_entries=["agent note only"],
        user_entries=["user note only"])
    mac._cmd_memory_show(SimpleNamespace(target="memory"))
    out = capsys.readouterr().out
    assert "agent note only" in out
    assert "user note only" not in out


def test_show_empty_reports_cleanly(tmp_path, monkeypatch, capsys):
    _make_store(tmp_path, monkeypatch)  # no files
    mac._cmd_memory_show(SimpleNamespace(target="all"))
    out = capsys.readouterr().out
    assert "No built-in memory entries found" in out


def test_forget_requires_confirmation_without_yes(tmp_path, monkeypatch, capsys):
    _make_store(tmp_path, monkeypatch, memory_entries=["Remember to hydrate"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: "no")  # declines confirmation
    mac._cmd_memory_forget(SimpleNamespace(target="memory", entry="hydrate", yes=False))
    out = capsys.readouterr().out
    assert "This will permanently remove" in out
    assert "Remember to hydrate" in out
    assert "Cancelled" in out
    # Nothing removed (no confirmation given).
    assert (tmp_path / "MEMORY.md").read_text(encoding="utf-8") == "Remember to hydrate"


def test_forget_confirms_via_typed_yes(tmp_path, monkeypatch, capsys):
    _make_store(tmp_path, monkeypatch, memory_entries=["Fact I typed yes to"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: "yes")
    mac._cmd_memory_forget(SimpleNamespace(target="memory", entry="typed yes", yes=False))
    out = capsys.readouterr().out
    assert "Removed one entry from MEMORY.md" in out
    store = memory_tool.load_on_disk_store()
    assert store._entries_for("memory") == []


def test_forget_confirms_and_persists(tmp_path, monkeypatch, capsys):
    store_dir = _make_store(
        tmp_path, monkeypatch,
        memory_entries=["Remember to hydrate", "Keep secrets out of repos"])
    mac._cmd_memory_forget(SimpleNamespace(target="memory", entry="hydrate", yes=True))
    out = capsys.readouterr().out
    assert "Removed one entry from MEMORY.md" in out
    assert "Remember to hydrate" in out

    # Persisted to disk — a fresh store no longer sees it.
    store = memory_tool.load_on_disk_store()
    assert store._entries_for("memory") == ["Keep secrets out of repos"]
    assert (store_dir / "MEMORY.md").read_text(encoding="utf-8") == "Keep secrets out of repos"


def test_forget_ambiguous_match_removes_nothing(tmp_path, monkeypatch, capsys):
    _make_store(
        tmp_path, monkeypatch,
        memory_entries=["test entry alpha", "test entry beta"])
    mac._cmd_memory_forget(SimpleNamespace(target="memory", entry="entry", yes=True))
    out = capsys.readouterr().out
    assert "Multiple entries matched" in out
    assert "Nothing removed" in out
    # Unchanged on disk.
    assert "test entry alpha" in (tmp_path / "MEMORY.md").read_text(encoding="utf-8")
    assert "test entry beta" in (tmp_path / "MEMORY.md").read_text(encoding="utf-8")


def test_forget_no_match_removes_nothing(tmp_path, monkeypatch, capsys):
    _make_store(tmp_path, monkeypatch, memory_entries=["only entry"])
    mac._cmd_memory_forget(SimpleNamespace(target="memory", entry="nonexistent", yes=True))
    out = capsys.readouterr().out
    assert "Nothing removed" in out
    assert (tmp_path / "MEMORY.md").read_text(encoding="utf-8") == "only entry"


def test_forget_user_target(tmp_path, monkeypatch, capsys):
    _make_store(
        tmp_path, monkeypatch,
        user_entries=["Stale fact about the user"])
    mac._cmd_memory_forget(SimpleNamespace(target="user", entry="Stale fact", yes=True))
    out = capsys.readouterr().out
    assert "Removed one entry from USER.md" in out
    store = memory_tool.load_on_disk_store()
    assert store._entries_for("user") == []