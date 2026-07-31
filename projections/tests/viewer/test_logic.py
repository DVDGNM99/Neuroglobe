import json

import pytest

from neuroglobe.projections.viewer import logic


def test_hex_to_rgb():
    assert logic.hex_to_rgb("#FFFFFF") == [255, 255, 255]
    assert logic.hex_to_rgb("#000000") == [0, 0, 0]
    assert logic.hex_to_rgb("#FF0000") == [255, 0, 0]


def test_load_regions_config(tmp_path):
    config_file = tmp_path / "regions.json"
    config_file.write_text(
        json.dumps(
            {
                "VISp": "Primary visual area",
                "MOs": "Secondary motor area",
            }
        ),
        encoding="utf-8",
    )
    regions = logic.load_regions_config(str(config_file))
    assert len(regions) == 2
    assert next(r for r in regions if r.acronym == "VISp").name == "Primary visual area"


def test_process_csv_data_has_stable_result_contract(tmp_path):
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("acronym,value\nVISp,0.5\nMOs,0.8", encoding="utf-8")

    result = logic.process_csv_data(str(csv_file))
    assert [item["acronym"] for item in result.items] == ["VISp", "MOs"]
    assert result.value_min == 0.0
    assert result.value_max == 0.8


@pytest.mark.parametrize(
    "content",
    [
        "",
        "wrong,value\nVISp,0.5\n",
        "acronym,value\nVISp,not-a-number\n",
        "acronym,value\nVISp,0.1\nVISp,0.2\n",
    ],
)
def test_process_csv_data_rejects_invalid_input(tmp_path, content):
    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text(content, encoding="utf-8")
    with pytest.raises(logic.CSVDataError):
        logic.process_csv_data(str(csv_file))
