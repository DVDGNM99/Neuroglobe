# Urgent Implementation Plan: Advanced Mining & Visualization

**Status:** Draft / Proposal
**Author:** Antigravity (Assistant)
**Date:** 2025-12-13

This document outlines two high-priority feature requests:
1.  **Hemisphere-Specific Data Aggregation:** Separating Ipsilateral (Right) and Contralateral (Left) connectivity data, avoiding the flattened "Mean" aggregation.
2.  **Allen Streamlines Integration:** Implementing the visualization of single-cell-like calculated streamlines to complement the existing density clouds.

---

## 1. Hemisphere-Specific Data Aggregation

### The Current State (The "Mean" Problem)
Currently, `src/miner/aggregate.py` performs a significant simplification of the data.
When we download data from the Allen API, we receive rows for *structure_unionizes*. Each row contains:
- `structure_id` (The area, e.g., "MOs")
- `hemisphere_id` (1 = Left, 2 = Right, 3 = Bilateral)
- `projection_density` (The value)

**Current Logic:**
```python
# src/miner/aggregate.py
agg_targets = target_df.groupby('acronym')[metric].mean()
```
**What this does:** It takes ALL entries for "MOs" (whether they are Left or Right) and calculates one single average number.
**Consequence:** You lose the ability to see if the projection is strong only in the Ipsilateral side (typical) or if it crosses heavily to the Contralateral side. The visual result in the GUI is a single color per region that represents a "mathematical blend" of both sides.

### Proposed Architecture

#### A. Miner Updates (`aggregate.py`)
We need to stop grouping *only* by acronym and start grouping by **Acronym + Hemisphere**.

**New Logic Concept:**
1.  Filter raw data.
2.  Group by `['acronym', 'hemisphere_id']`.
3.  Pivot the table so that for each `acronym`, we produce three distinct columns (or rows depending on preference):
    - `value_ipsi` (Same side as injection)
    - `value_contra` (Opposite side)
    - `value_mean` (The current average, for backward compatibility)

**Output CSV Structure Change:**
*Current:* `acronym, value, is_seed`
*New:* `acronym, value_mean, value_right, value_left, is_seed`

#### B. GUI Updates (`main.py` / `gui.py`)
The GUI needs to become "Laterality Aware".

**New Features:**
1.  **Aggregation Toggles:** Add a segmented toggle or radio buttons in the "Manual" toolbar:
    - `[ MEAN ]` (Default)
    - `[ IPSI / RIGHT ]`
    - `[ CONTRA / LEFT ]`
2.  **Dynamic Coloring:** When the user switches the toggle:
    - The `ViewerController` reads the corresponding column (e.g., `value_right` instead of `value_mean`).
    - The region colors in the 3D scene update instantly to reflect the connectivity of *that specific hemisphere*.

---

## 2. Allen Streamlines Integration

### The Concept
The "Clouds" we currently render are **Projection Density Volumes** (`.nrrd`). They represent the physical volume of the tracer.
**Streamlines** are mathematically calculated paths derived from this density. They look like "wires" or "neural tracts" and closely resemble the fMOST single-neuron imaging style (though they are still population-level estimates).

### Proposed Architecture

#### A. Miner Script (`fetch_streamlines.py` / update `extract_tracts.py`)
We need a script to fetch the `.json` streamlines file from the Allen API. This is different from the `.nrrd` volume.

**Workflow:**
1.  Identify the `experiment_id`.
2.  Query the URL: `http://api.brain-map.org/api/v2/data/query.json?criteria=model::Tract,rma::criteria,[section_data_set_id$eq{ID}]`
3.  Download the resulting JSON lines.
4.  Save to `data/processed/tracts/{ID}_streamlines.json`.

#### B. Rendering Logic (`rendering.py`)
We need to update the `RenderEngine` to handle `.json` actors.

**New Logic:**
1.  **Loader:** Add a case for `.json` files.
2.  **Actor:** Use `brainrender.actors.Streamlines` (which wraps `vedo`).
3.  **Visualization:**
    - These actors draw lines instead of meshes.
    - We can color them continuously (gradient from seed to target) or solid.
    - **Optimization:** Streamlines can vary in count (100 vs 10,000). We may need a "Downsampling" parameter in the config to prevent the Viewer from lagging if there are too many lines.

---

## 3. Variance & Statistical Confidence (Variability Analysis)

### The Concept
While the "Mean" tells us the average strength of a connection, the **Variance (or Standard Deviation)** tells us how reliable that connection is across individuals.
- **Low Variance:** The connection is robust/constant (hard-wired).
- **High Variance:** The connection varies greatly between individuals or experiments (potential artifacts or biological variability).

### Proposed Architecture

#### A. Miner Updates (`aggregate.py`)
In addition to calculating the `mean`, we will also calculate the standard deviation (`std`).

**New Logic:**
```python
# Group by acronym and calculate both mean and std
agg_targets = target_df.groupby('acronym')[metric].agg(['mean', 'std'])
```

**Output CSV Change:**
Add a `value_std` column to the CSV.

#### B. Utilization (Analysis Notebook)
Instead of cluttering the 3D Viewer with error bars (which is visually messy), we will expose this data in a dedicated **Statistical Analysis Notebook** (`notebooks/statistics.ipynb`).

**Planned Analysis:**
1.  **Scatter Plot (Confidence):** X-axis = Mean Strength, Y-axis = Variance.
    - *Goal:* Identify "Gold Standard" targets (High Mean, Low Variance).
2.  **Filtering:** Allow the user to filter the CSV not just by strength > 0, but by "Coefficient of Variation" (Std/Mean) to remove unstable targets.

### Summary of Urgency & Impact
| Feature | Complexity | Impact on User |
| :--- | :--- | :--- |
| **Hemisphere Logic** | Medium | **High:** Allows scientifically accurate distinction of callosal projections. |
| **Streamlines** | Medium | **High:** Provides the "clean" aesthetic requested, matching fMOST reference style. |
| **Variance/Stats** | Low | **High:** Crucial for selecting reliable biological targets. |
