import pytest

from neuroglobe.projections.config import ConfigError, MINING_METRICS, load_mining_config


def test_config_is_validated_and_targets_are_deduplicated(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
experiment:
  seed_acronym: ACA
  target_regex: "*"
processing:
  aggregation_mode: mean
  metric: projection_density
quality_control:
  min_injection_volume: 0.05
  threshold_lower: 0.00001
selection:
  use_custom_targets: true
  custom_targets: [PL, MOs, PL]
""",
        encoding="utf-8",
    )
    config = load_mining_config(path)
    assert config["selection"]["custom_targets"] == ["PL", "MOs"]


def test_config_rejects_unknown_keys(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        """
experiment: {seed_acronym: ACA}
processing: {aggregation_mode: mean, metric: projection_density}
quality_control: {}
selection: {}
silently_ignored: true
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="Unknown"):
        load_mining_config(path)


@pytest.mark.parametrize("metric", MINING_METRICS)
def test_config_accepts_every_miner_gui_metric(tmp_path, metric):
    path = tmp_path / "config.yaml"
    path.write_text(
        f"""
experiment: {{seed_acronym: ACA}}
processing: {{aggregation_mode: mean, metric: {metric}}}
quality_control: {{}}
selection: {{}}
""",
        encoding="utf-8",
    )

    assert load_mining_config(path)["processing"]["metric"] == metric
