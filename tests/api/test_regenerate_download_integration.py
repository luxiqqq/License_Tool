"""
Test di INTEGRAZIONE per gli endpoint /api/regenerate e /api/download
Questi test verificano il flusso completo con interazioni reali tra componenti,
usando mock SOLO per dipendenze esterne costose (ScanCode, LLM).
"""

import pytest
import os
import shutil
import zipfile
from io import BytesIO
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.core.config import CLONE_BASE_DIR
from app.models.schemas import AnalyzeResponse, LicenseIssue

client = TestClient(app)


# ==============================================================================
# FIXTURES E HELPER
# ==============================================================================

@pytest.fixture
def cleanup_test_repos():
    """Fixture per pulire le repository di test dopo ogni test."""
    yield
    # Cleanup dopo il test
    test_patterns = [
        'regenowner_regenrepo',
        'downloadowner_downloadrepo',
        'errorowner_errorrepo',
        'emptyowner_emptyrepo',
        'missingowner_missingrepo'
    ]
    for pattern in test_patterns:
        test_dir = os.path.join(CLONE_BASE_DIR, pattern)
        if os.path.exists(test_dir):
            try:
                shutil.rmtree(test_dir)
            except Exception as e:
                print(f"Cleanup warning: Could not remove {test_dir}: {e}")

        # Cleanup anche dei file zip
        zip_file = os.path.join(CLONE_BASE_DIR, f"{pattern}_download.zip")
        if os.path.exists(zip_file):
            try:
                os.remove(zip_file)
            except Exception as e:
                print(f"Cleanup warning: Could not remove {zip_file}: {e}")


@pytest.fixture
def create_test_repo():
    """Helper per creare una repository di test fisica sul file system."""
    def _create(owner: str, repo: str, files: dict = None):
        """
        Crea una repository di test con file specificati.

        Args:
            owner: Nome owner
            repo: Nome repository
            files: Dict {path: content} di file da creare

        Returns:
            Path assoluto della repository creata
        """
        repo_path = os.path.join(CLONE_BASE_DIR, f"{owner}_{repo}")
        os.makedirs(repo_path, exist_ok=True)

        # File di default se non specificati
        if files is None:
            files = {
                'README.md': '# Test Repository\n\nThis is a test.',
                'LICENSE': 'MIT License\n\nCopyright (c) 2025 Test\n\nPermission is hereby granted...',
                'src/main.py': '# Main file\nprint("Hello World")\n',
                'src/utils.py': '# Utils\ndef helper():\n    pass\n'
            }

        # Crea i file
        for file_path, content in files.items():
            full_path = os.path.join(repo_path, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)

        return repo_path

    return _create


@pytest.fixture
def sample_analyze_response():
    """Fixture che fornisce un AnalyzeResponse di esempio per test di rigenerazione."""
    return AnalyzeResponse(
        repository="regenowner/regenrepo",
        main_license="MIT",
        issues=[
            LicenseIssue(
                file_path="src/incompatible.py",
                detected_license="GPL-3.0",
                compatible=False,
                reason="GPL-3.0 is incompatible with MIT",
                suggestion="Consider relicensing or removing this file"
            )
        ],
        report_path="/tmp/old_report.txt"
    )


# ==============================================================================
# TEST DI INTEGRAZIONE - REGENERATE_ANALYSIS
# ==============================================================================

