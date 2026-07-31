import json
import numpy as np
from brainglobe_atlasapi import BrainGlobeAtlas
import SimpleITK as sitk

from neuroglobe.genetics.definitions import (
    ATLAS_RESOLUTION,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    CONFIGS_DIR,
    ensure_runtime_directories,
)
from neuroglobe.core.provenance import artifact_manifest, file_sha256, write_json_atomic

ATLAS_NAME = "allen_mouse_25um"

def filter_all_volumes():
    manifest_path = CONFIGS_DIR / "manifest.json"

    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    genes = manifest.get("processing", {}).get("genes", [])
    target_regions = manifest.get("processing", {}).get("target_regions", [])

    if not genes or not target_regions:
        print("[ERROR] Genes or target regions missing in manifest.")
        return

    print(f"Loading Atlas: {ATLAS_NAME}...")
    bg_atlas = BrainGlobeAtlas(ATLAS_NAME)

    print("Generating Master Mask...")
    master_mask = np.zeros(bg_atlas.annotation.shape, dtype=bool)
    valid_regions = []
    for region in target_regions:
        try:
            # Need to get children correctly in BrainGlobeAtlas if needed,
            # but get_structure_mask typically returns the mask for the region and its children
            struct = bg_atlas.structures[region]
            mask = bg_atlas.get_structure_mask(struct['id'])
            np.logical_or(master_mask, mask, out=master_mask)
            valid_regions.append(region)
            print(f"  Added {region} to mask.")
        except KeyError:
            print(f"[WARN] Region '{region}' not found in atlas.")

    if not valid_regions or not np.any(master_mask):
        raise ValueError("No valid, non-empty atlas region masks were generated.")

    print(f"Master Mask Shape: {master_mask.shape}")

    for gene in genes:
        input_nrrd = RAW_DATA_DIR / f"{gene}_density.nrrd"
        output_nrrd = PROCESSED_DATA_DIR / f"{gene}_filtered.nrrd"

        if not input_nrrd.exists():
            print(f"[WARN] Missing raw data for {gene}. Skipping...")
            continue

        print(f"--- Processing {gene} ---")
        img = sitk.ReadImage(str(input_nrrd))
        vol_data = sitk.GetArrayFromImage(img)

        print(f"[{gene}] Original Image Size (X,Y,Z): {img.GetSize()}, Array Shape (Z,Y,X): {vol_data.shape}")

        # BrainGlobe arrays are AP/DV/ML. SimpleITK accepts arrays as Z/Y/X,
        # hence this single explicit conversion before physical-space resampling.
        mask_image = sitk.GetImageFromArray(
            np.transpose(master_mask.astype(np.uint8), (2, 1, 0))
        )
        mask_image.SetSpacing(tuple(float(value) for value in ATLAS_RESOLUTION))
        mask_image.SetOrigin((0.0, 0.0, 0.0))
        mask_image.SetDirection((1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))
        resampled_mask_image = sitk.Resample(
            mask_image,
            img,
            sitk.Transform(),
            sitk.sitkNearestNeighbor,
            0,
            sitk.sitkUInt8,
        )
        resampled_mask = sitk.GetArrayFromImage(resampled_mask_image).astype(bool)
        if resampled_mask.shape != vol_data.shape:
            raise ValueError(
                f"Physical mask shape {resampled_mask.shape} does not match "
                f"gene volume {vol_data.shape}."
            )
        filtered_data = np.asarray(vol_data, dtype=np.float32).copy()
        filtered_data[~resampled_mask] = 0

        out_img = sitk.GetImageFromArray(filtered_data)
        out_img.CopyInformation(img)

        sitk.WriteImage(out_img, str(output_nrrd))
        write_json_atomic(
            output_nrrd.with_suffix(".manifest.json"),
            artifact_manifest(
                artifact_type="masked_gene_expression_volume",
                gene=gene,
                target_regions=valid_regions,
                coordinate_convention="Allen CCF: x=AP, y=DV, z=ML; units=um",
                resampling="SimpleITK nearest-neighbor in physical space",
                source={
                    "path": input_nrrd.name,
                    "sha256": file_sha256(input_nrrd),
                },
                output={
                    "path": output_nrrd.name,
                    "sha256": file_sha256(output_nrrd),
                    "size": list(out_img.GetSize()),
                    "spacing_um": list(out_img.GetSpacing()),
                    "origin_um": list(out_img.GetOrigin()),
                    "direction": list(out_img.GetDirection()),
                },
            ),
        )
        print(f"[SUCCESS] Saved filtered volume to {output_nrrd.name}")

def main() -> int:
    ensure_runtime_directories()
    filter_all_volumes()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
