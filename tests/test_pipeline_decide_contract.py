"""
ALADIN37 - Canonical `pipeline.decide()` Contract Test V1

Testet ausschliesslich die oeffentliche Funktion pipeline.decide(total_score)
gegen den verbindlichen Contract:

    total_score < 45        -> "ABLEHNEN"
    45 <= total_score < 75  -> "WEITER PRÜFEN"
    total_score >= 75       -> "WEITERVERFOLGEN"

Bewusst NICHT abgedeckt (fachlich nicht spezifiziert, siehe Auftrag):
None, str, bool, NaN, +inf, -inf. Kein neuer Contract fuer diese Faelle,
keine Validierung in pipeline.py, keine neue Fehlersemantik.

Testet nur das oeffentliche Verhalten von decide(), nicht die interne
if-Struktur oder die DECISION_THRESHOLDS-Konstanten.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pipeline  # noqa: E402


@pytest.mark.parametrize(
    "total_score, expected",
    [
        (0, "ABLEHNEN"),
        (44.999999, "ABLEHNEN"),
        (45, "WEITER PRÜFEN"),
        (45.000001, "WEITER PRÜFEN"),
        (74.999999, "WEITER PRÜFEN"),
        (75, "WEITERVERFOLGEN"),
        (75.000001, "WEITERVERFOLGEN"),
        (100, "WEITERVERFOLGEN"),
    ],
)
def test_decide_contract_boundaries(total_score, expected):
    assert pipeline.decide(total_score) == expected
