# Neuroglobe 4.0 - GUI System & Logic Changes

## 1. System Overview
We have successfully implemented a dual-GUI architecture to simplify the workflow.

### A. The Launcher (`GUI_caller/launcher.py`)
*   **Purpose**: Central entry point.
*   **Configuration**: Text and labels are loaded dynamically from `launcher_text.yaml`.
*   **Actions**:
    *   **Open Miner GUI**: Launches the detailed mining interface.
    *   **Launch Viewer**: Launches the main 3D visualization engine.

### B. The Miner GUI (`GUI_caller/miner_gui.py`)
*   **Structure**: 3-Tab Interface.
    1.  **About**: Explains the workflow steps.
    2.  **Mining Processor**:
        *   **Smart Search**: Typable dropdowns for Seed and Target selection (loads `regions.json`).
        *   **List Management**: Add (+) and Remove (-) buttons for targets.
        *   **Config Saving**: Updates `mining_config.yaml` with valid settings.
        *   **Pipeline Execution**: Buttons run the backend scripts via subprocesses, streaming logs to the GUI console.
    3.  **Miner Analysis**: Separate tab for running `miner_analysis.py`.

## 2. Logic Changes (Backend)
To support the GUI, minor changes were made to the backend scripts so they can run as standalone subprocesses from any directory (via `sys.path` fixes).

| File | Change | Reason |
| :--- | :--- | :--- |
| `src/miner/extract_tracts.py` | Added `if __name__ == "__main__":` block | To allow the "Extract Tracts" button to run it as a standalone script. |
| `src/miner/extract_tracts.py` | Added `sys.path` injection | Ensures `import src...` works when run from GUI. |
| `src/miner/fetch.py` | Added `sys.path` injection | Ensures `import src...` works when run from GUI. |
| `src/miner/miner_analysis.py` | Added `sys.path` injection | Ensures `import src...` works when run from GUI. |

## 3. How to Run
1.  **GUI Mode**: Run `python GUI_caller/launcher.py`.
2.  **Legacy Mode**: All original command-line scripts still work as before.
