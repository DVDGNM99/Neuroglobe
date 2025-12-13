import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.viewer.controller import ViewerController
from src.viewer.gui import ViewerGUI

if __name__ == "__main__":
    # 1. Initialize Controller (Logic)
    controller = ViewerController()
    
    # 2. Initialize GUI (Layout) with Controller
    app = ViewerGUI(controller)
    
    # 3. Launch
    app.build()