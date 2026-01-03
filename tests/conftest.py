"""
test: tests/conftest.py

Configurazione condivisa e fixtures per la suite di test pytest.

Questo modulo fornisce:
- Helper di utilità (es. `_msg_matches` per asserzioni di stringhe flessibili).
- Mocking delle variabili d'ambiente globali per isolare i test dalla configurazione locale.
- Patch di default per dipendenze di servizi complessi (come le matrici di compatibilità).
- Oggetti mock riutilizzabili per i nodi di parsing SPDX (`MockNode`, `MockLeaf`, ecc.).
"""

import pytest
import os
from unittest.mock import patch


# ==============================================================================
# HELPER DI UTILITÀ
# ==============================================================================

def msg_matches_helper(s: str, en: str, it: str) -> bool:
    """
    Controlla se una stringa contiene la variante inglese o italiana di un messaggio.
    Utile per asserire messaggi di errore che potrebbero essere localizzati.

    Args:
        s (str): La stringa da controllare (può essere None).
        en (str): La sottostringa inglese attesa.
        it (str): La sottostringa italiana attesa.

    Returns:
        bool: True se `en` o `it` si trova in `s`, False altrimenti.
    """
    if s is None:
        return False
    return (en in s) or (it in s)


@pytest.fixture
def _msg_matches():
    """
    Fixture che espone la funzione `msg_matches_helper`.
    """
    return msg_matches_helper


# ==============================================================================
# MOCK E PATCH GLOBALI
# ==============================================================================


@pytest.fixture(scope="session", autouse=True)
def mock_env_vars():
    """
    Fixture a scope session che mocka le variabili d'ambiente.
    Garantisce che i test vengano eseguiti con una configurazione coerente e isolata
    e previene l'uso accidentale di valori reali dal file .env.
    """
    with patch.dict(os.environ, {
        "GITHUB_CLIENT_ID": "test_id",
        "GITHUB_CLIENT_SECRET": "test_secret",
        "CALLBACK_URL": "http://localhost:8000/callback",
        "OLLAMA_HOST": "http://mock-ollama:11434",
        "OLLAMA_URL": "http://mock-ollama:11434",
        "OLLAMA_CODING_MODEL": "test-model",
        "OLLAMA_GENERAL_MODEL": "test-model",
        "OLLAMA_HOST_VERSION": "http://mock-ollama:11434/version",
        "OLLAMA_HOST_TAGS": "http://mock-ollama:11434/tags",
        "SCANCODE_BIN": "scancode",
        "CLONE_BASE_DIR": "./test_clones",
        "OUTPUT_BASE_DIR": "./test_output"
    }):
        yield


@pytest.fixture(autouse=True)
def patch_config_variables(tmp_path):
    """
    Fixture autouse che patcha le variabili di configurazione in `app.utility.config`
    e nei moduli dipendenti.

    Questo è necessario perché `config.py` carica le variabili d'ambiente al momento
    dell'importazione. Questa fixture garantisce che tutti i moduli utilizzino
    directory temporanee di test create tramite `tmp_path`.

    Args:
        tmp_path: Fixture pytest che fornisce una directory temporanea unica.

    Yields:
        str: Il percorso alla directory di clonazione temporanea.
    """
    test_clone_dir = str(tmp_path / "test_clones")
    test_output_dir = str(tmp_path / "test_output")

    # Crea le directory di test
    os.makedirs(test_clone_dir, exist_ok=True)
    os.makedirs(test_output_dir, exist_ok=True)

    # Patcha i moduli che importano CLONE_BASE_DIR direttamente
    with patch("app.utility.config.CLONE_BASE_DIR", test_clone_dir), \
            patch("app.utility.config.OUTPUT_BASE_DIR", test_output_dir), \
            patch("app.services.analysis_workflow.CLONE_BASE_DIR", test_clone_dir), \
            patch("app.services.llm.suggestion.CLONE_BASE_DIR", test_clone_dir), \
            patch("app.services.github.github_client.CLONE_BASE_DIR", test_clone_dir), \
            patch("app.services.downloader.download_service.CLONE_BASE_DIR", test_clone_dir):
        yield test_clone_dir


@pytest.fixture(autouse=True)
def _default_patches(monkeypatch, complex_matrix_data):
    """
    Fixture autouse che applica mock di default per funzioni di servizio comuni.

    Mocka `normalize_symbol` come un semplice pass-through/strip e
    `get_matrix` per restituire i dati della fixture di test. Questo riduce il boilerplate
    nei singoli test unitari.

    Args:
        monkeypatch: Fixture pytest per il patching.
        complex_matrix_data: Fixture che fornisce la matrice di compatibilità mock.
    """
    # Normalize di default: identity/strip
    normalize_mock = lambda s: s.strip() if isinstance(s, str) else s

    monkeypatch.setattr("app.services.compatibility.evaluator.normalize_symbol", normalize_mock)
    monkeypatch.setattr("app.services.compatibility.checker.normalize_symbol", normalize_mock)
    monkeypatch.setattr("app.services.compatibility.parser_spdx.normalize_symbol", normalize_mock)

    # get_matrix di default: restituisce i dati della fixture
    matrix_mock = lambda: complex_matrix_data

    monkeypatch.setattr("app.services.compatibility.evaluator.get_matrix", matrix_mock)
    monkeypatch.setattr("app.services.compatibility.checker.get_matrix", matrix_mock)

    yield


# ==============================================================================
# FIXTURE DATI
# ==============================================================================

@pytest.fixture
def complex_matrix_data():
    """
    Fornisce una matrice di compatibilità mock per testare la logica di valutazione.
    Copre scenari 'yes', 'no' e 'conditional'.

    Returns:
        dict: Un dizionario che rappresenta la matrice di compatibilità.
    """
    return {
        "MIT": {
            "MIT": "yes",
            "Apache-2.0": "yes",
            "GPL-3.0": "no",  # Permissivo vs Copyleft Forte
            "GPL-3.0-or-later": "no",
            "LGPL-2.1": "conditional",
            "Proprietary": "no"
        },
        "GPL-3.0": {
            "MIT": "yes",  # GPL può includere MIT
            "GPL-3.0": "yes",
            "Apache-2.0": "no",  # Simulazione incompatibilità V2 vs V3
            "Proprietary": "no"
        }
    }


# ==============================================================================
# CLASSI MOCK NODE (PARSER SPDX)
# ==============================================================================

@pytest.fixture
def MockNode():
    """Restituisce la classe Node dal modulo parser."""
    from app.services.compatibility import parser_spdx
    return parser_spdx.Node


@pytest.fixture
def MockLeaf():
    """Restituisce la classe Leaf dal modulo parser."""
    from app.services.compatibility import parser_spdx
    return parser_spdx.Leaf


@pytest.fixture
def MockAnd():
    """Restituisce la classe And dal modulo parser."""
    from app.services.compatibility import parser_spdx
    return parser_spdx.And


@pytest.fixture
def MockOr():
    """Restituisce la classe Or dal modulo parser."""
    from app.services.compatibility import parser_spdx
    return parser_spdx.Or

