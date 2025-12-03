import pytest
from unittest.mock import patch, MagicMock
from app.services.compatibility import evaluator


# ------------------------------------------------------------------
# 1. Mocking delle Classi del Parser
# ------------------------------------------------------------------
# Poiché evaluator.py fa controlli isinstance(), dobbiamo creare delle
# classi dummy e patchare quelle originali nel modulo evaluator.

class MockNode:
    pass


class MockLeaf(MockNode):
    def __init__(self, value):
        self.value = value


class MockAnd(MockNode):
    def __init__(self, left, right):
        self.left = left
        self.right = right


class MockOr(MockNode):
    def __init__(self, left, right):
        self.left = left
        self.right = right


# ------------------------------------------------------------------
# 2. Fixtures (Dati di prova)
# ------------------------------------------------------------------

@pytest.fixture
def mock_matrix_data():
    """
    Simula una matrice di compatibilità semplificata.
    Row = Main License, Col = Dep License
    """
    return {
        "MIT": {
            "MIT": "yes",
            "Apache-2.0": "yes",
            "GPL-2.0": "no"
        },
        "GPL-3.0": {
            "MIT": "yes",
            "GPL-3.0": "yes",
            "Apache-2.0": "yes",  # Compatibile in una direzione
            "Proprietary": "no"
        },
        "Apache-2.0": {
            "GPL-3.0": "no",  # Apache non è compatibile verso GPL (esempio)
            "MIT": "yes"
        }
    }


@pytest.fixture(autouse=True)
def setup_mocks(mock_matrix_data):
    """
    Applica automaticamente i patch prima di ogni test.
    Sostituisce get_matrix, normalize_symbol e le classi Node.
    """
    with patch("app.services.compatibility.evaluator.get_matrix", return_value=mock_matrix_data), \
            patch("app.services.compatibility.evaluator.normalize_symbol", side_effect=lambda x: x.strip()), \
            patch("app.services.compatibility.evaluator.Leaf", MockLeaf), \
            patch("app.services.compatibility.evaluator.And", MockAnd), \
            patch("app.services.compatibility.evaluator.Or", MockOr):
        yield


# ------------------------------------------------------------------
# 3. Test Unitari
# ------------------------------------------------------------------

def test_lookup_status_found():
    """Testa che il lookup trovi valori corretti nella matrice."""
    assert evaluator._lookup_status("MIT", "Apache-2.0") == "yes"
    assert evaluator._lookup_status("MIT", "GPL-2.0") == "no"


def test_lookup_status_unknown():
    """Testa licenze non presenti nella matrice."""
    assert evaluator._lookup_status("MIT", "Unknown-License") == "unknown"
    assert evaluator._lookup_status("NonExistentMain", "MIT") == "unknown"


def test_eval_node_none():
    """Testa input None."""
    status, trace = evaluator.eval_node("MIT", None)
    assert status == "unknown"
    assert "Expression missed" in trace[0]


def test_eval_leaf_simple():
    """Testa un singolo nodo foglia (Leaf)."""
    node = MockLeaf("Apache-2.0")

    # Caso: MIT include Apache-2.0 -> yes
    status, trace = evaluator.eval_node("MIT", node)
    assert status == "yes"
    assert "Apache-2.0 → yes for MIT" in trace[0]


def test_eval_leaf_with_exception():
    """Testa la gestione della clausola 'WITH'."""
    # Simuliamo un caso "GPL-3.0 WITH Classpath-exception"
    node = MockLeaf("GPL-3.0 WITH Classpath-exception")

    # La logica del codice splitta su " WITH " e controlla la base (GPL-3.0)
    # Nel nostro mock matrix, GPL-3.0 è compatibile con GPL-3.0
    status, trace = evaluator.eval_node("GPL-3.0", node)

    assert status == "yes"
    assert "exception requires manual verification" not in trace[0]
    assert "Exception found" in trace[0]


def test_eval_or_logic_optimistic():
    """
    Testa operatore OR.
    (GPL-2.0 OR Apache-2.0) contro MIT.
    GPL-2.0 è NO per MIT.
    Apache-2.0 è YES per MIT.
    Risultato atteso: YES (perché basta uno yes).
    """
    node = MockOr(MockLeaf("GPL-2.0"), MockLeaf("Apache-2.0"))

    status, trace = evaluator.eval_node("MIT", node)
    assert status == "yes"
    assert "OR ⇒ yes" in trace[-1]


def test_eval_and_logic_conservative():
    """
    Testa operatore AND.
    (MIT AND GPL-2.0) contro MIT.
    MIT -> YES
    GPL-2.0 -> NO
    Risultato atteso: NO (perché basta un no per invalidare AND).
    """
    node = MockAnd(MockLeaf("MIT"), MockLeaf("GPL-2.0"))

    status, trace = evaluator.eval_node("MIT", node)
    assert status == "no"
    assert "AND ⇒ no" in trace[-2]  # trace[-1] sono i cross checks


