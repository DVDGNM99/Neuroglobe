import pandas as pd
import pytest

from neuroglobe.projections.miner.aggregate import (
    process_aggregation,
    select_representative_experiment,
)


def test_aggregation_uses_ml_coordinate_and_excludes_hemisphere_three():
    experiments = pd.DataFrame(
        {
            "id": [100, 200],
            # Deliberately contradictory AP coordinates: they must be ignored.
            "injection_x": [9000, 2000],
            "injection_z": [2000, 9000],
        }
    )
    unionizes = pd.DataFrame(
        [
            {
                "experiment_id": 100,
                "structure_id": 5,
                "hemisphere_id": 1,
                "projection_density": 10.0,
                "is_injection": False,
            },
            {
                "experiment_id": 100,
                "structure_id": 5,
                "hemisphere_id": 2,
                "projection_density": 2.0,
                "is_injection": False,
            },
            {
                "experiment_id": 100,
                "structure_id": 5,
                "hemisphere_id": 3,
                "projection_density": 999.0,
                "is_injection": False,
            },
            {
                "experiment_id": 200,
                "structure_id": 5,
                "hemisphere_id": 1,
                "projection_density": 4.0,
                "is_injection": False,
            },
            {
                "experiment_id": 200,
                "structure_id": 5,
                "hemisphere_id": 2,
                "projection_density": 20.0,
                "is_injection": False,
            },
        ]
    )

    result = process_aggregation(
        unionizes,
        experiments,
        {5: "MR"},
        "projection_density",
        "mean",
        best_id=100,
    )
    row = result.loc[result["acronym"] == "MR"].iloc[0]

    assert row["value_ipsi"] == 15.0
    assert row["value_contra"] == 3.0
    assert row["value_left"] == 7.0
    assert row["value_right"] == 11.0
    assert row["value_mean"] == 9.0
    assert row["n_mean"] == 2
    assert row["variance_mean"] == 18.0
    assert row["ci95_low_mean"] == pytest.approx(3.12)
    assert row["ci95_high_mean"] == pytest.approx(14.88)
    assert row["n_ipsi"] == 2
    assert row["variance_ipsi"] == 50.0


def test_unknown_injection_coordinate_is_not_silently_right():
    experiments = pd.DataFrame({"id": [100], "injection_z": [None]})
    unionizes = pd.DataFrame(
        [
            {
                "experiment_id": 100,
                "structure_id": 5,
                "hemisphere_id": 2,
                "projection_density": 8.0,
                "is_injection": False,
            }
        ]
    )

    result = process_aggregation(
        unionizes,
        experiments,
        {5: "MR"},
        "projection_density",
        "mean",
    )
    row = result.iloc[0]
    assert row["value_ipsi"] == 0
    assert row["value_contra"] == 0
    assert row["n_ipsi"] == 0
    assert row["n_contra"] == 0


def test_representative_score_penalizes_missing_spatial_metadata():
    experiments = pd.DataFrame(
        {
            "id": [100, 200],
            "injection_volume": [1.0, 0.8],
            "injection_x": [None, 1000.0],
            "injection_y": [None, 2000.0],
            "injection_z": [None, 3000.0],
        }
    )

    representative = select_representative_experiment(experiments)

    assert representative["id"] == 200
    assert representative["representative_score"] == pytest.approx(0.85)
    assert representative["coordinate_completeness"] == 1.0