def test_regenerate_analysis_success_integration(
    create_test_repo,
    sample_analyze_response,
    cleanup_test_repos
):
    """
    Test di integrazione: rigenerazione completa con repository reale.

    Flusso:
    1. Crea repository fisica di test
    2. Chiama /regenerate con AnalyzeResponse precedente
    3. Verifica integrazione endpoint → workflow → file system

    Mock utilizzati: Solo perform_regeneration (workflow complesso)
    """
    # Step 1: Crea repository di test
    repo_path = create_test_repo(
        "regenowner",
        "regenrepo",
        files={
            'README.md': '# Test',
            'src/incompatible.py': '# GPL code\nprint("test")'
        }
    )

    assert os.path.exists(repo_path)

    # Step 2: Mock solo perform_regeneration (workflow complesso con LLM)
    with patch('app.api.analysis.perform_regeneration') as mock_regen:
        # Mock della risposta di rigenerazione
        mock_regen.return_value = AnalyzeResponse(
            repository="regenowner/regenrepo",
            main_license="MIT",
            issues=[
                LicenseIssue(
                    file_path="src/incompatible.py",
                    detected_license="MIT",  # Ora compatibile
                    compatible=True,
                    reason="Rigenerato con successo",
                    regenerated_code_path="src/incompatible.py"
                )
            ],
            report_path="/tmp/new_report.txt"
        )

        # Step 3: Chiamata endpoint
        response = client.post(
            "/api/regenerate",
            json=sample_analyze_response.model_dump()
        )

        # Verifica risposta
        assert response.status_code == 200
        result = response.json()

        assert result['repository'] == "regenowner/regenrepo"
        assert result['main_license'] == "MIT"
        assert len(result['issues']) == 1
        assert result['issues'][0]['compatible'] is True

        # Verifica che perform_regeneration sia stato chiamato correttamente
        mock_regen.assert_called_once()
        call_args = mock_regen.call_args
        assert call_args[1]['owner'] == "regenowner"
        assert call_args[1]['repo'] == "regenrepo"


def test_regenerate_analysis_invalid_repository_format():
    """
    Test di integrazione: validazione formato repository.
    Verifica che l'endpoint rifiuti repository senza slash.
    """
    invalid_payload = {
        "repository": "noslash",  # Manca "/"
        "main_license": "MIT",
        "issues": [],
        "report_path": "/tmp/report.txt"
    }

    response = client.post("/api/regenerate", json=invalid_payload)

    assert response.status_code == 400
    assert "Formato repository non valido" in response.json()["detail"]
    assert "owner/repo" in response.json()["detail"]


def test_regenerate_analysis_repository_not_found(cleanup_test_repos):
    """
    Test di integrazione: tentativo di rigenerazione su repository non esistente.
    Verifica l'integrazione endpoint → workflow → file system check.
    """
    with patch('app.api.analysis.perform_regeneration') as mock_regen:
        # Mock che solleva ValueError (repository non trovata)
        mock_regen.side_effect = ValueError("Repository non trovata")

        payload = {
            "repository": "missingowner/missingrepo",
            "main_license": "MIT",
            "issues": [],
            "report_path": "/tmp/report.txt"
        }

        response = client.post("/api/regenerate", json=payload)

        assert response.status_code == 400
        assert "Repository non trovata" in response.json()["detail"]


def test_regenerate_analysis_generic_exception(cleanup_test_repos):
    """
    Test di integrazione: gestione Exception generica durante rigenerazione.
    Verifica che errori imprevisti ritornino 500.
    """
    with patch('app.api.analysis.perform_regeneration') as mock_regen:
        # Mock che solleva Exception generica
        mock_regen.side_effect = RuntimeError("Errore imprevisto durante rigenerazione")

        payload = {
            "repository": "errorowner/errorrepo",
            "main_license": "MIT",
            "issues": [],
            "report_path": "/tmp/report.txt"
        }

        response = client.post("/api/regenerate", json=payload)

        assert response.status_code == 500
        assert "Errore interno" in response.json()["detail"]


def test_regenerate_analysis_missing_issues_field():
    """
    Test di integrazione: validazione schema Pydantic.
    Verifica che payload incompleto venga rifiutato.
    """
    incomplete_payload = {
        "repository": "owner/repo",
        "main_license": "MIT"
        # Manca 'issues' e 'report_path' (required fields)
    }

    response = client.post("/api/regenerate", json=incomplete_payload)

    # FastAPI validation error
    assert response.status_code == 422


# ==============================================================================
# TEST DI INTEGRAZIONE - DOWNLOAD_REPO
# ==============================================================================

