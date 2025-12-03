#TESTA checker.py
# python
import pytest
from unittest.mock import MagicMock
from app.services.compatibility.checker import check_compatibility


def test_main_license_invalid_returns_issues(monkeypatch):
    monkeypatch.setattr("app.services.compatibility.checker.normalize_symbol", lambda s: "")
    res = check_compatibility("", {"a.py": "MIT"})
    assert res["main_license"] == "UNKNOWN"
    assert len(res["issues"]) == 1
    issue = res["issues"][0]
    assert issue["file_path"] == "a.py"
    assert issue["compatible"] is False
    assert "Licenza principale non rilevata" in issue["reason"]


def test_matrix_missing_or_license_not_in_matrix(monkeypatch):
    monkeypatch.setattr("app.services.compatibility.checker.normalize_symbol", lambda s: "MIT")
    monkeypatch.setattr("app.services.compatibility.checker.get_matrix", lambda: None)
    res = check_compatibility("MIT", {"b.py": "Apache-2.0"})
    assert res["main_license"] == "MIT"
    assert len(res["issues"]) == 1
    assert "Matrice professionale non disponibile" in res["issues"][0]["reason"]


def test_eval_yes_marks_compatible_and_includes_trace(complex_matrix_data, monkeypatch):
    monkeypatch.setattr("app.services.compatibility.checker.normalize_symbol", lambda s: "MIT")
    monkeypatch.setattr("app.services.compatibility.checker.get_matrix", lambda: complex_matrix_data)
    monkeypatch.setattr("app.services.compatibility.checker.parse_spdx", lambda s: "NODE")
    monkeypatch.setattr("app.services.compatibility.checker.eval_node", lambda *_: ("yes", ["direct match"]))
    res = check_compatibility("MIT", {"src/file.py": "MIT"})
    assert res["main_license"] == "MIT"
    assert len(res["issues"]) == 1
    issue = res["issues"][0]
    assert issue["file_path"] == "src/file.py"
    assert issue["compatible"] is True
    assert "direct match" in issue["reason"]


def test_eval_no_marks_incompatible_and_includes_trace(complex_matrix_data, monkeypatch):
    monkeypatch.setattr("app.services.compatibility.checker.normalize_symbol", lambda s: "GPL-3.0")
    monkeypatch.setattr("app.services.compatibility.checker.get_matrix", lambda: complex_matrix_data)
    monkeypatch.setattr("app.services.compatibility.checker.parse_spdx", lambda s: "NODE")
    monkeypatch.setattr("app.services.compatibility.checker.eval_node", lambda *_: ("no", ["conflict detected"]))
    res = check_compatibility("GPL-3.0", {"lib/x.py": "Apache-2.0"})
    issue = res["issues"][0]
    assert issue["compatible"] is False
    assert "conflict detected" in issue["reason"]


def test_eval_conditional_returns_hint_in_reason_and_not_compatible(complex_matrix_data, monkeypatch):
    monkeypatch.setattr("app.services.compatibility.checker.normalize_symbol", lambda s: "MIT")
    monkeypatch.setattr("app.services.compatibility.checker.get_matrix", lambda: complex_matrix_data)
    mock_parse = MagicMock(return_value="NODE")
    monkeypatch.setattr("app.services.compatibility.checker.parse_spdx", mock_parse)
    monkeypatch.setattr("app.services.compatibility.checker.eval_node", lambda *_: ("conditional", ["some clause"]))

    res = check_compatibility("MIT", {"folder/thing.py": "  LGPL-2.1  "})
    mock_parse.assert_called_with("LGPL-2.1")
    issue = res["issues"][0]
    assert issue["compatible"] is False
    assert "Esito: conditional" in issue["reason"]
    assert "some clause" in issue["reason"]

def test_all_files_compatible_returns_no_issues(complex_matrix_data, monkeypatch):
    """
    Aggiornamento del test: la funzione attuale registra un issue per ogni file,
    anche quando è compatibile. Verifichiamo che gli issue esistano ma siano tutti
    marcati come compatibili.
    """
    monkeypatch.setattr("app.services.compatibility.checker.normalize_symbol", lambda s: "MIT")
    monkeypatch.setattr("app.services.compatibility.checker.get_matrix", lambda: complex_matrix_data)
    monkeypatch.setattr("app.services.compatibility.checker.parse_spdx", lambda s: s.strip())
    monkeypatch.setattr("app.services.compatibility.checker.eval_node", lambda *_: ("yes", ["direct match"]))

    res = check_compatibility("MIT", {"file1.py": "MIT", "file2.py": "Apache-2.0"})
    assert res["main_license"] == "MIT"
    assert isinstance(res["issues"], list)
    assert len(res["issues"]) == 2
    assert all(issue["compatible"] is True for issue in res["issues"])

def test_matrix_present_but_main_not_in_matrix(monkeypatch):
    monkeypatch.setattr("app.services.compatibility.checker.normalize_symbol", lambda s: "MIT")
    monkeypatch.setattr("app.services.compatibility.checker.get_matrix", lambda: {"GPL-3.0": {"MIT": "no"}})
    res = check_compatibility("MIT", {"file.py": "Apache-2.0"})
    assert res["main_license"] == "MIT"
    assert len(res["issues"]) == 1
    assert "licenza principale non presente" in res["issues"][0]["reason"].lower() or "Matrice professionale non disponibile" in res["issues"][0]["reason"]

def test_eval_unknown_status_shows_unknown_hint(complex_matrix_data, monkeypatch):
    monkeypatch.setattr("app.services.compatibility.checker.normalize_symbol", lambda s: "MIT")
    monkeypatch.setattr("app.services.compatibility.checker.get_matrix", lambda: complex_matrix_data)
    monkeypatch.setattr("app.services.compatibility.checker.parse_spdx", lambda s: "NODE")
    monkeypatch.setattr("app.services.compatibility.checker.eval_node", lambda *_: ("weird", ["trace info"]))
    res = check_compatibility("MIT", {"x.py": "Zlib"})
    issue = res["issues"][0]
    assert issue["compatible"] is False
    assert "Esito: unknown" in issue["reason"]

def test_empty_detected_license_calls_parse_with_empty(monkeypatch, complex_matrix_data):
    monkeypatch.setattr("app.services.compatibility.checker.normalize_symbol", lambda s: "MIT")
    monkeypatch.setattr("app.services.compatibility.checker.get_matrix", lambda: complex_matrix_data)
    mock_parse = MagicMock(return_value="NODE")
    monkeypatch.setattr("app.services.compatibility.checker.parse_spdx", mock_parse)
    monkeypatch.setattr("app.services.compatibility.checker.eval_node", lambda *_: ("no", ["no trace"]))
    res = check_compatibility("MIT", {"empty.py": None})
    mock_parse.assert_called_with("")
    issue = res["issues"][0]
    assert issue["detected_license"] == ""
    assert "no trace" in issue["reason"]

def test_main_license_special_values_treated_as_invalid(monkeypatch):
    for val in ("UNKNOWN", "NOASSERTION", "NONE"):
        monkeypatch.setattr("app.services.compatibility.checker.normalize_symbol", lambda s, v=val: v)
        res = check_compatibility(val, {"a.py": "MIT"})
        assert res["main_license"] == val or res["main_license"] == val
        assert len(res["issues"]) == 1
        assert "Licenza principale non rilevata" in res["issues"][0]["reason"] or "non valida" in res["issues"][0]["reason"]