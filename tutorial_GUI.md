# Neuroglobe 4.0 - GUI User Tutorial

## 1. Getting Started

### Prerequisites
This project relies on **two separate Conda environments** as described in `README.md`.

1.  **`allensdk`**: Used for the **Miner GUI** and data processing.
2.  **`brainglobe_render`**: Used for the **Viewer**.

### Installing GUI Dependencies
Since the new GUI uses `customtkinter`, you must install it in your `allensdk` environment:
```bash
conda activate allensdk
pip install customtkinter
```

### Launching the System
To use the **Miner GUI** (recommended starting point), ensure you are in the `allensdk` environment:
```bash
conda activate allensdk
python GUI_caller/launcher.py
```
This will open the main menu window.

---

## 2. The Main Menu (Launcher)
You will see two main options:
1.  **Open Miner GUI**: Click this to start the data mining and processing pipeline.
2.  **Launch Viewer**: Click this to open the 3D visualization engine once you have data.

---

## 3. using the Miner GUI

### Tab 1: About
Read this to understand the 4-step workflow (Fetch -> Extract -> Aggregate -> Filter).

### Tab 2: Mining Processor (Config & Run)
This is your command center.

#### Step A: Configure
1.  **Seed Selection**: Start typing in the "Seed Region" box (e.g., "MO"). The dropdown will filter automatically. Select your Injection Site (e.g., `MOp`).
2.  **Target Selection**:
    *   To **Add**: Type a region in the box next to the `+` button, select it, and click `+`.
    *   To **Remove**: Type/Select a region in the same box and click `-`.
    *   *Note*: The big text box below shows your current active list.
3.  **Metric**: Choose `projection_density` (recommended) or `projection_energy`.
4.  **Save**: Click **[ SAVE CONFIGURATION ]** to confirm your changes. Check the console log at the bottom for "[SUCCESS]".

#### Step B: Execute Pipeline
Run the buttons in order on the right side:
1.  **[ 1. Fetch Experiments ]**: Finds available data from Allen Institute. Wait for "Finished fetch.py".
2.  **[ 2. Extract Tracts ]**: Downloads the 3D volume for the best experiment. This might take a minute.
3.  **[ 3. Aggregate & Build ]**: Calculates the mean brain model.
4.  **[ 4. Filter Targets ]**: Refines the final CSV.

**Validation**:
Watch the **Process Log** at the bottom. It should say `[SUCCESS]` after each step. If you see errors (red text or "Traceback"), check your internet connection or the config.

---

## 4. Miner Analysis (Advanced)
Switch to the "Miner Analysis" tab if you want to export raw statistics for Excel/SPSS.
*   Click **[ RUN FULL ANALYSIS ]**.
*   The file will be saved in `analysis/data/`.

---

## 5. Visualizing
Once mining is done:
1.  Close the Miner window (optional).
2.  **Option A**: Back in the **Launcher**, click **[ Launch Viewer ]**. (This requires viewer dependencies in your current env).
3.  **Option B (Recommended)**: If Option A fails, switch environments manually:
    ```bash
    conda activate brainglobe_render
    python src/viewer/main.py
    ```
4.  The 3D window will open with your new Seed and Targets loaded!
