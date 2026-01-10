import sys
from pathlib import Path

# Add src to path
# Add src to path (prioritize local project)
root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)
print(f"DEBUG: Viewer running from: {root_path}")

from src.viewer.controller import ViewerController
from src.viewer.gui import ViewerGUI

if __name__ == "__main__":
    # 1. Initialize Controller (Logic)
    controller = ViewerController()
    
    # 2. Initialize GUI (Layout) with Controller
    app = ViewerGUI(controller)
    
    # 3. Launch
    app.build()