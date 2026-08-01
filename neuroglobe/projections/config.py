"""Validated projection configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


_TOP_LEVEL_KEYS = {"experiment", "processing", "quality_control", "selection"}
_SECTION_KEYS = {
    "experiment": {"seed_acronym", "target_regex"},
    "processing": {"aggregation_mode", "metric"},
    "quality_control": {"min_injection_volume", "threshold_lower"},
    "selection": {"custom_targets", "use_custom_targets"},
}
_AGGREGATION_MODES = {"mean", "median", "max"}
MINING_METRICS = (
    "projection_density",
    "projection_energy",
    "projection_volume",
)
_METRICS = frozenset(MINING_METRICS)


def _deduplicate(values: list[Any]) -> list[str]:
    return list(dict.fromkeys(str(value).split("#", 1)[0].strip() for value in values if str(value).strip()))


def load_mining_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config not found at {path}")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ConfigError("Mining config must be a YAML mapping.")

    unknown = set(config) - _TOP_LEVEL_KEYS
    if unknown:
        raise ConfigError(f"Unknown top-level config keys: {sorted(unknown)}")

    for section_name, allowed_keys in _SECTION_KEYS.items():
        section = config.get(section_name, {})
        if not isinstance(section, dict):
            raise ConfigError(f"{section_name} must be a YAML mapping.")
        unknown_section_keys = set(section) - allowed_keys
        if unknown_section_keys:
            raise ConfigError(
                f"Unknown {section_name} keys: {sorted(unknown_section_keys)}"
            )

    experiment = config.get("experiment", {})
    processing = config.get("processing", {})
    qc = config.get("quality_control", {})
    selection = config.get("selection", {})
    if not experiment.get("seed_acronym"):
        raise ConfigError("experiment.seed_acronym is required.")
    if processing.get("aggregation_mode", "mean") not in _AGGREGATION_MODES:
        raise ConfigError("processing.aggregation_mode must be mean, median, or max.")
    if processing.get("metric", "projection_density") not in _METRICS:
        raise ConfigError(f"Unsupported processing.metric: {processing.get('metric')}")

    min_volume = float(qc.get("min_injection_volume", 0.0))
    threshold = float(qc.get("threshold_lower", 0.0))
    if min_volume < 0 or threshold < 0:
        raise ConfigError("Quality-control thresholds cannot be negative.")

    selection["custom_targets"] = _deduplicate(selection.get("custom_targets", []))
    experiment["target_regex"] = str(experiment.get("target_regex", "*"))
    processing.setdefault("aggregation_mode", "mean")
    processing.setdefault("metric", "projection_density")
    qc["min_injection_volume"] = min_volume
    qc["threshold_lower"] = threshold
    config.update(
        experiment=experiment,
        processing=processing,
        quality_control=qc,
        selection=selection,
    )
    return config
