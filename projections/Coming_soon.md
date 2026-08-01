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
**Status**: Hidden. AllenSDK does not expose per-experiment axonal streamlines or
a supported `projection_lines` JSON artifact. The old selector implied a data
product that the Miner could not obtain and has been removed from the GUI.

**Goal:** Reconsider tube rendering only after selecting a documented external
tract dataset, coordinate convention, file schema, and validation protocol.
- [ ] **Data contract**: identify a real streamline source and versioned schema.
- [ ] **Scientific validation**: verify registration and anatomical meaning before display.
- [ ] **Rendering Logic**: add an actor only for the validated schema; reject arbitrary JSON.

### 3. Advanced Metrics Aggregation (Miner)
**Status**: Available. The Miner GUI exposes `projection_density`,
`projection_energy`, and `projection_volume`; configuration validation and
aggregation share the same metric contract.

- [x] **Miner Update**: download and validate `projection_energy` NRRD volumes.
- [x] **Aggregation Logic**: aggregate all three Allen unionize metrics.
- [x] **Viewer**: render and filter density or energy volumes.

`projection_volume` is a structure-level unionize measure, not a 3D grid image,
so it is intentionally available in CSV aggregation but not as a volume layer.

### 4. Variance & Statistical Confidence
**Goal:** Identify reliable biological targets by analyzing inter-animal variability.
- [x] **Miner Update**: Calculate N, variance, standard deviation, and CI95 alongside mean.
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