def test_and_cross_compatibility_check():
    """
    Testa la logica avanzata di 'Cross Check' nei nodi AND.
    Se ho (A AND B), il codice controlla se A è compatibile con B e viceversa.
    """
    # Usiamo: Apache-2.0 AND GPL-3.0
    # Apache verso GPL-3.0 -> NO (nel mock data)
    node = MockAnd(MockLeaf("Apache-2.0"), MockLeaf("GPL-3.0"))

    # Valutiamo contro una main license "GPL-3.0"
    # Apache per GPL-3.0 è YES.
    # GPL-3.0 per GPL-3.0 è YES.
    # Quindi il risultato combinato sarebbe YES.
    # MA vogliamo vedere se nei trace compaiono i controlli incrociati.

    status, trace = evaluator.eval_node("GPL-3.0", node)

    assert status == "yes"

    # Verifica che il trace contenga i controlli incrociati
    trace_str = " ".join(trace)
    assert "Cross compatibility check: Apache-2.0 with GPL-3.0" in trace_str
    assert "Cross compatibility check: GPL-3.0 with Apache-2.0" in trace_str


def test_combine_helpers():
    """Test diretti sulle funzioni helper di combinazione."""
    # AND Logic
    assert evaluator._combine_and("yes", "yes") == "yes"
    assert evaluator._combine_and("yes", "no") == "no"
    assert evaluator._combine_and("conditional", "yes") == "conditional"

    # OR Logic
    assert evaluator._combine_or("yes", "no") == "yes"
    assert evaluator._combine_or("no", "no") == "no"
    assert evaluator._combine_or("conditional", "no") == "conditional"


def test_lookup_status_empty_matrix():
    """Testa il caso in cui get_matrix restituisce None o dizionario vuoto."""
    with patch("app.services.compatibility.evaluator.get_matrix", return_value=None):
        assert evaluator._lookup_status("MIT", "MIT") == "unknown"

    with patch("app.services.compatibility.evaluator.get_matrix", return_value={}):
        assert evaluator._lookup_status("MIT", "MIT") == "unknown"


def test_eval_leaf_with_exception_fail():
    """
    Testa una licenza con eccezione ('WITH') dove la licenza base è INCOMPATIBILE ('no').
    Esercita il ramo 'if status != yes'.
    """
    # Proprietary -> NO per GPL-3.0 nel nostro mock
    node = MockLeaf("Proprietary WITH Some-Exception")

    status, trace = evaluator.eval_node("GPL-3.0", node)

    assert status == "no"
    # Verifica che il messaggio sia quello specifico per il fallimento
    assert "exception requires manual verification" in trace[0]


def test_combine_conditional_logic():
    """Testa i casi che restituiscono 'conditional' nei combinatori."""
    # AND: basta un 'conditional' (se l'altro è yes) per rendere tutto conditional
    assert evaluator._combine_and("yes", "conditional") == "conditional"
    assert evaluator._combine_and("conditional", "conditional") == "conditional"

    # OR: basta un 'conditional' (se l'altro è no) per rendere tutto conditional
    assert evaluator._combine_or("no", "conditional") == "conditional"
    assert evaluator._combine_or("conditional", "conditional") == "conditional"


def test_eval_node_unrecognized_type():
    """Testa il passaggio di un oggetto che non è né Leaf, né And, né Or."""

    class UnknownNode(MockNode):
        pass

    status, trace = evaluator.eval_node("MIT", UnknownNode())
    assert status == "unknown"
    assert "Node not recognized" in trace[0]


def test_and_nested_leaves_collection():
    """
    Testa che _collect_leaves funzioni ricorsivamente.
    Struttura: (MIT OR Apache-2.0) AND GPL-3.0
    Main License: Proprietary (che è 'no' per tutti nel mock, o 'unknown')

    Vogliamo verificare che il sistema estragga MIT, Apache e GPL-3.0
    e faccia i cross-check tra (MIT, Apache) e (GPL-3.0).
    """
    # Left side: (MIT OR Apache-2.0)
    left_node = MockOr(MockLeaf("MIT"), MockLeaf("Apache-2.0"))
    # Right side: GPL-3.0
    right_node = MockLeaf("GPL-3.0")
    # Root: AND
    root = MockAnd(left_node, right_node)

    status, trace = evaluator.eval_node("GPL-3.0", root)

    trace_str = " ".join(trace)

    # Verifica che siano stati fatti i controlli incrociati per TUTTE le foglie
    # MIT vs GPL-3.0
    assert "Cross compatibility check: MIT with GPL-3.0" in trace_str
    # Apache vs GPL-3.0
    assert "Cross compatibility check: Apache-2.0 with GPL-3.0" in trace_str
