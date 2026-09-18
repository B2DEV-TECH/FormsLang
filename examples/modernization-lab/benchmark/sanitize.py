"""Deterministic sanitizer and leakage validator for FormsLang modernization benchmark.

Removes answer-key hints (LOM-MOD-###, benchmark class/risk annotations, ground truth references)
while strictly preserving XML structure, attributes, and executable PL/SQL logic.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

# Patterns indicating answer-key leakage
LEAKAGE_PATTERNS = [
    re.compile(r"LOM-MOD-\d+", re.IGNORECASE),
    re.compile(r"\bground[-_ ]truth\b", re.IGNORECASE),
    re.compile(r"\bexpected[-_ ]decision\b", re.IGNORECASE),
    re.compile(r"\bexpected[-_ ]action\b", re.IGNORECASE),
    re.compile(
        r"\b(?:CONVERT|PRESERVE|REFACTOR|MOVE_TO_PLSQL_API|REPLACE_WITH_APEX_NATIVE|MANUAL_REVIEW|DROP)"
        r"\s*,\s*(?:LOW|MEDIUM|HIGH|CRITICAL)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bcategory\s+[A-F]\b", re.IGNORECASE),
]


def sanitize_text(text: str) -> str:
    """Deterministically sanitize source text to remove benchmark answer keys."""

    # 1. XML comment blocks referencing LOM-MOD or ground-truth
    def replace_xml_comment(m: re.Match[str]) -> str:
        content = m.group(0)
        if re.search(r"LOM-MOD|ground-truth|expected", content, re.IGNORECASE):
            return "<!-- Forms2XML module definition -->"
        return content

    text = re.sub(r"<!--[\s\S]*?-->", replace_xml_comment, text)

    # 2. Tooltip and Comment attributes containing benchmark references
    def sanitize_attribute(m: re.Match[str]) -> str:
        attr_name = m.group(1)
        val = m.group(2)
        # Remove parenthesized LOM-MOD references, e.g. (LOM-MOD-013) or (LOM-MOD-041/LOM-MOD-042)
        val = re.sub(r"\s*\([–-]?\s*LOM-MOD-[^)]*\)", "", val)
        # Remove '-- see LOM-MOD-###', ', see LOM-MOD-###', 'see LOM-MOD-###'
        val = re.sub(r"\s*--\s*see\s+LOM-MOD-\d+\.?", "", val)
        val = re.sub(r"\s*,\s*see\s+LOM-MOD-\d+\.?", "", val)
        val = re.sub(r"\s*see\s+LOM-MOD-\d+\.?", "", val)
        val = re.sub(r"LOM-MOD-\d+", "", val)
        val = val.strip()
        return f'{attr_name}="{val}"'

    text = re.sub(r'(Tooltip|Comment)="([^"]*)"', sanitize_attribute, text)

    # 3. PL/SQL code in TriggerText or ProgramUnitText attributes
    def sanitize_code_attribute(m: re.Match[str]) -> str:
        attr_name = m.group(1)
        raw_body = m.group(2)
        # Determine newline separator entity used in the attribute
        sep = "&amp;#10;" if "&amp;#10;" in raw_body else ("&#10;" if "&#10;" in raw_body else "\n")
        lines = raw_body.split(sep)
        cleaned_lines: list[str] = []
        skip_comment_block = False

        for line in lines:
            stripped = line.strip()
            # If line is a comment introducing a benchmark case (e.g. "-- LOM-MOD-013 (CONVERT, category A): ...")
            if stripped.startswith("--") and re.search(r"LOM-MOD-\d+", line, re.IGNORECASE):
                # Check if it has benchmark annotations
                if any(k in line for k in ("(", "CONVERT", "PRESERVE", "REFACTOR", "MOVE_TO_PLSQL_API",
                                           "REPLACE_WITH_APEX_NATIVE", "MANUAL_REVIEW", "DROP",
                                           "risk", "category", "risk):", "example):")):
                    skip_comment_block = True
                    continue
                else:
                    # In-line reference in architectural comment - remove LOM-MOD token only
                    line = re.sub(r"\s*\([–-]?\s*LOM-MOD-[^)]*\)", "", line)
                    line = re.sub(r"LOM-MOD-\d+", "", line)
                    cleaned_lines.append(line)
                    continue

            if skip_comment_block:
                # Continuation of benchmark commentary block
                if stripped.startswith("--") and not stripped.startswith("--  IF") and not stripped.startswith("--  SELECT"):
                    # Check if this comment discusses benchmark or is blank comment
                    if any(w in line.lower() for w in ("category", "risk", "ground-truth", "apex", "idiom",
                                                       "centralized", "duplication", "re-implement",
                                                       "contrast", "identical", "straightforward")) or stripped == "--":
                        continue
                    else:
                        continue
                else:
                    skip_comment_block = False

            # Remove any stray inline LOM-MOD references in comments
            if "LOM-MOD" in line:
                line = re.sub(r"\s*\([–-]?\s*LOM-MOD-[^)]*\)", "", line)
                line = re.sub(r"LOM-MOD-\d+", "", line)

            cleaned_lines.append(line)

        return f'{attr_name}="{sep.join(cleaned_lines)}"'

    text = re.sub(r'(TriggerText)="([^"]*)"', sanitize_code_attribute, text)
    text = re.sub(r'(ProgramUnitText)="([^"]*)"', sanitize_code_attribute, text)

    return text


def sanitize_file(input_path: Path, output_path: Path) -> str:
    """Sanitize one file deterministically, write output, and return SHA256."""
    input_text = input_path.read_text(encoding="utf-8")
    sanitized = sanitize_text(input_text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(sanitized, encoding="utf-8", newline="\n")
    return hashlib.sha256(sanitized.encode("utf-8")).hexdigest()


def detect_leakage_in_text(text: str) -> list[str]:
    """Return list of leakage descriptions if answer keys are detected."""
    leaks = []
    for pattern in LEAKAGE_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            leaks.append(f"Pattern '{pattern.pattern}' matched: {matches[:5]}")
    return leaks


def verify_no_leakage(directory: Path) -> None:
    """Scan all files in directory; raise RuntimeError if any leak is detected."""
    leaks_found: dict[str, list[str]] = {}
    for p in sorted(directory.rglob("*")):
        if p.is_file() and p.suffix.lower() in {".xml", ".sql", ".pks", ".pkb", ".json"}:
            content = p.read_text(encoding="utf-8")
            leaks = detect_leakage_in_text(content)
            if leaks:
                leaks_found[p.name] = leaks

    if leaks_found:
        msg_lines = ["Answer-key leakage detected in sanitized inputs:"]
        for fname, leaks in leaks_found.items():
            msg_lines.append(f"  {fname}: {leaks}")
        raise RuntimeError("\n".join(msg_lines))
