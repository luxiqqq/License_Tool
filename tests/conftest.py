'''
NON SERVE PIU PERCHE' HO INSERITO IL FILE .ini
from pathlib import Path
import sys

# Inserisce la root del progetto all'inizio di sys.path così "import app.*" funziona
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

# Questo file serve per poter scrivere solo pytest nella root del progetto.
# python -m pytest tests -q (potevo usare anche solo questo comando)

'''
import unittest

# TODO: Questo file serve per le configurazioni globali e Mock condivisi tra test
# ESEMPIO MINIMALE
import pytest
import os
from unittest.mock import MagicMock


# 1. Mock delle variabili d'ambiente per TUTTI i test
@pytest.fixture(scope="session", autouse=True)
def mock_env_vars():
    """Impedisce ai test di cercare vere API Key o file .env"""
    with unittest.mock.patch.dict(os.environ, {
        "GITHUB_CLIENT_ID": "fake-id",
        "GITHUB_CLIENT_SECRET": "fake-secret",
        "OLLAMA_HOST": "http://fake-ollama",
        "ENCRYPTION_KEY": "fake-key-must-be-32-bytes-long-!!" # Deve essere 32 byte se usi fernet
    }):
        yield

# 2. Mock della Matrice di Compatibilità (per non dipendere dal JSON su disco)
@pytest.fixture
def mock_matrix_data():
    return {
        "MIT": {
            "MIT": "yes",
            "GPL-3.0": "no",
            "APACHE-2.0": "yes"
        },
        "GPL-3.0": {
            "MIT": "yes", # GPL può includere MIT
            "GPL-3.0": "yes"
        }
    }