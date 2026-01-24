# 🎓 NeuroGlobe GUI Walkthrough

> **Prerequisites**: Ensure you have installed the environments as described in [README.md](README.md#setup--environments) and activated the `allensdk` environment.

---

## 🚀 The Launcher
![Launcher](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/launchGUIPicture1.png)

The **Launcher** (`GUI_caller/launcher.py`) is your starting point.
Run the following command in your terminal (ensure `allensdk` environment is active):
```bash
python GUI_caller/launcher.py
```

- **Miner GUI**: Choose this to discovering new data. It handles downloading experiments from the Allen API.
- **Launcher (Viewer)**: Choose this to jump straight into visualizations if you already have data.
    > *Two demo datasets (ACA and DR) are included and can be visualized immediately.*

---

## ⛏️ The Miner Interface
![Miner about](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/minerGUI1.png)

The Miner is divided into tabs. The **About** tab provides a quick workflow summary. Switch to the **Mining Processor** tab to start working.

### Step 1: Configuration
![Mining](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/minerGUI2.png)

1.  **Select Seed**: Enter the injection area (e.g., `VISp`). This is the source of the connections.
2.  **Select Targets**: Choose projection areas to analyze.
    *   *Type & Add*: Type an acronym and press `+` to add it to your list.
    *   *Remove*: Select a target and press `-` to remove it.
3.  **Metric**: Currently, `projection_density` is the standard metric. Other metrics like energy are planned for future updates.

### Step 2: Execution
On the right panel, click the buttons **in order** (1 → 4).
*   **Wait for "Success!"**: Do not proceed to the next button until the console confirms the previous step is done.
    > ⚠️ **Patience Required**: Fetching new experiments can take **tens of minutes**. The logger will keep you updated.
    > For technical details on what happens in the background (Extraction vs. Aggregation), see [README.md - Data Processing & Logic](README.md#2-data-processing--logic-crucial).

### Step 3: Statistical Analysis
![Statistical preparation](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/minerGUI3.png)

Switch to the **Miner Analysis** tab.
Click the **Run Full Analysis** button to process the raw data.
*   **Result**: This generates the necessary files for the [Jupyter Notebook Analysis](README.md#statistical-analysis) (`analysis/projection_stats_analysis.ipynb`), where you can view detailed plots.

---

## 🖥️ The Viewer Interface
![Viewer about](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/viewerGUI1.png)

The Viewer is designed for interactive exploration.

### 1. Loading Data
![Loading data](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/viewerGUI2.png)
*   **Automatic Loading**: Use the **Source** dropdown to select a CSV file (e.g., `..._filtered.csv`). This automatically loads all relevant brain regions.
*   **Manual Loading**: Use **+ Region** or **+ Group** to add specific structures manually for reference, even if they have no projection data.

### 2. Visualization Modes
![View mode projections strength](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/viewerGUI3.png)
Regions are color-coded using the Viridis heatmap (Purple = Low, Yellow = High). You can toggle the logic using the **View Mode** dropdown:

*   **Mean**: Symmetric average (hides lateralization).
*   **Ipsilateral**: Projections to the same side.
*   **Contralateral**: Crossing projections.
*   **Both**: Splits the view (Left Data on Left, Right Data on Right). Recommended for comparing asymmetry.
    > For a detailed explanation of these modes, refer to [README.md - View Mode](README.md#1-top-panel-data-control).

### 3. Tractography (The Cloud)
![View mode projections](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/viewerGUI4.png)
To visualize the 3D pathway:
1.  Click **Filter Raw Volume**. Wait for the status to update.
2.  Use the **Visualization Mode** dropdown (bottom panel):
    *   **None**: Show only regions.
    *   **Density (Raw)**: Show the full projection cloud.
    *   **Density (Filtered)**: Show only projections landing insde your target regions.
