"""Enterprise egress policy: which providers are allowed to leave the machine."""

from __future__ import annotations

import pytest

from formslang import policy


def test_enterprise_mode_defaults_to_off(monkeypatch):
    monkeypatch.delenv(policy.ENTERPRISE_ENV, raising=False)
    assert policy.enterprise_mode() is False


def test_enterprise_mode_reads_the_env_flag(monkeypatch):
    monkeypatch.setenv(policy.ENTERPRISE_ENV, "1")
    assert policy.enterprise_mode() is True
    monkeypatch.setenv(policy.ENTERPRISE_ENV, "0")
    assert policy.enterprise_mode() is False


def test_echo_never_leaves_the_machine():
    assert policy.egress_for("echo") == policy.NONE


def test_the_cli_providers_are_always_cloud():
    assert policy.egress_for("claude_cli") == policy.CLOUD
    assert policy.egress_for("codex_cli") == policy.CLOUD


def test_a_loopback_ollama_is_local():
    assert policy.egress_for("ollama", "http://127.0.0.1:11434") == policy.LOCAL
    assert policy.egress_for("ollama", "http://localhost:11434") == policy.LOCAL


def test_a_remote_ollama_is_not_local():
    assert policy.egress_for("ollama", "http://ollama.example.com:11434") == policy.CLOUD


def test_a_private_network_address_is_local():
    assert policy.egress_for("anthropic", "http://192.168.1.50:8080") == policy.LOCAL
    assert policy.egress_for("anthropic", "http://10.0.4.4:8080") == policy.LOCAL


def test_a_public_hosted_endpoint_is_cloud():
    assert policy.egress_for("anthropic", "https://api.anthropic.com") == policy.CLOUD


def test_a_blank_endpoint_is_not_assumed_local():
    assert policy.egress_for("anthropic", "") == policy.CLOUD


def test_nothing_changes_when_the_mode_is_off(monkeypatch):
    monkeypatch.delenv(policy.ENTERPRISE_ENV, raising=False)
    policy.check("claude_cli")  # would be CLOUD, must not raise while off
    policy.check("anthropic", "https://api.anthropic.com")


def test_a_cloud_provider_is_refused_in_enterprise_mode(monkeypatch):
    monkeypatch.setenv(policy.ENTERPRISE_ENV, "1")
    with pytest.raises(policy.PolicyViolation, match="Enterprise mode"):
        policy.check("claude_cli")


def test_a_local_provider_is_allowed_in_enterprise_mode(monkeypatch):
    monkeypatch.setenv(policy.ENTERPRISE_ENV, "1")
    policy.check("ollama", "http://127.0.0.1:11434")
    policy.check("echo")
