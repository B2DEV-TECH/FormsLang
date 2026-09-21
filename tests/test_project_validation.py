"""Validation evidence is bound to bytes, not architectural approval."""

# ruff: noqa: F811 -- imported pytest fixtures are injected by name

import pytest

from formslang import apeximport
from formslang.project_model import RevisionConflict
from tests.test_project_generation import generation_project, prepared  # noqa: F401


def artifact(service):
    detail = prepared(service)
    return service.generate({**detail['binding'], 'scopes': [detail]})


@pytest.mark.parametrize(('ok', 'output', 'expected'), [
    (True, 'Validation successful.', 'Validated'),
    (False, 'APEXlang Compile Errors: bad region', 'Validation Failed'),
    (True, 'Unknown command: apex validate', 'Validation Failed'),
    (True, '', 'Validation Failed'),
])
def test_validation_requires_positive_tool_verdict(generation_project, monkeypatch, ok, output, expected):
    service = generation_project
    generated = artifact(service)
    calls = []

    def run(path, **kwargs):
        calls.append(kwargs)
        return apeximport.ImportResult(ok, 0, output, '')

    monkeypatch.setattr(apeximport, 'run_import', run)
    monkeypatch.setattr(apeximport, 'sqlcl_version', lambda: 'SQLcl 26.2.2')
    result = service.generation_validate(generated['artifact_id'])
    assert result['status'] == expected
    assert result['artifact_sha256'] == generated['sha256']
    assert result['tool_version'] == 'SQLcl 26.2.2'
    assert calls == [{'validate_only': True}]
    assert service.generation_overview()['artifacts'][0]['validation_status'] == expected


def test_unavailable_tool_is_not_validated(generation_project, monkeypatch):
    generated = artifact(generation_project)
    monkeypatch.setattr(apeximport, 'sqlcl_version', lambda: '')
    result = generation_project.generation_validate(generated['artifact_id'])
    assert result['status'] == 'Not Validated'


def test_edit_during_validation_does_not_publish_success(generation_project, monkeypatch):
    service = generation_project
    generated = artifact(service)
    monkeypatch.setattr(apeximport, 'sqlcl_version', lambda: 'SQLcl 26.2.2')

    def run(path, **kwargs):
        apx = service.access.root / '.formslang/artifacts' / generated['artifact_id'] / 'apexlang/application.apx'
        apx.write_text('edited while SQLcl ran', encoding='utf-8')
        return apeximport.ImportResult(True, 0, 'Validation successful.', '')

    monkeypatch.setattr(apeximport, 'run_import', run)
    with pytest.raises(RevisionConflict):
        service.generation_validate(generated['artifact_id'])
    assert service._store.session.db.execute('SELECT count(*) FROM project_artifact_validation').fetchone()[0] == 0
