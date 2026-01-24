# NeuroGlobe 4.0: Comprehensive Manual

**NeuroGlobe** is a complete suite for mining, analyzing, and visualizing mouse brain connectivity data. It bridges the gap between the Allen Brain Atlas API and modern 3D rendering technologies.

---

## 📸 Examples
![Whole brain Serotonine projections](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/Whole%20brain%20Serotonine%20projections.png)
![Filtered Serotonine projections](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/Filtered%20Serotonine%20projections%20in%20cortical%20target%20regions.png)
![Cortical targets Heatmaps](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/Cortical%20targets%20Heatmaps%20of%20Serotonine%20inputs.png)
![Serotonine projections in target regions](https://github.com/DVDGNM99/Python-assignments-main/blob/main/Images/Serotonine%20projections%20in%20target%20regions.png)

---

## ⚙️ Setup & Environments

Why do we need two separate environments?
The **AllenSDK** (used for downloading data) relies on older scientific libraries, whereas **BrainGlobe/Vedo** (used for 3D rendering) requires cutting-edge graphics libraries. To prevent conflicts and crashes, we keep them strictly separated.

### 1. Preparation
Ensure you have **Conda** installed. You will create two spaces:
*   **`allensdk`**: The "Miner". Handles API communication, data downloading, and statistical analysis.
*   **`brainglobe_render`**: The "Viewer". Handles the 3D interactive display.

### 2. Installation Commands
```bash
# 1. Create Miner Environment
conda env create -f envs/allensdk.yml

# 2. Create Viewer Environment
conda env create -f envs/brainglobe_render.yml

# 3. Install Project in Editable Mode (Required for both)
conda activate allensdk
pip install -e .
conda activate brainglobe_render
pip install -e .

# 3. Create Analysis Environment (Optional, for Notebooks)
conda env create -f envs/jupyter_analysis.yml
```

---

## 🚀 Running the Software

The entry point for everything is the **Launcher**.

### Activation
You must activate a compatible environment before starting. Both environments contain the necessary GUI library (`customtkinter`). We recommend starting with `allensdk`:

```bash
conda activate allensdk
python GUI_caller/launcher.py
```

### The Launcher Interface
The Launcher presents you with a choice based on your goal:
1.  **Open Miner GUI**: Choose this if you need to **generate new data**. Use this to search for a new brain region (Seed) or update existing datasets.
2.  **Launch Viewer**: Choose this if you already have data (CSVs and .nrrd files) and want to **visualize** the results immediately. (some demo data is provided in the `data/processed` folder DR_connectivity_filtered.csv, ACA_connectivity_filtered.csv, as well as DR_density.nrrd and ACA_density.nrrd)

---

## ⛏️ The Miner GUI

This tool manages the interface with the Allen Institute.

### 1. Experiment Search
*   **Input Seed**: Enter the acronym of the injection site (e.g., `VISp`, `DR`).
*   **Behavior**: When you run the search, the Miner queries the Allen API for **ALL** available experiments involving that injection site. It does not filter them yet; it retrieves the entire catalog available in the database.
    > ⚠️ **Note**: If the data is not already in your local cache, fetching and aggregating hundreds of experiments can take **dozens of minutes**. Please be patient; the console will update you on progress.
    > ⚠️ **Crucial**: Avoid selecting specific layers (e.g., `MO1`) as they may cause visualization issues. Always choose the Generic Parent (e.g., `MO`). See [TUTORIAL.md - Best Practices](TUTORIAL.md#⚠-best-practices-region-selection-layers-vs-areas) for details.

### 2. Data Processing & Logic (Crucial!)
When you click "Run Pipeline", two distinct extractors work in parallel. It is vital to understand the difference between what you *see* as a cloud and what you *see* as region colors.

#### A. 3D Volume Extraction (The Cloud)
*   **Selection Logic**: For 3D tractography visualization, we cannot average volumes easily on the fly. Therefore, the algorithm automatically identifies the **Single Best Experiment** (the one with the largest injection volume) to serve as the representative "Avatar" for that connection.
*   **Output**: Saves `.nrrd` (Raw density) and `.vtk` (Mesh) files for this specific animal.

#### B. Statistical Aggregation (The Heatmap)
*   **Selection Logic**: For the quantitative data (CSV), the miner uses **ALL** experiments found.
*   **Calculation**: It downloads the projection values for every target region across all N animals and calculates the **Grand Mean** (Average).
*   **Implication**:
    *   **Region Colors** in the Viewer represent the robust, average connectivity across the entire population.
    *   **Projection Cloud** in the Viewer represents the physical pathway of the single best representative animal.
*   *Note: Future updates may implement an "Average Brain" volume, but currently, this hybrid approach offers the best balance of anatomical clarity and statistical robustness.*

### 3. File Generation
The Miner generates several files in `data/processed/`:
*   `{SEED}_connectivity.csv`: The raw statistical average of all regions.
*   `{SEED}_connectivity_filtered.csv`: A cleaned version containing only your specific regions of interest (as defined in `configs/mining_config.yaml`).
*   `tracts/{ID}_density.nrrd`: The 3D volume of the representative experiment.

### 4. Output & Generated Files (`scenes/`)
The **`scenes/`** folder is your gallery.
*   **Purpose**: Stores high-resolution screenshots generated from the Viewer.
*   **Demo Content**: We have included some demo captures (e.g., *Whole brain Serotonine projections*) to show potential results.
*   **How to Save**: See [TUTORIAL.md - Saving Your Work](TUTORIAL.md#4-saving-your-work-screenshots) for instructions on capturing scenes.

---

## 📊 Statistical Analysis

The "Analysis" button in the GUI triggers a post-processing script.

*   **Function**: It takes the raw aggregation data and performs higher-level stats (e.g., calculating Correlation Coefficients, Variability metrics).
*   **Interactive Notebook**:
    For detailed plots, matrices, and charts, use the dedicated Jupyter Notebook:
    *   **File**: `analysis/projection_stats_analysis.ipynb`
    *   **Usage**: Run this notebook *after* the Miner has finished. It loads the generated CSVs and produces publication-ready visualizations (Bar charts of strong targets, Inter-animal variability plots, etc.). future updates will include broader and more detailed analysis, in addition to the present ones.

---

## 🖥️ The Viewer GUI

The Viewer is designed for exploration.

### 1. Top Panel: Data Control
*   **Source**: Dropdown to select which CSV file to load. Defaults to your filtered datasets.
*   **View Mode**: Changes how the regions are colored.
    *   *Mean*: **Symmetric visualization**. It averages the values of Left and Right hemispheres. Useful for general connectivity strength but hides laterality.
    *   *Ipsilateral*: Shows projections to the **same side** as the injection.
    *   *Contralateral*: Shows crossing projections to the **opposite side**.
    *   *Both*: **The Asymmetric Truth**. Splits the brain visualization: the Left side renders Left Hemisphere data, and the Right side renders Right Hemisphere data independently. This allows you to see lateralization (e.g., strong Ipsilateral vs weak Contralateral) simultaneously.

### 2. Manual Controls
*   **+ Region / + Group**: Allows you to manually add brain structures to the scene even if they aren't in your CSV.
*   **Filter Raw Volume**: This button creates a "Masked" version of the tractography cloud. It removes all projections *except* those ending inside your selected regions.

### 3. Bottom Panel: Rendering
*   **Visualization Mode**:
    *   *None*: Statistics only (Region colors).
    *   *Density (Raw)*: The full 3D cloud from the representative animal.
    *   *Density (Filtered)*: The clean, masked cloud focusing on your targets.
*   **Render 3D Scene**: Launches the interactive window.

### 4. Interactive Controls (In-Window)
*   **Rotate/Zoom**: Mouse controls.
*   **Keyboard Shortcuts**:
    *   `X`, `Y`, `Z`: Snap camera to side/front/top views.
    *   `S`: **Save Screenshot**. Saves high-res PNGs to `scenes/`.
