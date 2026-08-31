"""Sensitive data found in a unit's source, not sent anywhere yet.

Legacy Forms code carries real client data in plain sight -- a hardcoded
``IDENTIFIED BY`` password, a CPF typed into a test literal, an e-mail left
in a comment. Nothing in the pipeline looked at that content before handing
it to an AI provider. This module does, deterministically, the same way
:mod:`formslang.risk` scores danger and :mod:`formslang.behavior` classifies
change: no model involved, every finding traceable to the text that produced
it.

One rule overrides everything else here: **a finding never carries the
secret itself.** ``Finding.excerpt`` is always :func:`redact`-ed. Nothing in
this module ever returns, logs, or serializes the raw matched value -- the
same guarantee :mod:`formslang.secrets` gives the stored API key, extended
to the client's own source.

Note on the name: :mod:`formslang.secrets` already exists and is the OS
credential store for *our* API key, not a scanner; and :mod:`formslang.apexlang`
already imports the stdlib ``secrets`` module. Hence ``sensitive``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .plsql import strip_comments

VERSION = "sensitive/1"

CREDENTIAL, BR_DOCUMENT, CONTACT, FINANCIAL = (
    "CREDENTIAL",
    "BR_DOCUMENT",
    "CONTACT",
    "FINANCIAL",
)
CATEGORIES = (CREDENTIAL, BR_DOCUMENT, CONTACT, FINANCIAL)

CONFIRMED, LIKELY, POSSIBLE = "CONFIRMED", "LIKELY", "POSSIBLE"
CONFIDENCE_LEVELS = (CONFIRMED, LIKELY, POSSIBLE)

LOW, MEDIUM, HIGH, CRITICAL = "LOW", "MEDIUM", "HIGH", "CRITICAL"
SEVERITY_LEVELS = (LOW, MEDIUM, HIGH, CRITICAL)
_SEVERITY_RANK = {level: i for i, level in enumerate(SEVERITY_LEVELS)}

# --------------------------------------------------------------------------
# Tokenization. Mirrors formslang.plsql's comment/string grammar exactly,
# duplicated rather than imported: plsql's regexes are private to that
# module, and what this module needs -- the *contents* of a comment or
# literal -- is the opposite operation from plsql.strip_noise, which erases
# them. strip_comments() itself (public, line-preserving) is reused as-is
# below instead of being reimplemented.
# --------------------------------------------------------------------------
_LINE_COMMENT = re.compile(r"--[^\n]*")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING = re.compile(r"'(?:[^']|'')*'")


def _blank(m: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", m.group(0))


def _comment_spans(text: str) -> list[tuple[int, int]]:
    spans = [(m.start(), m.end()) for m in _BLOCK_COMMENT.finditer(text)]
    without_blocks = _BLOCK_COMMENT.sub(_blank, text)
    spans += [(m.start(), m.end()) for m in _LINE_COMMENT.finditer(without_blocks)]
    return spans


def _comments(text: str) -> list[tuple[int, str]]:
    out = [
        (text.count("\n", 0, m.start()) + 1, m.group(0))
        for m in _BLOCK_COMMENT.finditer(text)
    ]
    without_blocks = _BLOCK_COMMENT.sub(_blank, text)
    out += [
        (without_blocks.count("\n", 0, m.start()) + 1, m.group(0))
        for m in _LINE_COMMENT.finditer(without_blocks)
    ]
    return out


# --------------------------------------------------------------------------
# Credential patterns -- scanned across the whole body, comments included,
# since a commented-out password is still a password.
# --------------------------------------------------------------------------
_IDENTIFIED_BY = re.compile(
    r"IDENTIFIED\s+BY\s+(?:VALUES\s+)?[\"']?([A-Za-z0-9_!@#$%^&*()\-+=]{3,})[\"']?",
    re.IGNORECASE,
)
_CONNECT_STRING = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_]{2,})/([^'\"@\s/]{3,})@([A-Za-z0-9_.$]{2,})\b"
)
_PASSWORD_ASSIGN = re.compile(
    r"\b(\w*(?:PASSWORD|PASSWD|PWD|SENHA)\w*)\s*:?=\s*'([^']{2,})'",
    re.IGNORECASE,
)
_API_KEY = re.compile(r"\b(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,})\b")
_LONG_TOKEN = re.compile(r"\b([A-Fa-f0-9]{32,})\b")

# --------------------------------------------------------------------------
# BR_DOCUMENT / CONTACT / FINANCIAL patterns -- scanned only inside string
# literals and comments (see scan()). A bare digit run in an arithmetic
# expression is noise, not client data.
# --------------------------------------------------------------------------
_CNPJ_CANDIDATE = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_CPF_CANDIDATE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_CARD_CANDIDATE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_BR = re.compile(r"\b(?:\+?55\s?)?\(?\d{2}\)?[\s.-]?9?\d{4}[\s.-]?\d{4}\b")
_CEP = re.compile(r"\b\d{5}-?\d{3}\b")
_AGENCIA = re.compile(r"\bAG(?:ENCIA|ÊNCIA)?\.?\s*[:.\-]?\s*\d{3,5}\b", re.IGNORECASE)
_CONTA = re.compile(r"\b(?:CONTA|C/C|CC)\s*[:.\-]?\s*\d{4,12}-?\d?\b", re.IGNORECASE)


def _valid_cpf(digits: str) -> bool:
    if len(digits) != 11 or digits == digits[0] * 11:
        return False

    def check_digit(nums: str, weights: range) -> str:
        total = sum(int(n) * w for n, w in zip(nums, weights))
        remainder = total % 11
        return "0" if remainder < 2 else str(11 - remainder)

    d1 = check_digit(digits[:9], range(10, 1, -1))
    d2 = check_digit(digits[:9] + d1, range(11, 1, -1))
    return digits[9] == d1 and digits[10] == d2


def _valid_cnpj(digits: str) -> bool:
    if len(digits) != 14 or digits == digits[0] * 14:
        return False

    def check_digit(nums: str, weights: list[int]) -> str:
        total = sum(int(n) * w for n, w in zip(nums, weights))
        remainder = total % 11
        return "0" if remainder < 2 else str(11 - remainder)

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = check_digit(digits[:12], w1)
    d2 = check_digit(digits[:12] + d1, w2)
    return digits[12] == d1 and digits[13] == d2


def _luhn_valid(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0 and total > 0


def redact(value: str) -> str:
    """A trace a human can eye-match against the source, never the value.

    The first and last character survive; everything between is masked.
    Short values are masked in full. This is the only place a matched
    value is ever touched -- callers must not format it any other way.
    """
    v = (value or "").strip()
    if len(v) <= 4:
        return "*" * len(v)
    return v[0] + "*" * (len(v) - 2) + v[-1]


@dataclass(frozen=True)
class Finding:
    id: str
    category: str
    title: str
    severity: str
    confidence: str
    line: int
    excerpt: str
    detail: str
    in_comment: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "severity": self.severity,
            "confidence": self.confidence,
            "line": self.line,
            "excerpt": self.excerpt,
            "detail": self.detail,
            "in_comment": self.in_comment,
        }


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    level: str = LOW
    version: str = VERSION

    def to_dict(self) -> dict:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "counts": dict(self.counts),
            "level": self.level,
            "version": self.version,
        }


def _finding(
    id_: str,
    category: str,
    title: str,
    severity: str,
    confidence: str,
    line: int,
    raw_value: str,
    *,
    in_comment: bool,
    detail: str,
) -> Finding:
    return Finding(
        id=id_,
        category=category,
        title=title,
        severity=severity,
        confidence=confidence,
        line=line,
        excerpt=redact(raw_value),
        detail=detail,
        in_comment=in_comment,
    )


def _scan_credentials(text: str) -> list[Finding]:
    spans = _comment_spans(text)

    def in_comment(pos: int) -> bool:
        return any(s <= pos < e for s, e in spans)

    out: list[Finding] = []
    for m in _IDENTIFIED_BY.finditer(text):
        out.append(_finding(
            "identified_by", CREDENTIAL, "Hardcoded password (IDENTIFIED BY)",
            HIGH, LIKELY, text.count("\n", 0, m.start()) + 1, m.group(1),
            in_comment=in_comment(m.start()),
            detail="A database user's password is set directly in the source.",
        ))
    for m in _CONNECT_STRING.finditer(text):
        out.append(_finding(
            "connect_string", CREDENTIAL, "Hardcoded connect string (user/password@db)",
            CRITICAL, LIKELY, text.count("\n", 0, m.start()) + 1, m.group(2),
            in_comment=in_comment(m.start()),
            detail="A user, password and database are combined in one literal.",
        ))
    for m in _PASSWORD_ASSIGN.finditer(text):
        out.append(_finding(
            "password_assignment", CREDENTIAL, "Password assigned as a literal",
            HIGH, LIKELY, text.count("\n", 0, m.start()) + 1, m.group(2),
            in_comment=in_comment(m.start()),
            detail="A variable named like a password is set to a literal "
                   "string instead of being read at runtime.",
        ))
    for m in _API_KEY.finditer(text):
        out.append(_finding(
            "api_key_format", CREDENTIAL, "API key in a recognised provider format",
            CRITICAL, CONFIRMED, text.count("\n", 0, m.start()) + 1, m.group(1),
            in_comment=in_comment(m.start()),
            detail="Matches a known API key format (OpenAI, AWS, GitHub, or similar).",
        ))
    for m in _LONG_TOKEN.finditer(text):
        out.append(_finding(
            "long_token", CREDENTIAL, "Long hexadecimal token",
            MEDIUM, POSSIBLE, text.count("\n", 0, m.start()) + 1, m.group(1),
            in_comment=in_comment(m.start()),
            detail="A long hexadecimal string, possibly a key, hash or token.",
        ))
    return out


def _scan_value(value: str, line: int, *, in_comment: bool) -> list[Finding]:
    out: list[Finding] = []
    claimed: list[tuple[int, int]] = []

    def claim(start: int, end: int) -> bool:
        for s, e in claimed:
            if start < e and s < end:
                return False
        claimed.append((start, end))
        return True

    for m in _CNPJ_CANDIDATE.finditer(value):
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) == 14 and _valid_cnpj(digits) and claim(m.start(), m.end()):
            out.append(_finding(
                "cnpj", BR_DOCUMENT, "CNPJ (validated)", HIGH, CONFIRMED, line,
                m.group(0), in_comment=in_comment,
                detail="A CNPJ with a valid check digit was found.",
            ))
    for m in _CPF_CANDIDATE.finditer(value):
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) == 11 and _valid_cpf(digits) and claim(m.start(), m.end()):
            out.append(_finding(
                "cpf", BR_DOCUMENT, "CPF (validated)", HIGH, CONFIRMED, line,
                m.group(0), in_comment=in_comment,
                detail="A CPF with a valid check digit was found.",
            ))
    for m in _CARD_CANDIDATE.finditer(value):
        digits = re.sub(r"[ \-]", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn_valid(digits) and claim(m.start(), m.end()):
            out.append(_finding(
                "credit_card", FINANCIAL, "Card number (Luhn-valid)", CRITICAL,
                CONFIRMED, line, m.group(0), in_comment=in_comment,
                detail="A digit sequence that passes the card-number check digit.",
            ))
    for m in _EMAIL.finditer(value):
        if claim(m.start(), m.end()):
            out.append(_finding(
                "email", CONTACT, "E-mail address", LOW, LIKELY, line,
                m.group(0), in_comment=in_comment,
                detail="An e-mail address in a literal or a comment.",
            ))
    for m in _PHONE_BR.finditer(value):
        if claim(m.start(), m.end()):
            out.append(_finding(
                "phone_br", CONTACT, "Phone number", LOW, LIKELY, line,
                m.group(0), in_comment=in_comment,
                detail="A Brazilian phone number pattern.",
            ))
    for m in _CEP.finditer(value):
        if claim(m.start(), m.end()):
            out.append(_finding(
                "cep", CONTACT, "Postal code (CEP)", LOW, POSSIBLE, line,
                m.group(0), in_comment=in_comment,
                detail="An 8-digit pattern matching a Brazilian postal code.",
            ))
    for m in _AGENCIA.finditer(value):
        if claim(m.start(), m.end()):
            out.append(_finding(
                "bank_agency", FINANCIAL, "Bank agency number", MEDIUM, LIKELY,
                line, m.group(0), in_comment=in_comment,
                detail="A bank agency number next to its keyword.",
            ))
    for m in _CONTA.finditer(value):
        if claim(m.start(), m.end()):
            out.append(_finding(
                "bank_account", FINANCIAL, "Bank account number", MEDIUM, LIKELY,
                line, m.group(0), in_comment=in_comment,
                detail="A bank account number next to its keyword.",
            ))
    return out


def _summarize(findings: list[Finding]) -> ScanResult:
    counts = {c: 0 for c in CATEGORIES}
    level = LOW
    for f in findings:
        counts[f.category] = counts.get(f.category, 0) + 1
        if _SEVERITY_RANK[f.severity] > _SEVERITY_RANK[level]:
            level = f.severity
    ordered = sorted(findings, key=lambda f: (-_SEVERITY_RANK[f.severity], f.line))
    return ScanResult(findings=ordered, counts=counts, level=level)


def scan(source: str) -> ScanResult:
    """Deterministic scan of ``source`` for credentials and BR/PII/financial data.

    Same input always yields the same output. No finding's excerpt or
    detail ever contains the raw matched text -- see :func:`redact`.
    """
    text = source or ""
    findings: list[Finding] = list(_scan_credentials(text))

    code_only = strip_comments(text)
    for m in _STRING.finditer(code_only):
        line = code_only.count("\n", 0, m.start()) + 1
        inner = m.group(0)[1:-1].replace("''", "'")
        findings += _scan_value(inner, line, in_comment=False)

    for line, comment_text in _comments(text):
        findings += _scan_value(comment_text, line, in_comment=True)

    return _summarize(findings)


def explain() -> dict:
    """Mirrors :func:`formslang.risk.explain` -- the rules, for display."""
    return {
        "version": VERSION,
        "categories": {
            CREDENTIAL: "Hardcoded passwords, connect strings and API keys. "
                        "Matched anywhere in the body, comments included.",
            BR_DOCUMENT: "CPF/CNPJ validated by check digit -- an unchecked "
                         "digit string is not reported.",
            CONTACT: "E-mail, phone and postal code, inside a string literal "
                     "or a comment only.",
            FINANCIAL: "Card numbers validated by Luhn; bank agency/account "
                       "matched by keyword. Inside a string literal or a "
                       "comment only.",
        },
        "scope": "BR_DOCUMENT, CONTACT and FINANCIAL are scanned only inside "
                 "string literals and comments. CREDENTIAL is scanned "
                 "everywhere, since a hardcoded password is not less real "
                 "for sitting outside a string.",
        "not_scanned": [
            "identifier and column names",
            "numeric literals outside a string or a comment",
        ],
    }
