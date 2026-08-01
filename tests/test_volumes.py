import numpy as np
import pytest

from neuroglobe.core.volumes import (
    apply_binary_mask_inplace,
    iter_axis0_chunks,
    plan_axis0_chunks,
    write_masked_npy,
)


def test_chunk_plan_respects_budget_and_covers_volume():
    plan = plan_axis0_chunks(
        (10, 4, 5),
        np.float32,
        maximum_working_bytes=4 * 4 * 5 * 2,
    )

    chunks = list(iter_axis0_chunks(plan))
    covered = sum(chunk[0].stop - chunk[0].start for chunk in chunks)
    assert plan.chunk_depth == 1
    assert plan.chunk_count == 10
    assert plan.working_memory_bytes <= 4 * 4 * 5 * 2
    assert covered == 10


def test_inplace_masking_changes_original_without_full_copy():
    values = np.arange(60, dtype=np.float32).reshape(3, 4, 5)
    original_identity = id(values)
    mask = np.zeros(values.shape, dtype=bool)
    mask[:, 1:3, 2:4] = True

    plan = apply_binary_mask_inplace(values, mask, maximum_working_bytes=80)

    assert id(values) == original_identity
    assert plan.chunk_count == 3
    assert np.all(values[~mask] == 0)
    assert np.all(values[mask] > 0)


def test_masked_memmap_output_can_be_loaded_without_resident_copy(tmp_path):
    values = np.arange(120, dtype=np.int16).reshape(4, 5, 6)
    mask = values % 3 == 0
    path, plan = write_masked_npy(
        values,
        mask,
        tmp_path / "masked.npy",
        maximum_working_bytes=90,
    )

    restored = np.load(path, mmap_mode="r")
    assert isinstance(restored, np.memmap)
    assert plan.chunk_count > 1
    np.testing.assert_array_equal(restored, values * mask)


def test_masking_rejects_shape_mismatch():
    with pytest.raises(ValueError, match="shape mismatch"):
        apply_binary_mask_inplace(
            np.zeros((2, 2), dtype=np.float32),
            np.zeros((2, 3), dtype=bool),
        )
