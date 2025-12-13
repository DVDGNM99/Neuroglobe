# 📘 NeuroGlobe Antigravity - Project Tutorial

This guide provides step-by-step instructions on how to set up, run, and understand the NeuroGlobe Antigravity project.

---

## 1. 🛠 Environment Setup

The project uses two separate Conda environments to avoid dependency conflicts between the AllenSDK (mining) and BrainGlobe (rendering).

### Prerequisites
- **Anaconda** or **Miniconda** installed.
- **Git** installed.

### Step 1: Create Environments
Open your terminal (Anaconda Prompt on Windows) and navigate to the project folder:

```bash
cd path/to/neuroglobe-antigravity
```

**A. Mining Environment (for downloading data)**
```bash
# Includes: allensdk, pandas, jupyter, pytest
conda env create -f envs/allensdk.yml
```

**B. Rendering Environment (for the 3D Viewer)**
```bash
conda env create -f envs/brainglobe_render.yml
```

### Step 2: Activate Environments
You will switch between these depending on what you are doing:

- **To Mine Data**: `conda activate neuroglobe` (or whatever name is in allensdk.yml, usually `neuroglobe` or `allensdk`)
- **To View Data**: `conda activate brainglobe_render`

---

## 2. ⛏️ Data Mining (The "Miner")

The Miner downloads tractography data from the Allen Mouse Brain Connectivity Atlas based on a "Seed" region.

### A. Configure the Seed
Open `configs/mining_config.yaml`.
- Look for the `seed` or `source` parameter.
- Change it to the acronym of the brain region you want to investigate (e.g., `DR` for Dorsal Raphe, `MOs` for Secondary Motor Area).
- You can also define `targets` here for filtering.

### B. Run the Mining Pipeline
**Activate the Mining Environment first!**

The mining scripts are located in `src/miner`. Run them in this order:

1.  **Fetch Experiments**: Finds experiments matching your seed.
    ```bash
    python src/miner/fetch.py
    ```
    *Output*: Saves metadata to `data/processed/`.

2.  **Extract Tracts**: Downloads the volumetric projection data.
    ```bash
    python src/miner/extract_tracts.py
    ```
    *Output*: Downloads `.nrrd` files to `data/processed/tracts/`.

3.  **Aggregate Data**: Combines connectivity data into a CSV.
    ```bash
    python src/miner/aggregate.py
    ```
    *Output*: `data/processed/DR_connectivity.csv` (or similar).

---

## 3. 👁️ 3D Viewer

The Viewer visualizes the downloaded projection data in 3D space, registered to the Allen Atlas.

### A. Prepare the Data (Native Workflow)
**Activate the Rendering Environment!** (`conda activate brainglobe_render`)

Raw downloaded data often has incorrect metadata (spacing). Before viewing, run the fix script:

```bash
python scripts/fix_volume_metadata.py data/processed/tracts/YOUR_FILE.nrrd
```
*   **Input**: The raw `.nrrd` file from the miner.
*   **Output**: A `_fixed.vtk` file (Mesh) correctly scaled to 25μm.
*   **Why**: This ensures the projection cloud aligns perfectly with the brain atlas.

### B. Launch the Viewer
```bash
python src/viewer/main.py
```

### C. Using the Viewer
- **Load Data**: The viewer automatically looks for the most recent data in `data/processed/tracts`.
- **Navigation**:
    - **Left Click + Drag**: Rotate
    - **Middle Click + Drag**: Pan
    - **Scroll**: Zoom
    - **Shift + Click**: Select a brain region (*Coming Soon - currently disabled*).
- **Controls**: Use the GUI panel to toggle visibility, change transparency, or switch visualization modes (Density Raw vs Filtered).

### D. Saving & Exporting
- **Save Session**: Press **'S'** at any time. This creates a timestamped folder in `scenes/` containing:
    - **Screenshot**: High-resolution PNG.
    - **Metadata**: JSON file with experiment details.
    - **Geometry (OBJ)**: A merged `.obj` file of the scene geometry.

#### 🎨 Professional Workflow (High-Quality SVG)
To generate publication-quality vector graphics:
1.  Render your scene and press **'S'** to export the `.obj` file.
2.  Import the `.obj` file into **Blender**.
3.  Use Blender's **Grease Pencil (Line Art)** or **Freestyle** engine to trace the geometry.
4.  Export the result as SVG from Blender.
This method ensures perfect vector lines without the artifacts common in direct 3D-to-SVG exports.

