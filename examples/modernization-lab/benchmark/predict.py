"""Prediction runner using the current FormsLang engine.

Strictly isolated from benchmark ground-truth:
- Reads ONLY sanitized Forms2XML files.
- Never imports ground truth or evaluator helpers.
- Uses official FormsLang parser and blueprint/analysis stack.
- Produces comprehensive raw analysis artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from formslang import __version__ as formslang_version
from formslang.blueprint import ENGINE_VERSION as BLUEPRINT_ENGINE_VERSION
from formslang.blueprint import build as build_blueprint
from formslang.parser import parse_xml


def run_prediction(sanitized_xml_dir: Path, raw_output_path: Path) -> dict[str, Any]:
    """Execute FormsLang engine over sanitized XML and save raw-analysis.json."""
    if not sanitized_xml_dir.exists():
        raise FileNotFoundError(f"Sanitized XML directory does not exist: {sanitized_xml_dir}")

    xml_files = sorted(sanitized_xml_dir.glob("*.xml"))
    if not xml_files:
        raise ValueError(f"No XML files found in {sanitized_xml_dir}")

    # Parse XML fixtures using the real FormsLang parser
    modules = []
    source_keys = []
    for p in xml_files:
        mod = parse_xml(p)
        mod.source_path = p.name
        modules.append(mod)
        source_keys.append(p.name)

    # Run the comprehensive FormsLang blueprint pipeline
    blueprint_payload = build_blueprint(
        modules,
        title="LOM Modernization Lab",
        source_keys=source_keys,
    )

    raw_output = {
        "engine": "FormsLang",
        "forms_lang_version": formslang_version,
        "blueprint_engine_version": BLUEPRINT_ENGINE_VERSION,
        "sources": source_keys,
        "blueprint": blueprint_payload,
    }

    raw_output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_output_path.write_text(
        json.dumps(raw_output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return raw_output
