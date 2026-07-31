import sys
import types
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from neuroglobe.projections.miner import fetch


def _allen_modules(cache_class):
    allensdk = types.ModuleType("allensdk")
    core = types.ModuleType("allensdk.core")
    cache_module = types.ModuleType("allensdk.core.mouse_connectivity_cache")
    cache_module.MouseConnectivityCache = cache_class
    return {
        "allensdk": allensdk,
        "allensdk.core": core,
        "allensdk.core.mouse_connectivity_cache": cache_module,
    }


def test_get_experiments_success(tmp_path):
    cache_class = MagicMock()
    cache = cache_class.return_value
    ontology = MagicMock()
    ontology.get_structures_by_acronym.return_value = [{"id": 123, "acronym": "VISp"}]
    cache.get_structure_tree.return_value = ontology
    cache.get_experiments.return_value = pd.DataFrame({"id": [1, 2]})

    with patch.dict(sys.modules, _allen_modules(cache_class)):
        experiments, returned_cache = fetch.get_experiments("VISp", tmp_path)

    assert len(experiments) == 2
    assert returned_cache is cache
    ontology.get_structures_by_acronym.assert_called_once_with(["VISp"])


def test_get_experiments_invalid_acronym(tmp_path):
    cache_class = MagicMock()
    ontology = MagicMock()
    ontology.get_structures_by_acronym.return_value = []
    cache_class.return_value.get_structure_tree.return_value = ontology

    with patch.dict(sys.modules, _allen_modules(cache_class)):
        with pytest.raises(ValueError, match="not found in Allen Ontology"):
            fetch.get_experiments("INVALID", tmp_path)
