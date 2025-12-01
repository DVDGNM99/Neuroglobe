import sys
from vedo import Volume

def check_volume(path):
    print(f"--- Volume Info: {path} ---")
    try:
        vol = Volume(path)
        print(f"Dimensions:   {vol.dimensions()}")
        print(f"Spacing:      {vol.spacing()}")
        print(f"Origin:       {vol.origin()}")
        print(f"Bounds:       {vol.bounds()}")
        print(f"Scalar Range: {vol.scalar_range()}")
        print("-----------------------------")
    except Exception as e:
        print(f"Error loading volume: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_volume_info.py <path_to_nrrd>")
    else:
        check_volume(sys.argv[1])
