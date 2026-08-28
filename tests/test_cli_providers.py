"""Driving an agent CLI instead of an API key.

These providers spawn a coding agent, so the tests that matter are the ones
about containment: the prompt must not reach the command line, the agent must
not start inside the source tree, and a missing binary must say how to fix
it rather than blow up somewhere deep.

No test here needs the binaries installed -- ``subprocess.run`` is replaced.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from formslang import ai
from formslang.ai import (
    ClaudeCliProvider,
    CodexCliProvider,
    Message,
    ProviderError,
    build_provider,
    provider_catalog,
)


@pytest.fixture()
def fake_cli(monkeypatch):
    """Pretend both CLIs exist, and record how they were called."""
    monkeypatch.setattr(ai.shutil, "which", lambda binary: f"C:/fake/{binary}.exe")
    calls = []

    def run(argv, **kw):
        calls.append({"argv": argv, **kw})
        answer = kw.pop("_answer", "")
        return subprocess.CompletedProcess(argv, 0, stdout=answer, stderr="")

    monkeypatch.setattr(ai.subprocess, "run", run)
    return calls


MESSAGES = [Message("system", "You convert Forms to APEX."), Message("user", "PRE-INSERT body")]


# -- containment ---------------------------------------------------------


def test_the_prompt_travels_on_stdin_not_on_the_command_line(fake_cli, monkeypatch):
    """Windows caps a command line at ~32k; a trigger body can exceed it.

    It is also the difference between analyzed code in a process listing and
    analyzed code in a pipe.
    """
    monkeypatch.setattr(ai.subprocess, "run", lambda argv, **kw: _answer(fake_cli, argv, kw, '{"result":"ok"}'))
    ClaudeCliProvider().complete([Message("user", "SECRET_BODY")])
    call = fake_cli[-1]
    assert call["input"] == "SECRET_BODY"
    assert not any("SECRET_BODY" in part for part in call["argv"])


def test_the_agent_starts_in_an_empty_scratch_folder(fake_cli, monkeypatch, tmp_path):
    """These are coding agents: whatever folder they start in, they will read.

    Starting them in the project would hand them CLAUDE.md and a user's
    source tree to wander through.
    """
    seen = {}

    def run(argv, **kw):
        # Look while the folder still exists: it is deleted on the way out.
        seen["cwd"] = Path(kw["cwd"])
        seen["contents"] = sorted(p.name for p in Path(kw["cwd"]).iterdir())
        return _answer(fake_cli, argv, kw, '{"result":"ok"}')

    monkeypatch.setattr(ai.subprocess, "run", run)
    monkeypatch.chdir(tmp_path)
    ClaudeCliProvider().complete(MESSAGES)

    assert seen["cwd"].is_absolute()
    assert seen["cwd"] != Path.cwd()
    assert seen["contents"] == []
    assert not seen["cwd"].exists()  # and it does not outlive the call


def test_the_shell_is_never_involved(fake_cli, monkeypatch):
    monkeypatch.setattr(ai.subprocess, "run", lambda argv, **kw: _answer(fake_cli, argv, kw, '{"result":"ok"}'))
    ClaudeCliProvider().complete(MESSAGES)
    assert fake_cli[-1]["shell"] is False


def test_a_missing_binary_says_how_to_fix_it(monkeypatch):
    monkeypatch.setattr(ai.shutil, "which", lambda binary: None)
    with pytest.raises(ProviderError) as e:
        ClaudeCliProvider().complete(MESSAGES)
    assert "not on PATH" in str(e.value)
    assert "claude-code" in str(e.value)


def test_a_hung_agent_becomes_a_provider_error(monkeypatch):
    monkeypatch.setattr(ai.shutil, "which", lambda binary: "C:/fake/claude.exe")

    def hang(argv, **kw):
        raise subprocess.TimeoutExpired(argv, kw["timeout"])

    monkeypatch.setattr(ai.subprocess, "run", hang)
    p = ClaudeCliProvider()
    p.timeout = 5.0
    with pytest.raises(ProviderError, match="did not answer within"):
        p.complete(MESSAGES)


# -- Claude Code CLI -----------------------------------------------------


def test_claude_runs_headless_and_leaves_no_session_behind(fake_cli, monkeypatch):
    monkeypatch.setattr(ai.subprocess, "run", lambda argv, **kw: _answer(fake_cli, argv, kw, '{"result":"ok"}'))
    ClaudeCliProvider(model="opus").complete(MESSAGES)
    argv = fake_cli[-1]["argv"]
    assert "-p" in argv                                  # print mode, not a REPL
    assert argv[argv.index("--output-format") + 1] == "json"
    assert "--no-session-persistence" in argv            # analyzed code stays out of ~/.claude
    assert "--strict-mcp-config" in argv                 # the user's MCP servers stay out of this
    assert argv[argv.index("--model") + 1] == "opus"
    assert argv[argv.index("--system-prompt") + 1] == MESSAGES[0].content


def test_claude_answers_from_the_json_envelope(fake_cli, monkeypatch):
    payload = json.dumps({"type": "result", "is_error": False, "result": "-- converted"})
    monkeypatch.setattr(ai.subprocess, "run", lambda argv, **kw: _answer(fake_cli, argv, kw, payload))
    assert ClaudeCliProvider().complete(MESSAGES) == "-- converted"


def test_claude_reporting_its_own_error_is_not_treated_as_an_answer(fake_cli, monkeypatch):
    """Exit code 0 with is_error true: the JSON is the only place it shows."""
    payload = json.dumps({"is_error": True, "result": "Credit balance too low"})
    monkeypatch.setattr(ai.subprocess, "run", lambda argv, **kw: _answer(fake_cli, argv, kw, payload))
    with pytest.raises(ProviderError, match="Credit balance"):
        ClaudeCliProvider().complete(MESSAGES)


def test_claude_speaking_prose_instead_of_json_is_an_error(fake_cli, monkeypatch):
    monkeypatch.setattr(ai.subprocess, "run", lambda argv, **kw: _answer(fake_cli, argv, kw, "Welcome to Claude!"))
    with pytest.raises(ProviderError, match="non-JSON"):
        ClaudeCliProvider().complete(MESSAGES)


# -- Codex CLI -----------------------------------------------------------


def test_codex_writes_its_answer_to_a_file_because_stdout_is_noisy(fake_cli, monkeypatch):
    """Codex narrates to stdout; only ``-o`` carries the final message."""

    def run(argv, **kw):
        fake_cli.append({"argv": argv, **kw})
        out = Path(argv[argv.index("-o") + 1])
        out.write_text("BEGIN :P0_CREATED := SYSDATE; END;", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, stdout="tokens used: 812", stderr="")

    monkeypatch.setattr(ai.subprocess, "run", run)
    assert CodexCliProvider().complete(MESSAGES) == "BEGIN :P0_CREATED := SYSDATE; END;"
    argv = fake_cli[-1]["argv"]
    assert argv[1] == "exec"
    assert "--ephemeral" in argv                    # no session file holding analyzed code
    assert argv[argv.index("-s") + 1] == "read-only"
    assert argv[-1] == "-"                          # prompt on stdin
    assert Path(argv[argv.index("-o") + 1]).parent == Path(fake_cli[-1]["cwd"])


def test_codex_carries_the_doctrine_in_the_prompt_since_it_has_no_system_flag(fake_cli, monkeypatch):
    monkeypatch.setattr(ai.subprocess, "run", lambda argv, **kw: _answer(fake_cli, argv, kw, "", write="x"))
    CodexCliProvider().complete(MESSAGES)
    call = fake_cli[-1]
    assert "--system-prompt" not in call["argv"]
    assert call["input"].startswith("You convert Forms to APEX.")
    assert "PRE-INSERT body" in call["input"]


def test_codex_saying_nothing_is_an_error_not_an_empty_conversion(fake_cli, monkeypatch):
    monkeypatch.setattr(ai.subprocess, "run", lambda argv, **kw: _answer(fake_cli, argv, kw, "stream disconnected"))
    with pytest.raises(ProviderError, match="no final message"):
        CodexCliProvider().complete(MESSAGES)


# -- the catalog the picker is built from --------------------------------


def test_the_catalog_marks_which_clis_this_machine_actually_has(monkeypatch):
    monkeypatch.setattr(ai.shutil, "which", lambda binary: "C:/fake/claude.exe" if binary == "claude" else None)
    monkeypatch.delenv("FORMSLANG_AI_KEY", raising=False)
    catalog = {p["id"]: p for p in provider_catalog()}

    assert catalog["claude_cli"]["kind"] == "cli"
    assert catalog["claude_cli"]["available"] is True
    assert catalog["claude_cli"]["needs_key"] is False   # it rides the subscription
    assert catalog["codex_cli"]["available"] is False
    assert "npm i -g" in catalog["codex_cli"]["hint"]

    assert catalog["anthropic"]["kind"] == "http"
    assert catalog["anthropic"]["needs_key"] is True
    # No key in the environment: the picker says so up front, instead of a
    # blind 401 after the code body was already sent to the API.
    assert catalog["anthropic"]["available"] is False
    assert "FORMSLANG_AI_KEY" in catalog["anthropic"]["hint"]
    assert catalog["ollama"]["needs_key"] is False       # local server, no key

    monkeypatch.setenv("FORMSLANG_AI_KEY", "k")
    catalog = {p["id"]: p for p in provider_catalog()}
    assert catalog["anthropic"]["available"] is True


def test_every_catalogued_provider_can_actually_be_built():
    for entry in provider_catalog():
        provider = build_provider(entry["id"], model=entry["default_model"])
        assert provider.type_id == entry["id"]
        assert provider.describe()


# -- helper --------------------------------------------------------------


def _answer(calls, argv, kw, stdout, write=""):
    """Record the call and hand back a finished process."""
    calls.append({"argv": argv, **kw})
    if write and "-o" in argv:
        Path(argv[argv.index("-o") + 1]).write_text(write, encoding="utf-8")
    return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")
