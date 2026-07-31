from neuroglobe.projections.viewer.controller import ViewerController
from neuroglobe.projections.viewer.gui import ViewerGUI


def main() -> int:
    # 1. Initialize Controller (Logic)
    controller = ViewerController()

    # 2. Initialize GUI (Layout) with Controller
    app = ViewerGUI(controller)

    # 3. Launch
    app.build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
