# 🗺️ Project Roadmap & Coming Soon

This document tracks planned features, with a focus on items currently visible as "Coming Soon" in the software interface.

---

## 🛑 Urgent Repairs (High Impact)

### 1. Re-enable Viewer Legend
**Status**: Currently disabled in GUI due to crashes ("Legend (Coming Soon)").
**Goal:** Restore the color scalar bar to interpret heatmap values quantitatively.
- [ ] **Fix**: Implement a robust, thread-safe overlay (using `vedo` 2D text or a static image) that doesn't conflict with the `customtkinter` main loop.

---

## 🟡 Medium Complexity (Planned Features)

### 2. Allen Streamlines Integration
**Status**: "Streamlines (Tubes)" mode is currently a placeholder or experimental.
**Goal:** Visualize single-cell-like calculated streamlines to complement density clouds (fMOST style).
- [ ] **Miner Update (`extract_tracts.py`)**: Fetch `projection_lines` (JSON) from Allen API.
- [ ] **Rendering Logic**: Update `rendering.py` to support `.json` actors using `brainrender` style (lines vs meshes).

### 3. Advanced Metrics Aggregation (Miner)
**Status**: In Miner GUI, metrics like "Projection Energy" and "Projection Volume" are marked as "(Coming Soon)".
**Goal:** Allow analysis based on different physical properties of the signal.
- [ ] **Miner Update**: Implement download logic for `projection_energy` volumes.
- [ ] **Aggregation Logic**: Update `aggregate.py` to process these new metric types correctly.

### 4. Variance & Statistical Confidence
**Goal:** Identify reliable biological targets by analyzing inter-animal variability.
- [ ] **Miner Update**: Calculate `std` (standard deviation) alongside `mean`.
- [ ] **Analysis Notebook**: Visualize Confidence (Mean vs Variance) and filter by Coefficient of Variation.

---

## 🟢 Low Complexity (Enhancements)

### Data & Mining
- [ ] **Advanced Metadata Scraping**: Investigate additional fields (e.g., exact injection coordinates, transgenic line info).
- [ ] **2D Image Download**: Fetch high-res 2D images of injection sites.
- [ ] **Smart Caching**: Hash-based checks to prevent re-downloading existing data.

---

## 🔴 High Complexity (Long Term)

### 🧬 Gene Expression Integration
**Goal:** Cross-reference connectivity with Gene Expression Atlas data.
- [ ] **Dedicated Miner (`gene_miner.py`)**: Fetch 3D expression volumes (Energy/Density) for specific genes (*Tph2*, *Slc6a4*).
- [ ] **Lego-Style Visualization**: Implement Voxel rendering mode.
- [ ] **GUI Integration**: "Gene Search" box to load genes dynamically.

---
*Note: This file replaces the previous ROADMAP.md.*