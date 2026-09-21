"""Run Oracle's offline validator against a real ZIP and a deliberately broken copy."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from formslang.apeximport import run_import, sqlcl_version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', type=Path)
    args = parser.parse_args()
    original = args.artifact.resolve(strict=True)
    positive = run_import(original, validate_only=True)
    with tempfile.TemporaryDirectory(prefix='formslang-validation-control-') as directory:
        broken = Path(directory) / 'invalid.apex.zip'
        changed = 0
        with zipfile.ZipFile(original) as source, zipfile.ZipFile(broken, 'w', zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename.endswith('.apx') and b'type: interactiveGrid' in data:
                    data = data.replace(b'type: interactiveGrid', b'type: notARealRegionType')
                    changed += 1
                target.writestr(info, data)
        if not changed:
            raise SystemExit('The synthetic control must contain an interactiveGrid; nothing was modified.')
        negative = run_import(broken, validate_only=True)
    result = {'tool_version': sqlcl_version(), 'mode': 'offline-syntax', 'modified_entries': changed,
              'positive_ok': positive.ok and 'Validation successful.' in positive.stdout,
              'negative_rejected': not negative.ok,
              'positive_exit': positive.exit_code, 'negative_exit': negative.exit_code}
    print(json.dumps(result, indent=2))
    return 0 if result['positive_ok'] and result['negative_rejected'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
