import pandas as pd

from neuroglobe.projections.miner.aggregate import process_aggregation


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
