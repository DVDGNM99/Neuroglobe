import sys
from pathlib import Path

# Add src to path
# Add src to path (prioritize local project)
root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)
print(f"DEBUG: Viewer running from: {root_path}")

# --- CRASH PROTECTION ---
def clean_brainrender_logs():
    """
    Brainrender tries to delete its log file on import. 
    If another instance is running, this causes a crash (WinError 32).
    We attempt to clear it here to catch the error gracefully.
    """
    try:
        home = Path.home()
        log_path = home / ".brainglobe" / "brainrender" / "log.log"
        if log_path.exists():
            log_path.unlink()
            print("[STARTUP] Cleared stale brainrender log.")
    except PermissionError:
        print("\n" + "!"*60)
        print("CRITICAL ERROR: Neuroglobe is already running!")
        print(f"Could not access log file: {log_path}")
        print("Please CLOSE all open Viewer/Miner windows and try again.")
        print("!"*60 + "\n")
        input("Press Enter to exit...")
        sys.exit(1)
    except Exception as e:
        print(f"[STARTUP] Log cleanup warning: {e}")

# Run protection before importing brainrender (via controller)
clean_brainrender_logs()

from src.viewer.controller import ViewerController
from src.viewer.gui import ViewerGUI

if __name__ == "__main__":
    # 1. Initialize Controller (Logic)
    controller = ViewerController()
    
    # 2. Initialize GUI (Layout) with Controller
    app = ViewerGUI(controller)
    
    # 3. Launch
    app.build()