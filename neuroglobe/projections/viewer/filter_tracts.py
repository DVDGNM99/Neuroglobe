import numpy as np
from pathlib import Path

from neuroglobe.projections.config import load_mining_config
from neuroglobe.projections.definitions import CONFIGS_DIR, TRACTS_DIR
from neuroglobe.projections.logger_config import log

# --- PATH CONFIGURATION ---
CONFIG_PATH = CONFIGS_DIR / "mining_config.yaml"
DATA_DIR = TRACTS_DIR
OUTPUT_NAME = "filtered_tracts.vtk"
ATLAS_NAME = "allen_mouse_25um"


class TractFilterError(RuntimeError):
    pass


def load_targets_from_config():
    cfg = load_mining_config(CONFIG_PATH)
    targets = cfg.get("selection", {}).get("custom_targets", [])
    return list(dict.fromkeys(t.split("#")[0].strip() for t in targets if t.strip()))

def get_latest_tract_file():
    """Finds the most recent .nrrd file and returns the ABSOLUTE path."""
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Directory not found: {DATA_DIR}")

    files = list(DATA_DIR.glob("*.nrrd"))
    if not files:
        files = list(DATA_DIR.glob("*.mhd"))

    if not files:
        raise FileNotFoundError("No tractography files found in data/processed/tracts")

    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files[0].resolve()

def run_filter(
    input_path: Path | None = None,
    output_path: Path | None = None,
    *,
    target_regions: list[str] | None = None,
):
    log.info(f"--- FILTERING TRACTS (VOXEL MODE) ---")

    # 1. Load Targets
    if target_regions is None:
        target_regions = load_targets_from_config()
    target_regions = list(dict.fromkeys(target_regions))
    log.info(f"Targets: {target_regions}")

    if not target_regions:
        raise TractFilterError("At least one target region is required.")

    # 2. Find Input File
    input_file = Path(input_path) if input_path else get_latest_tract_file()
    if not input_file.exists():
        raise FileNotFoundError(f"Tract volume not found: {input_file}")
    log.info(f"Input Absolute Path: {input_file}")

    if output_path is None:
        output_path = DATA_DIR / OUTPUT_NAME

    # 3. Load Atlas
    from brainglobe_atlasapi import BrainGlobeAtlas
    from vedo import Volume

    log.info(f"Loading Atlas: {ATLAS_NAME}...")
    bg_atlas = BrainGlobeAtlas(ATLAS_NAME)

    # 4. Load Volume
    log.info(f"Loading Volume...")
    vol = Volume(str(input_file))
    vol_data = np.asarray(vol.tonumpy(), dtype=np.float32)

    log.info(f"Volume Shape: {vol_data.shape}")
    log.info(f"Atlas Shape: {bg_atlas.annotation.shape}")

    # Index-space masking is only valid when both volumes have the same,
    # explicitly preserved AP/DV/ML geometry.
    if vol_data.shape != bg_atlas.annotation.shape:
        raise TractFilterError(
            "Volume/atlas shape mismatch. Automatic transposition is disabled "
            f"because it loses anatomical meaning: {vol_data.shape} != "
            f"{bg_atlas.annotation.shape}."
        )

    volume_spacing = tuple(float(value) for value in vol.spacing())
    atlas_spacing = tuple(float(value) for value in bg_atlas.resolution)
    if not np.allclose(volume_spacing, atlas_spacing, atol=1e-6):
        raise TractFilterError(
            f"Volume spacing {volume_spacing} does not match atlas {atlas_spacing}."
        )

    # 5. Create Voxel Mask
    log.info("Generating Voxel Mask...")
    full_mask = np.zeros(bg_atlas.annotation.shape, dtype=bool)
    valid_regions = []
    for region in target_regions:
        try:
            structure = bg_atlas.structures[region]
            sid = structure['id']
            mask = bg_atlas.get_structure_mask(sid)
            np.logical_or(full_mask, mask, out=full_mask)
            valid_regions.append(region)
        except KeyError:
            log.warning(f"[WARN] Region '{region}' not found in atlas.")
        except Exception as e:
            log.warning(f"[WARN] Error masking '{region}': {e}")

    if not valid_regions:
        raise TractFilterError("None of the requested target regions exists in the atlas.")
    if not np.any(full_mask):
        raise TractFilterError("The combined target mask contains no voxels.")

    # 6. Apply Mask
    log.info("Applying Mask to Volume...")
    np.multiply(vol_data, full_mask, out=vol_data, casting="unsafe")

    # Update volume data
    res = bg_atlas.resolution
    masked_vol = Volume(vol_data, spacing=res, origin=vol.origin())

    # 7. Isosurface & Save
    log.info("Extracting Isosurface...")
    dmax = masked_vol.scalar_range()[1]
    if not np.isfinite(dmax) or dmax <= 0:
        raise TractFilterError("Filtered projection volume is empty.")
    threshold = dmax * 0.05
    filtered_tracts = masked_vol.isosurface(value=threshold)
    point_count = getattr(filtered_tracts, "npoints", None)
    if callable(point_count):
        point_count = point_count()
    if point_count is not None and int(point_count) == 0:
        raise TractFilterError("Isosurface extraction produced an empty mesh.")

    log.info(f"Saving to {output_path}...")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filtered_tracts.write(str(output_path))
    if not output_path.exists():
        raise TractFilterError(f"Mesh writer did not create {output_path}.")
    log.info(f"[SUCCESS] Done! File saved: {output_path.name}")
    return output_path

if __name__ == "__main__":
    try:
        run_filter()
    except Exception as error:
        log.error("[ERROR] %s", error)
        raise SystemExit(1)