---

## 4. 📂 Project Structure & File Guide

Here is a detailed breakdown of the project files and what they do.

### 📁 `configs/`
*   `mining_config.yaml`: **[USER EDITABLE]** Controls which brain region to mine (Seed) and which regions to filter for.
*   `regions.json`: Defines the colors and acronyms for brain regions displayed in the viewer.
*   `visual_config.yaml`: **[USER EDITABLE]** Settings for the 3D renderer (background color, camera speed, etc.) and manual alignment.

### 📁 `src/miner/`
*   `fetch.py`: Queries the Allen API for experiments matching the config.
*   `extract_tracts.py`: Downloads the actual 3D projection density volumes (`.nrrd`).
*   `aggregate.py`: Compiles connectivity scores into a single CSV file.
*   `miner_analysis.py`: Performs statistical analysis on the mined data.

### 📁 `src/viewer/`
*   `main.py`: **[ENTRY POINT]** The main application script. Initializes the GUI and Renderer.
*   `gui.py`: **[GUI]** Handles the DearPyGui layout and user interactions.
*   `controller.py`: **[LOGIC]** Manages application state and coordinates between GUI and Rendering.
*   `rendering.py`: **[CORE ENGINE]** Handles all 3D rendering logic (BrainGlobe/Vedo), actor management, and alignment.
*   `filter_tracts.py`: A script to spatially filter the projection cloud to specific target regions (creates `filtered_tracts.vtk`).
*   `logic.py`: Helper functions for viewer logic.
*   `show_legend.py`: Handles the colorbar/legend display.

### 📁 `scripts/`
*   `check_volume_info.py`: Diagnostic tool. Prints metadata (spacing, origin) of a volume file.
*   `fix_volume_metadata.py`: **[CRITICAL]** Converts raw `.nrrd` (1μm spacing) to `.vtk` (25μm spacing) for correct alignment.

### 📁 `data/processed/`
*   `tracts/`: Stores the 3D data files.
    *   `*.nrrd`: Raw volumetric data (Density). **Requires fixing.**
    *   `*_fixed.vtk`: **[READY]** Fixed mesh data, correctly aligned. **The viewer prefers this.**
    *   `*.vti`: Volumetric data (legacy format).
*   `DR_connectivity.csv`: The main dataset containing connectivity strength between the Seed and all other regions.

### 📁 `analysis/`
*   `analisi_proiezioni_stat.ipynb`: Jupyter Notebook for advanced statistical analysis and plotting (e.g., correlation matrices, variability).
*   `region_reference.csv`: A reference table of brain region names and IDs.

### 📁 `envs/`
*   `allensdk.yml`: Conda environment file for the Miner.
*   `brainglobe_render.yml`: Conda environment file for the Viewer.

---

## 5. ❓ Troubleshooting

**Q: The projection cloud is a tiny dot.**
A: You are viewing the raw `.nrrd` file. Run `scripts/fix_volume_metadata.py` to create a correctly scaled `_fixed.vtk` file.

**Q: The projection is the right size but slightly shifted.**
A: Open `configs/visual_config.yaml` and adjust the `manual_shift` (x, y, z) values.
**Note:** The viewer uses a **Fixed Pivot** (Raw Cloud Center) for rotations. This ensures that if you adjust `manual_rotation`, both the Raw and Filtered clouds move together perfectly.

**Q: "Module not found" errors.**
A: Ensure you have activated the correct environment (`brainglobe_render` for viewer, `neuroglobe` for miner).
---

## 6. 👨‍💻 Developer Guide

### Logs
The application now logs extensive details to `logs/app_YYYY-MM-DD.log`.
- **INFO**: Standard operations (files loaded, scenes rendered).
- **WARNING**: Non-critical issues (missing configs, slight misalignments).
- **ERROR**: Critical failures (API errors, missing dependencies).

Check this file first if something goes wrong.

### Testing
To run the developer tests:
1.  **Recommended Method** (easiest):
    ```bash
    conda run -n allensdk pytest
    ```
2.  **Manual Method**:
    ```bash
    conda activate allensdk
    pytest
    ```
3. See [TESTING_WORKFLOW.md](TESTING_WORKFLOW.md) for full details.

### Changelog
For a technical deep-dive into the latest changes, see [UPDATE4.0.md](UPDATE4.0.md).
