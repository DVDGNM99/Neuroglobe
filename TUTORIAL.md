# 🎓 NeuroGlobe GUI Walkthrough

> **Prerequisites**: Ensure you have installed the environments (including `jupyter_analysis` for notebooks) as described in [README.md](README.md#setup--environments) and activated the `allensdk` environment.

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
    > **Fallback**: If the Launcher fails to open the Viewer, you can launch it manually:
    > ```bash
    > conda activate brainglobe_render
    > python src/viewer/main.py
    > ```

---

## ⛏️ The Miner Interface
![Miner about](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/minerGUI1.png)

The Miner is divided into tabs. The **About** tab provides a quick workflow summary. Switch to the **Mining Processor** tab to start working.

### Step 1: Configuration
![Mining](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/minerGUI2.png)

1.  **Select Seed**: Start typing the acronym (e.g., `VIS`...) in the box. The dropdown will filter automatically. Select your Injection Site (e.g., `VISp`).
2.  **Select Targets**: Choose projection areas to analyze.
    *   *Type & Add*: Type an acronym and press `+` to add it to your list.
    *   *Remove*: Select a target and press `-` to remove it.
3.  **Metric**: Currently, `projection_density` is the standard metric. Other metrics like energy are planned for future updates.

### ⚠️ Best Practices: Region Selection (Layers vs. Areas)
When exploring the `regions.json` dropdown, you will see specific layers (e.g., `"MO1": "Somatomotor areas, Layer 1"`).
*   **Recommendation**: Always choose the **Generic Parent** (e.g., `MO` - Somatomotor areas) instead of specific layers (`MO1`, `MO2/3`, etc.).
*   **The Reason**: The 3D Atlas Mesh granularity often stops at the "Area" level. Specific layers are defined mathematically in the Allen API but **do not have a corresponding 3D mesh** in the BrainGlobe renderer.
*   **The Problem**: If you select `MO1`, the data will be downloaded and analyzed correctly (CSV), but the Viewer **will not be able to render the region**, resulting in invisible targets.

### Step 2: Execution
On the right panel, click the buttons **in order** (1 → 4).
*   **Wait for "Success!"**: Do not proceed to the next button until the console confirms the previous step is done.
    > ⚠️ **Patience Required**: Fetching new experiments can take **tens of minutes**. The logger will keep you updated.
    > *Troubleshooting*: If you see red error text, check your internet connection or the config.
    > For technical details on what happens in the background, see [README.md](README.md#2-data-processing--logic-crucial).

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

### 4. Saving Your Work (Screenshots)
You can save high-quality images of your current 3D view at any time.

*   **Command**: Press the **`S`** key on your keyboard while the Viewer window is focused.
*   **Output**: The image is saved immediately to the `scenes/` folder.
*   **Format**: High-resolution PNG.
    > *For more details on where these files go, check [README.md - Output Files](README.md#4-output--generated-files-scenes).*

---

## 🎨 Interpreting the Visualization

### Understanding Colors (Global Normalization)
You might notice that colors appear "darker" or shift compared to previous versions. This is a feature, not a bug.

**The Logic**:
The Viewer uses **Global Normalization**. This means the color scale (Purple -> Green -> Yellow) is calculated based on the **Maximum Value in the entire dataset** (usually the peak Ipsilateral connection).

*   **Why?** To allow fair comparison. If "Green" meant 0.5 in one view and 0.01 in another, the visualization would be misleading.
*   **Result**:
    -   **Ipsilateral (Strong)**: Will reach the brighter colors (Yellow/Green).
    -   **Contralateral (Weak)**: Will likely stay in the darker range (Purple/Blue).
    -   **Mean (Average)**: Will appear as a mix (Teal/Blue).

### Data View Reference
| Mode | Description | Interpretation |
| :--- | :--- | :--- |
| **Mean** | Average of Left and Right hemisphere values. | Gives a general idea of connection strength but hides asymmetry. Result is symmetric coloring. |
| **Ipsilateral** | Projections to the **same side** as the injection. | Shows the direct, local connectivity strength. Usually the strongest signal. |
| **Contralateral** | Projections to the **opposite side** (crossing the corpus callosum). | Shows long-range, callosal connectivity. Usually weaker than Ipsilateral. |
| **Both** | **The Truth View**. Splits the brain in half. | Left side shows Left data, Right side shows Right data. Perfect for visualizing **Asymmetry** (e.g., strong Ipsilateral vs weak Contralateral). |

---

## 📘 Advanced: Technical Architecture

> This section is for developers or advanced users who want to understand the internal logic or modify the code.

### 📂 Source Overview (`src/`)

#### Core Infrastructure
*   **`src/definitions.py`**: The central source of truth for all file paths. It dynamically locates the project root, replacing brittle relative paths.
*   **`src/logger_config.py`**: Manages the unified logging system.

#### The Miner (`src/miner/`)
*   **`fetch.py`**: Queries the Allen API. Strict validation ensures acronyms match `configs/regions.json`.
*   **`extract_tracts.py`**: Downloads 3D volumes. Note that raw Allen volumes often have metadata mismatches (1µm vs 25µm), which our pipeline automatically corrects.
*   **`aggregate.py`**: Aggregates pixel-level data into region statistics. It applies **Strict Filtering**: if configured, it removes "spillover" injection regions to prevent cluttering the viewer with 50+ seed entries.

#### The Viewer (`src/viewer/`)
*   **`main.py`**: Boots the application and initializes the DearPyGui context.
*   **`controller.py`**: The "Brain". Orchestrates user input, data loading, and rendering updates.
*   **`rendering.py`**: The 3D Engine (based on BrainGlobe/Vedo).
    > **Critical**: The Viewer uses a **Fixed Pivot** system based on the center of the Raw Cloud. Changing the rotation order in this file will desynchronize the Filtered Cloud from the Raw one.
