import sys
from neuroglobe.projections.logger_config import log

def check_volume(path):
    from vedo import Volume

    log.info(f"--- Volume Info: {path} ---")
    try:
        vol = Volume(path)
        log.info(f"Dimensions:   {vol.dimensions()}")
        log.info(f"Spacing:      {vol.spacing()}")
        log.info(f"Origin:       {vol.origin()}")
        log.info(f"Bounds:       {vol.bounds()}")
        log.info(f"Scalar Range: {vol.scalar_range()}")
        log.info("-----------------------------")
        return True
    except Exception as e:
        log.error(f"Error loading volume: {e}")
        return False


def main() -> int:
    if len(sys.argv) < 2:
        log.error("Usage: python check_volume_info.py <path_to_nrrd>")
        return 2
    return 0 if check_volume(sys.argv[1]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
