import pytest
from pathlib import Path
import json

# Define path to notebooks
NOTEBOOK_DIR = Path(__file__).resolve().parent.parent.parent / "analysis"

def test_notebook_exists():
    nb_path = NOTEBOOK_DIR / "analisi_proiezioni_stat.ipynb"
    assert nb_path.exists(), f"Notebook not found at {nb_path}"

def test_notebook_valid_json():
    nb_path = NOTEBOOK_DIR / "analisi_proiezioni_stat.ipynb"
    if not nb_path.exists():
        pytest.skip("Notebook not found")
        
    with open(nb_path, "r", encoding="utf-8") as f:
        try:
            nb_content = json.load(f)
        except json.JSONDecodeError:
            pytest.fail("Notebook is not valid JSON")
            
    assert "cells" in nb_content
    assert "metadata" in nb_content
    assert "nbformat" in nb_content

# Optional: Test execution (skipped by default as it requires specific kernels)
@pytest.mark.skip(reason="Requires specific kernel and data")
def test_notebook_execution():
    # This would use nbconvert to execute
    pass
