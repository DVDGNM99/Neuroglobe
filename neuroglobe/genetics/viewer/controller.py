import argparse
from pathlib import Path

from neuroglobe.genetics.viewer.rendering import GeneticsRenderEngine

class GeneticsViewerController:
    """
    Bridge between GUI and Rendering Engine for Genetics Module.
    """
    def __init__(self, runtime_state_path=None):
        self.engine = None
        self.runtime_state_path = runtime_state_path

    def get_lazy_engine(self):
        if self.engine is None:
            self.engine = GeneticsRenderEngine(
                runtime_state_path=self.runtime_state_path
            )
        return self.engine

    def launch_viewer(self):
        print("[CONTROLLER] Launching Genetics Viewer...")
        try:
            engine = self.get_lazy_engine()
            engine.render_genes()
            return True, "Viewer engaged successfully."
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"Viewer crash: {e}"

def main() -> int:
    parser = argparse.ArgumentParser(description="Neuroglobe genetics viewer")
    parser.add_argument("--state", type=Path, help="Per-run GUI state JSON")
    args = parser.parse_args()
    c = GeneticsViewerController(runtime_state_path=args.state)
    success, message = c.launch_viewer()
    print(message)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
