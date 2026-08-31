"""The sensitive-data scanner. Deterministic, and never echoes what it finds."""

from __future__ import annotations

import json

from formslang import sensitive

PASSWORD_IN_CODE = """
PROCEDURE do_login IS
BEGIN
  GRANT CONNECT TO scott IDENTIFIED BY tiger123;
  v_password := 'hunter2222';
END;
"""

PASSWORD_IN_COMMENT = """
BEGIN
  -- v_password := 'oldSecret1';
  NULL;
END;
"""

CONNECT_STRING = """
BEGIN
  LOGON('scott/tiger123@orcl');
END;
"""

VALID_CPF = "529.982.247-25"
INVALID_CPF = "111.111.111-11"
VALID_CNPJ = "11.222.333/0001-81"
VALID_CARD = "4111111111111111"
INVALID_CARD = "1234567890123456"

BR_DOCUMENT_BODY = f"""
BEGIN
  :GLOBAL.CPF := '{VALID_CPF}';
  :GLOBAL.BOGUS_CPF := '{INVALID_CPF}';
  :GLOBAL.CNPJ := '{VALID_CNPJ}';
END;
"""

FINANCIAL_BODY = f"""
BEGIN
  :GLOBAL.CARD := '{VALID_CARD}';
  :GLOBAL.BOGUS_CARD := '{INVALID_CARD}';
  -- conta corrente do cliente: CONTA 123456-7
END;
"""

CONTACT_BODY = """
BEGIN
  :GLOBAL.EMAIL := 'cliente@empresa.com.br';
  -- contato: (11) 98765-4321
END;
"""

SAFE = """
BEGIN
  :ORDERS.TOTAL := :ORDERS.QTY * :ORDERS.PRICE;
  v_count := v_count + 1234567890123;
END;
"""


def test_the_same_source_always_scans_the_same():
    a = sensitive.scan(BR_DOCUMENT_BODY)
    b = sensitive.scan(BR_DOCUMENT_BODY)
    assert a.to_dict() == b.to_dict()


def test_a_finding_never_carries_the_secret_itself():
    secrets = ["tiger123", "hunter2222", VALID_CPF, VALID_CNPJ, VALID_CARD]
    blob = json.dumps(sensitive.scan(
        PASSWORD_IN_CODE + BR_DOCUMENT_BODY + FINANCIAL_BODY
    ).to_dict())
    for secret in secrets:
        assert secret not in blob


def test_a_password_identified_by_is_found():
    result = sensitive.scan(PASSWORD_IN_CODE)
    ids = {f.id for f in result.findings}
    assert "identified_by" in ids
    assert "password_assignment" in ids
    assert all(f.category == sensitive.CREDENTIAL for f in result.findings)


def test_a_password_in_a_comment_is_still_found():
    result = sensitive.scan(PASSWORD_IN_COMMENT)
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.id == "password_assignment"
    assert finding.in_comment is True


def test_a_connect_string_is_found_as_critical():
    result = sensitive.scan(CONNECT_STRING)
    finding = next(f for f in result.findings if f.id == "connect_string")
    assert finding.severity == sensitive.CRITICAL


def test_a_valid_cpf_is_confirmed_and_an_invalid_one_is_not_reported():
    result = sensitive.scan(BR_DOCUMENT_BODY)
    cpf_findings = [f for f in result.findings if f.id == "cpf"]
    assert len(cpf_findings) == 1
    assert cpf_findings[0].confidence == sensitive.CONFIRMED


def test_a_valid_cnpj_is_confirmed():
    result = sensitive.scan(BR_DOCUMENT_BODY)
    cnpj_findings = [f for f in result.findings if f.id == "cnpj"]
    assert len(cnpj_findings) == 1
    assert cnpj_findings[0].confidence == sensitive.CONFIRMED


def test_a_luhn_valid_card_is_confirmed_and_an_invalid_one_is_not_reported():
    result = sensitive.scan(FINANCIAL_BODY)
    card_findings = [f for f in result.findings if f.id == "credit_card"]
    assert len(card_findings) == 1
    assert card_findings[0].confidence == sensitive.CONFIRMED


def test_a_bank_account_keyword_in_a_comment_is_found():
    result = sensitive.scan(FINANCIAL_BODY)
    finding = next(f for f in result.findings if f.id == "bank_account")
    assert finding.in_comment is True


def test_contact_data_is_found_in_literals_and_comments():
    result = sensitive.scan(CONTACT_BODY)
    ids = {f.id: f for f in result.findings}
    assert "email" in ids
    assert ids["email"].in_comment is False
    assert "phone_br" in ids
    assert ids["phone_br"].in_comment is True


def test_plain_arithmetic_reports_nothing():
    result = sensitive.scan(SAFE)
    assert result.findings == []
    assert result.level == sensitive.LOW


def test_findings_are_sorted_by_severity_then_line():
    result = sensitive.scan(PASSWORD_IN_CODE + BR_DOCUMENT_BODY)
    ranks = [sensitive._SEVERITY_RANK[f.severity] for f in result.findings]
    assert ranks == sorted(ranks, reverse=True)


def test_the_scan_level_is_the_highest_finding_severity():
    assert sensitive.scan(CONTACT_BODY).level == sensitive.LOW
    assert sensitive.scan(PASSWORD_IN_CODE).level == sensitive.HIGH
    assert sensitive.scan(CONNECT_STRING).level == sensitive.CRITICAL


def test_redact_never_returns_the_full_value():
    assert sensitive.redact("hunter2222") != "hunter2222"
    assert "hunter2222" not in sensitive.redact("hunter2222")
    assert sensitive.redact("") == ""
    assert sensitive.redact("ab") == "**"


def test_counts_match_the_findings_by_category():
    result = sensitive.scan(PASSWORD_IN_CODE + BR_DOCUMENT_BODY + FINANCIAL_BODY + CONTACT_BODY)
    for category in sensitive.CATEGORIES:
        assert result.counts[category] == len(
            [f for f in result.findings if f.category == category]
        )


def test_explain_documents_every_category():
    doc = sensitive.explain()
    assert set(doc["categories"]) == set(sensitive.CATEGORIES)
    assert doc["version"] == sensitive.VERSION
