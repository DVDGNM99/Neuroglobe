
# NeuroGlobe
**NeuroGlobe** is a comprehensive toolkit for mining, analyzing, and visualizing mouse brain connectivity data using the Allen Brain Atlas API. It provides a pipeline to fetch experimental data, perform statistical analysis, and render 3D interactive scenes with tractography.
---
![imagine](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/Whole%20brain%20Serotonine%20projections.png)
![imagine](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/Filtered%20Serotonine%20projections%20in%20cortical%20target%20regions.png)
![imagine](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/Cortical%20targets%20Heatmaps%20of%20Serotonine%20inputs.png)
![imagine](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/Serotonine%20projections%20in%20target%20regions.png)
![imagine](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/statistical%20serotonine.png)



## 🔗 Documentation & Roadmap

- **[TUTORIAL.md](https://github.com/DVDGNM99/Neuroglobe-3.0/blob/main/TUTORIAL.md)**: This file provides a complete guide to the project. It covers **Environment Setup** (Conda), **Data Mining** (how to fetch and process data), **3D Viewer Usage** (controls and features), and a detailed **Project Structure** breakdown. It also includes a **Troubleshooting** section.
- **[ROADMAP.md](https://github.com/DVDGNM99/Neuroglobe-3.0/blob/main/ROADMAP.md)**: This file tracks the development progress. It lists **Completed Features** (like the native workflow and alignment system), **In Progress** items (advanced analysis, viewer enhancements), and contains critical **Developer Notes** regarding the manual alignment logic.

---

## 📚 Table of Contents
- [Project Structure](#project-structure)
- [Environments & Setup](#environments--setup)
- [Configuration](#configuration)
- [Mining Pipeline](#mining-pipeline)
- [Analysis](#analysis)
- [Viewer & Visualization](#viewer--visualization)
- [Testing](#testing)

---

## 📂 Project Structure

```
neuroglobe3.0/
├── analysis/               # Jupyter notebooks for statistical analysis
├── configs/                # Configuration files (YAML/JSON)
├── data/                   # Data storage (Raw & Processed)
├── envs/                   # Conda environment definitions
├── scenes/                 # Saved 3D scenes and screenshots
├── src/                    # Source code
│   ├── definitions.py      # [NEW] Central Path Definitions
│   ├── logger_config.py    # [NEW] Centralized Logging
│   ├── miner/              # Data mining scripts
│   └── viewer/             # Visualization scripts
│       ├── main.py         # Entry point
│       ├── gui.py          # GUI layout (DearPyGui)
│       ├── controller.py   # Business logic
│       └── rendering.py    # 3D Rendering engine
├── tests/                  # Test suite
├── TESTING_WORKFLOW.md     # [NEW] Guide for running tests
├── UPDATE4.0.md            # [NEW] Changelog for v4.0
└── README.md               # This guide
```

---

## 🛠 Environments & Setup

This project uses **Conda** to manage dependencies and is installed as a Python package.

### 1. Installation
First, create the `allensdk` environment (used for mining, analysis, and testing):

```bash
conda env create -f envs/allensdk.yml
conda activate allensdk
# Install the project in editable mode
pip install -e .

# Alternative (Non-Conda):
# pip install -r envs/requirements.txt
```

### 2. Viewer Environment
For the 3D Viewer (BrainGlobe/Vedo), use the specialized environment:
```bash
conda env create -f envs/brainglobe_render.yml
conda activate brainglobe_render
# Install project here as well
pip install -e .
```

---

## ⚙️ Configuration

### `configs/mining_config.yaml`
Controls the mining process.
- **`experiment.seed_acronym`**: The brain region to use as the injection seed (e.g., `VISp`).
- **`selection.custom_targets`**: List of target regions to filter or analyze.

### `configs/visual_config.yaml`
Controls the Viewer's rendering and alignment.
- **`aesthetics`**: Background color, axes visibility, etc.
- **`alignment`**: Manual shifts and rotations for fine-tuning data alignment.

### `configs/regions.json`
Controls the Viewer's default region list.
- Contains a list of regions with `acronym`, `name`, and `color_hex_triplet`.

---

## ⛏ Mining Pipeline

Scripts located in `src/miner/`. Run these in the **`allensdk`** environment.

### 1. `fetch.py`
**Function**: Queries the Allen API for experiments injected in the seed region defined in `mining_config.yaml`.
**Output**: Prints a summary of found experiments.

### 2. `extract_tracts.py`
**Function**: Downloads the projection density volume (tractography) for a specific experiment ID.
**Usage**: Can be imported or run to test extraction for the first found experiment.
**Output**: Saves `.nrrd` files to `data/processed/tracts/`.

### 3. `miner_analysis.py`
**Function**: Performs a full analysis of projection data.
- Fetches "unionize" data (projection stats per region).
- Enriches data with ontology (names, acronyms).
- Calculates lateralization (Ipsilateral/Contralateral).
**Output**: Saves a CSV file to `analysis/data/` (e.g., `VISp_full_analysis.csv`).

---

## 📊 Analysis

Located in `analysis/`. Run in the **`allensdk`** environment.

### `analisi_proiezioni_stat.ipynb`
**Function**: Interactive Jupyter Notebook for statistical analysis.
- Loads the CSV generated by `miner_analysis.py`.
- Generates plots (Connectivity Matrix, Bar Charts).
- Performs statistical tests (e.g., Coefficient of Variation).
- Exports filtered data for the Viewer.

---

## 🛠 Data Preparation (Native Workflow)
The viewer expects data to be registered to the Allen Mouse Brain Atlas (CCFv3 25um).
However, raw data often has incorrect metadata (e.g., spacing=1 instead of 25).

We provide tools to fix this automatically:

1.  **Check your data**:
    ```bash
    python scripts/check_volume_info.py data/processed/tracts/your_file.nrrd
    ```
2.  **Fix metadata**:
    ```bash
    python scripts/fix_volume_metadata.py data/processed/tracts/your_file.nrrd
    ```
    This will create a `_fixed.vtk` file (Mesh) with correct spacing (25um) and origin (0,0,0).
    The viewer will **automatically** prioritize this file if it exists.

## Manual Fine-Tuning
Even with correct metadata, slight misalignments can occur due to different registration templates.
You can manually fine-tune the alignment in `configs/visual_config.yaml`:

```yaml
alignment:
  manual_shift:
    x: 0      # + Right, - Left
    y: 0      # + Down (Ventral), - Up (Dorsal)
    z: 0      # + Back (Caudal), - Front (Rostral)

  manual_rotation:
    x: 0
    y: 90     # Often needed for A-P orientation
    z: 0
```
For new experimental data not yet registered to the Allen Atlas, use **[brainreg](https://github.com/brainglobe/brainreg)**:
```bash
brainreg /path/to/raw_data /path/to/output_dir -v 25 -a allen_mouse_25um
```

---

## 🖥 Viewer & Visualization

Scripts located in `src/viewer/`. Run these in the **`brainglobe_render`** environment.

### 3. Interactive 3D Viewer
  - Visualize brain regions and projection clouds.
  - Toggle visibility and transparency.
  - *Coming Soon: Click-to-select regions for detailed stats.*
Launch the viewer to explore the data in 3D:
```bash
python src/viewer/main.py
```
### Visualization Features
- **Brain Regions**: Render any brain region by acronym with custom colors.
- **Hemisphere-Specific Visualization**: Toggle between **Mean**, **Ipsilateral**, **Contralateral**, or **Both** views to analyze callosal projections.
- **Tractography**:
    - **Density (Raw)**: Full projection density cloud.
    - **Density (Filtered)**: Masked cloud showing only connections to selected regions.
    - **Streamlines**: (Experimental) Tube visualization.
- **GUI Controls**:
    - **Top Bar**: Dropdowns for Manual Actions (Add Region/Group) and Data Loading (Auto-detects CSVs).
    - **Bottom Bar**: Large "RENDER SCENE" button, Visualization Mode selector, and **Show Legend** toggle.
- **Interactivity**:
    - **Navigation**: Rotate, Pan, Zoom.
    - **Views**: Quick views (X/Y/Z keys).
    - **Style**: Toggle wireframe (K key - Experimental).
-   **`rendering.py`**: The rendering core.
    -   **Fixed Pivot Rotation**: Rotations now occur around the Raw Cloud's center to ensure Raw and Filtered data stay aligned.
    -   **Viridis Colormap**: Uses the standard scientific colormap (Purple=Low, Yellow=High).
    -   **Legend**: Displays a scalar bar with value ranges (Toggleable via GUI).
    -   **Controls**:
        -   `X`, `Y`, `Z`: Snap to Side, Front, Top views (Double-tap).
        -   `S`: **Save Session**. Creates a timestamped folder with:
            -   `screenshot_...png`: High-res capture.

            -   `metadata.json`: Experiment details.
-   **`filter_tracts.py`**: High-performance voxel masking script.

---

## 🧪 Testing

The project includes a comprehensive test suite in `tests/`.

> [!TIP]
> **See [TESTING_WORKFLOW.md](TESTING_WORKFLOW.md) for detailed instructions on running tests in the correct environment.**

**Quick Method (Recommended)**:
Simply double-click (or run) the helper script:
```bash
.\tests\run_tests.bat
```
This automatically handles environment activation and error logging.

**Test Coverage**:
- **`tests/viewer/`**: Tests UI logic and internal data structures.
- **`tests/miner/`**: Verifies API fetching and data logic.


