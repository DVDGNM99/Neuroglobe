# 📘 Technical Reference & Project Map

> **Note:** For Installation and Basic Usage, please refer to [README.md](README.md).
> This document is intended for **Developers** and **Advanced Users** who need to understand the internal logic, file structure, and critical constraints of the codebase.

---

## 📂 Source Code (`src/`)

### 🔹 Core Infrastructure
These files provide the foundation for the entire project.

#### `src/definitions.py`
**Purpose**: Central source of truth for all file paths.
- **Capabilities**: Dynamically locates the project root using `pathlib`. Defines standard paths like `DATA_DIR`, `LOGS_DIR`, `SCENES_DIR`.
- **Why it exists**: To replace brittle `../../` relative path hacks that broke when running scripts from different directories.

> [!CAUTION]
> **DO NOT modify `PROJECT_ROOT` logic.**
> All other paths are derived from this. Any change here will break file loading across the entire Miner and Viewer. Always use `from src.definitions import ...` instead of hardcoding paths.

#### `src/logger_config.py`
**Purpose**: unified logging configuration.
- **Capabilities**: Sets up a rotating file handler (`logs/app_YYYY-MM-DD.log`) and a console handler.
- **Usage**: Import `setup_logger` and call it at the start of every script.

---

### 🔹 The Miner (`src/miner/`)
**Environment**: `allensdk`

#### `src/miner/fetch.py`
**Purpose**: Queries the Allen API for available experiments.
- **Critical Logic**: Uses `allensdk.core.mouse_connectivity_cache.MouseConnectivityCache`.

> [!WARNING]
> **API Constraints**: parameters like `injection_structure_ids` are strictly validated by the AllenSDK. Ensure the acronyms match exactly what is in `configs/regions.json`.

#### `src/miner/extract_tracts.py`
**Purpose**: Downloads the 3D Projection Density Volume (`.nrrd`).
- **Limitation**: The Allen API returns volumes with **1µm spacing** (metadata) but the actual data is often 25µm. This metadata mismatch necessitates the `fix_volume_metadata.py` script.

> [!IMPORTANT]
> **Do NOT rely on raw downloads.**
> The downloaded files are often unusable in 3D viewers directly due to incorrect origin/spacing headers. Always run the fix script afterwards.

#### `src/miner/aggregate.py`
**Purpose**: Aggregates pixel-level projection data into region-level statistics.
- **Mechanism**: Groups data by `structure_acronym` and `hemisphere_id`.
- **Filtering Logic (Strict)**: If `use_custom_targets: true` in `mining_config.yaml`:
  1. Keeps only regions listed in `custom_targets`.
  2. Keeps **only** the Primary Seed defined in `experiment.seed_acronym` (removing spillover injection regions).
  3. Saves a separate `_filtered.csv` for clean visualization.
- **Output**: Generates full `value_mean`, `value_ipsi`, `value_contra`, `value_left`, `value_right` metrics.

> [!TIP]
> **Why Filter?**
> Allen experiments often have "injection spillover" into dozens of tiny sub-regions (e.g., layers of hippocampus). Without strict filtering, the Viewer would be flooded with 50+ "[SEED]" entries. The logic ensures you see only what you asked for.

---

### 🔹 The Viewer (`src/viewer/`)
**Environment**: `brainglobe_render`

#### `src/viewer/main.py`
**Purpose**: Entry point. Bootstraps the application.
- **Logic**: Initializes `ViewerGUI`, `ViewerController`, and starts the DearPyGui (DPG) context.

> [!CAUTION]
> **DPG Context Order**: `dpg.create_context()` must be called BEFORE any GUI setup. Do not move this initialization logic.

#### `src/viewer/rendering.py`
**Purpose**: The 3D Rendering Engine (BrainGlobe/Vedo wrapper).
- **Capabilities**: Manages Actors (Brain Regions, Clouds), Scene Camera, and Exporting.

