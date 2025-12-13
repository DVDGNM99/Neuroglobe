# 🗺️ Project Roadmap

## 🚧 In Progress
- [ ] **Advanced Analysis**: Inter-animal variability, normalized connectivity indices.
<!-- Deferred Features -->
<!-- - [ ] **Viewer Enhancements**: Click-to-Info, 2D Slicing (Moved to Future) -->


## 🔮 Future Improvements (Todo)

### ⛏️ Miner & Data
- [ ] **Advanced Metadata Scraping**: Investigate additional available fields in the Allen API (e.g., exact injection coordinates, detailed transgenic line info).
- [ ] **Metadata Utilization**: Implement a system to save and use this extra metadata for advanced filtering and analysis.
- [ ] **2D Image Download**: Fetch high-res 2D images of injection sites for visual verification.
- [ ] **Multi-Experiment Analysis**: Automate aggregation of datasets (e.g., all males vs females) for group studies.
- [ ] **Smart Caching**: Implement hash-based checks to prevent re-downloading existing or corrupted data.
- [ ] **Gene Expression Integration**: Cross-reference connectivity data with Allen Gene Expression Atlas data.

### 💾 Saving & Export
- [x] **Fix Auto-Save Behavior**: Ensure scenes/metadata are saved **ONLY** when 'S' is pressed. Prevent automatic saving on viewer launch/exit.
- [x] **Professional Geometry Export (OBJ)**: Implemented `.obj` export (merged geometry) when 'S' is pressed to enable high-quality SVG generation in Blender (replacing direct unstable SVG export).

### 🏗️ Architecture & Refactoring (Completed v4.0)
- [x] **Refactor Viewer Architecture**: Split `src/viewer/main.py` into `gui.py` (layout) and `controller.py` (logic) to decouple UI from business logic.
- [x] **Clean up `filter_tracts.py`**: Remove duplicated code blocks and extract file/config helpers to a shared utility module.
- [x] **Centralize Configuration**: Move hardcoded constants (e.g., alignment shifts in `rendering.py`) to external config files (YAML/JSON) to avoid editing source code.
- [x] **Unified Data Manager**: Create a `DataManager` class to handle all file I/O (finding tracts, loading CSVs, saving scenes) centrally.

### 🖥️ GUI & Visualization
- [x] **Legend Toggle Button**: Add a GUI button to optionally load/display the heatmap colorbar (legend) upon rendering, instead of showing it by default.
- [ ] **Click-to-Info**: (Deferred) Select a brain region to see statistics.
- [ ] **2D Slicing**: (Deferred) Coronal/Sagittal views for detailed inspection.

## 🧬 Gene Expression Integration (Planned)

### 1. Dedicated Miner (`src/miner/gene_miner.py`)
- [ ] **API Integration**: Create a separate miner using AllenSDK `MouseGeneExpressionCache` (GridDataApi) distinct from the connectivity miner.
- [ ] **Data Fetching**: Implement downloading of 3D expression volumes (Energy/Density) for specific genes (e.g., *Tph2*, *Slc6a4*).
- [ ] **Storage Strategy**:
    - **Location**: `data/processed/gene_expression/` (separate from `tracts`).
    - **Structure**: Subfolders by Gene Symbol (e.g., `.../gene_expression/tph2/`).
    - **Format**: Save raw `.nrrd` volumes and metadata JSONs.

### 2. Data Processing
- [ ] **Voxelization**: Convert raw continuous expression volumes into discrete voxel coordinates (X, Y, Z, Value) to prepare for "Lego" style rendering.
- [ ] **Thresholding**: Implement logic to filter voxels below a certain expression level to reduce noise and improve performance.

### 3. Visualization (Voxel/Lego Style)
- [ ] **Voxel Actor**: Implement a new rendering mode in `src/viewer/rendering.py` to visualize data as "Lego Blocks" (cubes) matching the [Brainrender style](https://github.com/brainglobe/brainrender).
- [ ] **Colormapping**: Apply gene-specific colormaps (e.g., Red for Gene A, Blue for Gene B) to allow multi-gene comparison.
- [ ] **UI Integration**: Add a "Gene Search" box in the GUI to fetch/load gene data dynamically.

## 🌊 Projection Streamlines (Planned)

### 1. Miner Update (`src/miner/extract_streamlines.py`)
- [ ] **Data Source**: The current volumetric data (`.nrrd`) is **NOT** suitable for streamline visualization. We must fetch vector data (JSON/SWC) from the Allen API.
- [ ] **Implementation**: Add a new script or update `extract_tracts.py` to download `projection_lines` (streamlines) for the experiment ID.
- [ ] **Storage**: Save as `{experiment_id}_streamlines.json` in `data/processed/tracts/`.

### 2. Visualization Logic
- [ ] **Actor Implementation**: Refine the existing (but unused) `Streamlines` logic in `src/viewer/rendering.py` to properly load and render the JSON files.
- [ ] **Styling**: Match the "Brainrender Style" (as seen in the requested image):
    - **Thickness**: Adjust tube radius for visibility.
    - **Coloring**: Allow coloring by target region or injection source.
    - **Opacity**: Implement transparency to see deep structures.
- [ ] **Performance**: Streamlines can be heavy. Implement downsampling (e.g., show only 10% of fibers) if rendering becomes too slow.

## ✅ Completed
- [x] **📦 Modern Packaging**: Implemented `pyproject.toml` and standard installation via `pip install -e .`.
- [x] **🚀 v4.0 Architecture Overhaul**: Centralized logging, robust path management, redundancy removal, and test suite restoration.
- [x] **Native Workflow**: Automatic metadata fixing (`fix_volume_metadata.py`).
- [x] **Alignment System**: Consistent alignment for Raw and Filtered clouds using Fixed Pivot.
- [x] **GUI Redesign**: Improved layout with Top/Bottom bars and CSV auto-detection.
- [x] **Documentation**: Comprehensive `TUTORIAL.md` and updated README.
- [x] **Advanced Testing Suite**: Robust `pytest` integration with Global Mocking for Viewer interactions.
- [x] **Critical Bugfix**: Resolved Projection Cloud Rendering misalignment regression.

## ⚠️ Developer Notes (CRITICAL)
- **Manual Alignment Controls**: The manual shift (`SHIFT_X/Y/Z`) and rotation (`ROTATE_X/Y/Z`) constants in `src/viewer/rendering.py` **MUST BE PRESERVED**. Even if the native workflow works, the user requires the ability to manually fine-tune the alignment at any time. **DO NOT REMOVE THIS LOGIC.**