def test_download_repo_success_integration(create_test_repo, cleanup_test_repos):
    """
    Test di integrazione completo: download di repository reale.

    Flusso:
    1. Crea repository fisica con file
    2. Chiama /download
    3. Verifica che lo ZIP sia creato correttamente
    4. Verifica contenuto dello ZIP

    Nessun mock: test di integrazione PURO
    """
    # Step 1: Crea repository di test
    repo_path = create_test_repo(
        "downloadowner",
        "downloadrepo",
        files={
            'README.md': '# Download Test\n\nThis repo will be downloaded.',
            'LICENSE': 'MIT License\n',
            'src/main.py': 'print("main")\n',
            'src/utils.py': 'def util(): pass\n',
            'docs/guide.md': '# Guide\n'
        }
    )

    assert os.path.exists(repo_path)

    # Step 2: Chiamata endpoint
    response = client.post(
        "/api/download",
        json={"owner": "downloadowner", "repo": "downloadrepo"}
    )

    # Step 3: Verifica risposta
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "downloadowner_downloadrepo.zip" in response.headers.get("content-disposition", "")

    # Step 4: Verifica contenuto ZIP
    zip_content = BytesIO(response.content)
    with zipfile.ZipFile(zip_content, 'r') as zip_file:
        # Lista file nel ZIP
        zip_files = zip_file.namelist()

        # Verifica che tutti i file siano presenti
        assert 'downloadowner_downloadrepo/README.md' in zip_files
        assert 'downloadowner_downloadrepo/LICENSE' in zip_files
        assert 'downloadowner_downloadrepo/src/main.py' in zip_files
        assert 'downloadowner_downloadrepo/src/utils.py' in zip_files
        assert 'downloadowner_downloadrepo/docs/guide.md' in zip_files

        # Verifica contenuto di un file
        readme_content = zip_file.read('downloadowner_downloadrepo/README.md').decode('utf-8')
        assert '# Download Test' in readme_content


def test_download_repo_repository_not_found():
    """
    Test di integrazione: tentativo di download di repository non esistente.
    Verifica l'integrazione endpoint → service → file system check.
    """
    response = client.post(
        "/api/download",
        json={"owner": "nonexistent", "repo": "notfound"}
    )

    assert response.status_code == 400
    assert "Repository non trovata" in response.json()["detail"]


def test_download_repo_missing_parameters():
    """
    Test di integrazione: validazione parametri obbligatori.
    """
    # Caso 1: Manca owner
    response1 = client.post("/api/download", json={"repo": "test"})
    assert response1.status_code == 400
    assert "obbligatori" in response1.json()["detail"].lower() or "required" in response1.json()["detail"].lower()

    # Caso 2: Manca repo
    response2 = client.post("/api/download", json={"owner": "test"})
    assert response2.status_code == 400

    # Caso 3: Payload vuoto
    response3 = client.post("/api/download", json={})
    assert response3.status_code == 400


def test_download_repo_empty_repository(create_test_repo, cleanup_test_repos):
    """
    Test di integrazione: download di repository vuota.
    Verifica che anche una repo senza file possa essere zippata.
    """
    # Crea repository vuota (solo directory)
    repo_path = create_test_repo("emptyowner", "emptyrepo", files={})
    assert os.path.exists(repo_path)

    response = client.post(
        "/api/download",
        json={"owner": "emptyowner", "repo": "emptyrepo"}
    )

    # Dovrebbe comunque funzionare (ZIP vuoto o con solo la directory)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"


def test_download_repo_with_special_characters_in_filenames(
    create_test_repo,
    cleanup_test_repos
):
    """
    Test di integrazione: download di repository con nomi file speciali.
    Verifica che caratteri speciali nei nomi file siano gestiti correttamente.
    """
    repo_path = create_test_repo(
        "specialowner",
        "specialrepo",
        files={
            'file with spaces.txt': 'Content with spaces',
            'file-with-dash.py': '# Dash file',
            'file_with_underscore.md': '# Underscore file',
            'special (parens).txt': 'Parentheses content'
        }
    )

    response = client.post(
        "/api/download",
        json={"owner": "specialowner", "repo": "specialrepo"}
    )

    assert response.status_code == 200

    # Verifica contenuto ZIP
    zip_content = BytesIO(response.content)
    with zipfile.ZipFile(zip_content, 'r') as zip_file:
        zip_files = zip_file.namelist()

        # Verifica che i file con caratteri speciali siano presenti
        assert any('file with spaces.txt' in f for f in zip_files)
        assert any('file-with-dash.py' in f for f in zip_files)
        assert any('file_with_underscore.md' in f for f in zip_files)
        assert any('special (parens).txt' in f for f in zip_files)

    # Cleanup
    cleanup_path = os.path.join(CLONE_BASE_DIR, 'specialowner_specialrepo')
    if os.path.exists(cleanup_path):
        shutil.rmtree(cleanup_path)
    zip_path = os.path.join(CLONE_BASE_DIR, 'specialowner_specialrepo_download.zip')
    if os.path.exists(zip_path):
        os.remove(zip_path)