> [!DANGER]
> **CRITICAL: Alignment Logic**
> The Viewer uses a **Fixed Pivot** system. It calculates the center of the `Raw Cloud` and applies all rotations around THAT point.
> **DO NOT CHANGE** the rotation order or pivot logic. Doing so will desynchronize the "Filtered Cloud" from the "Raw Cloud", making the visualization scientifically invalid.

#### `src/viewer/controller.py`
**Purpose**: The "Brain" of the application.
- **Capabilities**: Handles user input events, loads data, and orchestrates the GUI and Renderer updates.
- **State Management**: Keeps track of `current_region`, `loaded_file_path`, etc.

#### `src/viewer/filter_tracts.py`
**Purpose**: High-performance spatial filtering.
- **Logic**: Uses `numpy` boolean masking to zero out voxels that are NOT inside the target regions.
- **Output**: Writes a temporary `.vtk` file (`filtered_tracts.vtk`) which is then loaded by the renderer.

### 4. Interpreting the Visualization

The Viewer offers powerful tools to dissect connectivity data. Here is how to interpret what you see.

#### Data Views (The Dropdown)
Located in the Top Menu, the **"Data View"** dropdown allows you to toggle how projection density is mapped to color:

| Mode | Description | Interpretation |
| :--- | :--- | :--- |
| **Mean** | Average of Left and Right hemisphere values. | Gives a general idea of connection strength but hides asymmetry. Result is symmetric coloring. |
| **Ipsilateral** | Projections to the **same side** as the injection. | Shows the direct, local connectivity strength. Usually the strongest signal. |
| **Contralateral** | Projections to the **opposite side** (crossing the corpus callosum). | Shows long-range, callosal connectivity. Usually weaker than Ipsilateral. |
| **Both** | **The Truth View**. Splits the brain in half. | Left side shows Left data, Right side shows Right data. Perfect for visualizing **Asymmetry** (e.g., strong Ipsilateral vs weak Contralateral). |

#### 🎨 Understanding Colors (Global Normalization)
You might notice that colors appear "darker" or shift compared to previous versions. This is a feature, not a bug.

**The Logic**:
The Viewer uses **Global Normalization**. This means the color scale (Purple -> Green -> Yellow) is calculated based on the **Maximum Value in the entire dataset** (usually the peak Ipsilateral connection).

- **Why?** To allow fair comparison. If "Green" meant 0.5 in one view and 0.01 in another, the visualization would be misleading.
- **Result**:
    - **Ipsilateral (Strong)**: Will reach the brighter colors (Yellow/Green).
    - **Contralateral (Weak)**: Will likely stay in the darker range (Purple/Blue).
    - **Mean (Average)**: Will appear as a mix (Teal/Blue).
    
**In "Both" Mode**:
You may see a region that is **Bright Green** on the right and **Dark Purple** on the left. This visualizes lateralization: the region receives strong input on one side and almost none on the other.

---

## � Helper Scripts (`scripts/`)

#### `scripts/fix_volume_metadata.py`
**Purpose**: The "Bridge" between Allen Data and BrainGlobe Viewer.
- **Operation**:
    1. Reads `.nrrd`.
    2. Overwrites Spacing to `(25, 25, 25)` microns.
    3. Resets Origin to `(0, 0, 0)`.
    4. Saves as `.vtk` (Mesh).

> [!TIP]
> **Why VTK?**
> We convert to VTK because `vedo` (the rendering backend) handles VTK meshes significantly faster and more accurately than raw NRRD volumes for this specific type of density cloud.

#### `scripts/check_volume_info.py`
**Purpose**: Debugging tool to inspect file headers.
- **Use this if**: Your cloud looks like a tiny dot (implies Spacing=1 instead of 25).

---

## 🧪 Tests (`tests/`)

The test suite is your safety net.
- **`tests/conftest.py`**: **Critical**. Sets up `sys.path` so tests can import `src` without installation errors.
- **`run_tests.bat`**: The recommended way to run tests. It handles the environment context.

> [!NOTE]
> **Mocking**:
> The Viewer tests use **MagicMock** heavily to avoid opening a real window during testing. If you modify `rendering.py`, you MUST update the mocks in `test_rendering.py` or the tests will fail.

