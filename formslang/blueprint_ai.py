"""Optional advisory explanation of an already-built, anonymized finding."""

from __future__ import annotations

from collections import Counter

from . import blueprint, policy
from .ai import Message, ProviderError


def review(payload, entity, provider):
    finding = next((f for f in payload["findings"] if f["entity"] == entity), None)
    if finding is None:
        raise ValueError("unknown Blueprint finding")
    policy.check(provider.type_id, provider.base_url)
    nodes = {n["id"]: n for n in payload["entities"]}
    edges = [e for e in payload["edges"] if e["source"] == entity]
    # Deliberate allowlist. No source names, paths, literals, comments, human
    # decisions, evidence excerpts, credentials or complete sessions are sent.
    sanitized = {
        "unit": "reviewed_component", "type": nodes[entity]["type"],
        "facts": {"observed_relationship_counts": dict(Counter(e["type"] for e in edges))},
        "dependencies": [{"alias": f"dependency_{i}", "type": nodes[nid]["type"]}
                         for i, nid in enumerate(sorted({e["target"] for e in edges}))],
        "classification": finding["classification"],
        "recommendation": finding["recommendation"],
        "unresolved_questions": ["Runtime equivalence, callee bodies and target constraints require human investigation."],
    }
    messages = [Message("system", "You are an advisory modernization reviewer. Explain alternatives using only the structured evidence. Distinguish facts, inferences, assumptions and unknowns. Do not invent dependencies, approve work, declare safety, calculate official scores or assert functional parity. Every response is an unapproved proposal. You cannot change the Blueprint."),
                Message("user", blueprint.canonical(sanitized))]
    try:
        answer = provider.complete(messages, max_tokens=2048)
    except ProviderError:
        raise ValueError("AI provider failed; no Blueprint data or decisions were changed") from None
    return {"status": "PROPOSAL", "requires_human_review": True,
            "text": str(answer)[:16000], "provider": provider.type_id,
            "sent": sanitized, "changes_applied": False}
