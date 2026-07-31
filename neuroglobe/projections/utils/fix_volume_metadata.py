import sys
from pathlib import Path
from neuroglobe.projections.logger_config import log

def fix_volume(path, target_spacing):
    """Write an explicit-spacing NRRD without guessing axis permutations."""
    import SimpleITK as sitk

    source = Path(path)
    log.info(f"--- Applying explicit spacing metadata: {source} ---")
    try:
        image = sitk.ReadImage(str(source))
        log.info(f"Original spacing: {image.GetSpacing()}")
        image.SetSpacing(tuple(float(value) for value in target_spacing))
        output_path = source.with_name(f"{source.stem}_with_metadata.nrrd")
        sitk.WriteImage(image, str(output_path), useCompression=True)
        log.info(f"Saving corrected NRRD to: {output_path}")
        log.info("Done.")
        return output_path
    except Exception as e:
        log.error(f"Error fixing volume: {e}")
        return None

def main() -> int:
    if len(sys.argv) != 5:
        log.error(
            "Usage: python -m neuroglobe.projections.utils.fix_volume_metadata "
            "<path_to_nrrd> <ap_spacing_um> <dv_spacing_um> <ml_spacing_um>"
        )
        return 2
    output = fix_volume(sys.argv[1], tuple(float(value) for value in sys.argv[2:5]))
    return 0 if output else 1


if __name__ == "__main__":
    raise SystemExit(main())
