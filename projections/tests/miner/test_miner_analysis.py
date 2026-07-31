from neuroglobe.projections.miner.miner_analysis import get_lateralization


def test_lateralization_uses_injection_ml():
    assert get_lateralization(1, 2000) == "Ipsilateral"
    assert get_lateralization(2, 2000) == "Contralateral"
    assert get_lateralization(2, 9000) == "Ipsilateral"
    assert get_lateralization(1, 9000) == "Contralateral"
    assert get_lateralization(3, 9000) == "Midline"
    assert get_lateralization(2, None) == "Unknown"