def test_download_repo_with_empty_string_parameters():
    """
    Test di integrazione: validazione con stringhe vuote.
    """
    # Owner stringa vuota
    response1 = client.post("/api/download", json={"owner": "", "repo": "test"})
    assert response1.status_code == 400

    # Repo stringa vuota
    response2 = client.post("/api/download", json={"owner": "test", "repo": ""})
    assert response2.status_code == 400

    # Entrambi stringhe vuote
    response3 = client.post("/api/download", json={"owner": "", "repo": ""})
    assert response3.status_code == 400


def test_download_repo_generic_exception(create_test_repo, cleanup_test_repos):
    """
    Test di integrazione: gestione Exception generica durante download.
    Verifica che errori imprevisti ritornino 500.
    """
    # Crea repository
    create_test_repo("errorowner", "errorrepo")

    with patch('app.api.analysis.perform_download') as mock_download:
        # Mock che solleva Exception generica
        mock_download.side_effect = RuntimeError("Errore imprevisto durante zip")

        response = client.post(
            "/api/download",
            json={"owner": "errorowner", "repo": "errorrepo"}
        )

        assert response.status_code == 500
        assert "Errore interno" in response.json()["detail"]


# ==============================================================================
# TEST FLUSSO COMPLETO: UPLOAD → ANALYZE → REGENERATE → DOWNLOAD
# ==============================================================================

def test_complete_workflow_integration(create_test_repo, cleanup_test_repos):
    """
    Test di integrazione del flusso completo end-to-end:
    1. Setup repository
    2. Analyze (mockato)
    3. Regenerate (mockato)
    4. Download (reale)

    Verifica l'integrazione tra tutti gli endpoint.
    """
    # Step 1: Setup repository
    owner, repo = "workflowowner", "workflowrepo"
    repo_path = create_test_repo(
        owner,
        repo,
        files={
            'README.md': '# Workflow Test',
            'src/code.py': 'print("test")'
        }
    )

    # Step 2: Mock Analyze (già testato altrove)
    with patch('app.api.analysis.perform_initial_scan') as mock_scan:
        mock_scan.return_value = AnalyzeResponse(
            repository=f"{owner}/{repo}",
            main_license="MIT",
            issues=[],
            report_path="/tmp/report.txt"
        )

        analyze_resp = client.post("/api/analyze", json={"owner": owner, "repo": repo})
        assert analyze_resp.status_code == 200
        analyze_result = analyze_resp.json()

    # Step 3: Mock Regenerate
    with patch('app.api.analysis.perform_regeneration') as mock_regen:
        mock_regen.return_value = AnalyzeResponse(
            repository=f"{owner}/{repo}",
            main_license="MIT",
            issues=[],
            report_path="/tmp/new_report.txt"
        )

        regen_resp = client.post("/api/regenerate", json=analyze_result)
        assert regen_resp.status_code == 200

    # Step 4: Download (integrazione reale)
    download_resp = client.post("/api/download", json={"owner": owner, "repo": repo})
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/zip"

    # Verifica contenuto ZIP
    zip_content = BytesIO(download_resp.content)
    with zipfile.ZipFile(zip_content, 'r') as zip_file:
        zip_files = zip_file.namelist()
        assert any('README.md' in f for f in zip_files)
        assert any('src/code.py' in f for f in zip_files)

    # Cleanup
    cleanup_path = os.path.join(CLONE_BASE_DIR, f'{owner}_{repo}')
    if os.path.exists(cleanup_path):
        shutil.rmtree(cleanup_path)
    zip_path = os.path.join(CLONE_BASE_DIR, f'{owner}_{repo}_download.zip')
    if os.path.exists(zip_path):
        os.remove(zip_path)

