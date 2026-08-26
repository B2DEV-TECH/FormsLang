"""Provider layer: configuration, and never leaking a key."""

from __future__ import annotations

import json

import pytest

from formslang import ai


def test_offline_provider_is_the_default(monkeypatch):
    monkeypatch.delenv("FORMSLANG_AI_PROVIDER", raising=False)
    p = ai.provider_from_env()
    assert p.type_id == "echo"


def test_env_selects_the_provider(monkeypatch):
    monkeypatch.setenv("FORMSLANG_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("FORMSLANG_AI_MODEL", "some-model")
    monkeypatch.setenv("FORMSLANG_AI_KEY", "sk-secret")
    p = ai.provider_from_env()
    assert p.type_id == "anthropic"
    assert p.model == "some-model"


def test_describe_never_shows_the_key(monkeypatch):
    monkeypatch.setenv("FORMSLANG_AI_PROVIDER", "openai")
    monkeypatch.setenv("FORMSLANG_AI_KEY", "sk-do-not-print-me")
    assert "do-not-print-me" not in ai.provider_from_env().describe()


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="unknown AI provider"):
        ai.build_provider("mainframe")


def test_offline_answer_is_valid_but_admits_it_did_nothing():
    data = json.loads(ai.EchoProvider().complete([ai.Message("user", "x")]))
    assert data["confidence"] == 0.0
    assert "placeholder" in " ".join(data["notes"]).lower()
    assert "no ai provider" in data["code"].lower()


def test_azure_url_uses_the_deployment():
    p = ai.build_provider(
        "azure_openai", model="gpt-4o", base_url="https://x.openai.azure.com",
        deployment="my-deploy", api_version="2024-08-01-preview",
    )
    url = p._url()
    assert "/openai/deployments/my-deploy/chat/completions" in url
    assert "api-version=2024-08-01-preview" in url


def test_check_provider_reports_failure_as_data():
    class Broken(ai.Provider):
        type_id = "broken"

        def complete(self, messages, max_tokens=0):
            raise ai.ProviderError("401 unauthorized")

    ok, detail = ai.check_provider(Broken())
    assert ok is False
    assert "401" in detail
