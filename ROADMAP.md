# 🗺️ Project Roadmap

## � Urgent Priorities (High Impact)

### 1. Hemisphere-Specific Data Aggregation (Medium Complexity)
**Goal:** Distinguish Ipsilateral (Right) vs. Contralateral (Left) connectivity, avoiding the flattened "Mean".

- [x] **Miner Update (`aggregate.py`)**: Group by `['acronym', 'hemisphere_id']` and pivot to `value_ipsi`, `value_contra`, `value_mean`.
- [x] **GUI Update (`main.py`)**: Add toggle `[ MEAN | IPSI | CONTRA ]` to switch coloring dynamically.
- [x] **Impact**: Allows scientifically accurate distinction of callosal projections.

### 2. Allen Streamlines Integration (Medium Complexity)
**Goal:** Visualize single-cell-like calculated streamlines to complement density clouds (fMOST style).

- [ ] **Miner Update (`extract_tracts.py`)**: Fetch `projection_lines` (JSON) from Allen API.
- [ ] **Rendering Logic**: Update `rendering.py` to support `.json` actors using `brainrender` style (lines vs meshes).
- [ ] **Performance**: Implement downsampling for heavy tracts.

### 3. Variance & Statistical Confidence (Low Complexity)
**Goal:** Identify reliable biological targets by analyzing inter-animal variability.

- [ ] **Miner Update**: Calculate `std` (standard deviation) alongside `mean`.
- [ ] **Analysis Notebook**: Visualize Confidence (Mean vs Variance) and filter by Coefficient of Variation.

---

## 🟢 Low Complexity 

### Data & Mining
- [ ] **Advanced Metadata Scraping**: Investigate additional fields (e.g., exact injection coordinates, transgenic line info).
- [ ] **Metadata Utilization**: Save and use extra metadata for filtering.
- [ ] **2D Image Download**: Fetch high-res 2D images of injection sites.
- [ ] **Smart Caching**: Hash-based checks to prevent re-downloading existing data.

---

## 🟡 Medium Complexity (Enhancements)

### Visualization
- [ ] **Click-to-Info**: (Deferred) Select a brain region to see statistics.
- [ ] **2D Slicing**: (Deferred) Coronal/Sagittal views for detailed inspection.
- [ ] **Multi-Experiment Analysis**: Automate aggregation of datasets (e.g., all males vs females).

---

## 🔴 High Complexity (Long Term)

### 🧬 Gene Expression Integration
**Goal:** Cross-reference connectivity with Gene Expression Atlas data.

- [ ] **Dedicated Miner (`gene_miner.py`)**: Fetch 3D expression volumes (Energy/Density) for specific genes (*Tph2*, *Slc6a4*).
- [ ] **Data Processing**: Voxelize continuous volumes into discrete coordinates.
- [ ] **Lego-Style Visualization**: Implement Voxel/Lego rendering mode (cubes) with gene-specific colormaps.
- [ ] **GUI Integration**: "Gene Search" box to load genes dynamically.

---
*Note: Completed achievements have been archived to keep the roadmap focused.*