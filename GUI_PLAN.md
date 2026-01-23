# Neuroglobe - GUI Implementation Plan

## 1. Overview
The goal is to implement a user-friendly Graphical User Interface (GUI) system to manage the Neuroglobe workflows. This system will consist of two main components:
1.  **Launcher GUI**: A central entry point to direct the user to the correct tool.
2.  **Miner GUI**: A dedicated interface to manage the data mining, tract extraction, and analysis pipeline.

## 2. Technical Feasibility Analysis

### What IS Possible ✅
*   **Unified Launcher**: A fast, lightweight window to launch other separate processes.
*   **Configurable UI Text**: The Launcher's text will be loaded from an external YAML file, satisfying the requirement for easy editing.
*   **Smart Search / Autocomplete**: `customtkinter` (combined with a library like `CTkScrollableDropdown` or custom logic) allows for real-time filtering of the `regions.json` list as the user types.
*   **Dynamic Lists**: We can easily implement "+" and "-" buttons to manage a list of selected targets.

### What IS NOT Recommended / Difficult ⚠️
*   **Real-time Interactivity within Scripts**: The current scripts (`fetch.py`, etc.) are designed as "batch" jobs. The GUI will configure them and run them, capturing their output, rather than interacting with them mid-process.

---

## 3. Directory Structure
As requested, all GUI-related files and their configurations will be housed in a strictly defined folder.

```
Neuroglobe 4.0/
  GUI_caller/
    __init__.py
    launcher.py        # Main Launcher Script
    miner_gui.py       # Miner Interface Script
    viewer_bridge.py   # Wrapper to launch the existing Viewer
    launcher_text.yaml # Config file for Launcher text/descriptions
    assets/            # Icons, etc.
```

---

## 4. Launcher GUI Design
**Purpose**: Simple, elegant entry point.

### Layout
*   **Title**: "Neuroglobe" (Clean, no version number).
*   **Description Area**:
    *   **Source**: Text is read dynamically from `GUI_caller/launcher_text.yaml`.
    *   **Format**: The YAML will have keys like `welcome_message`, `miner_description`, `viewer_description` to allow easy text updates without code changes.
*   **Buttons**:
    1.  **[ Open Miner GUI ]**
    2.  **[ Launch Viewer ]**

---

## 5. Miner GUI Design
**Purpose**: Smart configuration and execution of the mining pipeline.

### Structure

#### Tab 1: About / Workflow
*   **Content**: Minimalist explanation of the steps (Fetch -> Extract -> Aggregate -> Filter).
*   **Text Source**: Defaults in code, but can optionally be moved to YAML if preferred.

#### Tab 2: Mining Processor (Smart Config)
This tab manages `mining_config.yaml` with advanced user controls.
*   **Seed Selection (Smart Search)**:
    *   **Widget**: Searchable Dropdown / ComboBox.
    *   **Source**: Loads `configs/regions.json`.
    *   **Behavior**: User types "D" -> Dropdown filters to show only regions starting with "D" (e.g., "DR", "DP"). Selecting one auto-fills the configured acronym.
*   **Target Selection (List Management)**:
    *   **Widget**: A list box showing currently selected targets.
    *   **Controls**:
        *   **Smart Dropdown**: Same behavior as Seed (Type to search `regions.json`).
        *   **[ + ] Button**: Adds the selected region from the dropdown to the Target List.
        *   **[ - ] Button**: Removes the selected region from the Target List.
*   **Metric**: Dropdown (`projection_density`, `projection_energy`).
*   **Actions**:
    *   **[ Save Config ]**: Writes to `mining_config.yaml`.
    *   **Pipeline Buttons**:
        1.  **[ 1. Fetch Experiments ]**
        2.  **[ 2. Extract Tracts ]**
        3.  **[ 3. Aggregate & Build ]**
        4.  **[ 4. Filter Results ]** (Updates the CSV based on the current Target List without re-downloading).
*   **Console Output**: Real-time log display.

#### Tab 3: Miner Analysis
This tab is conceptually separate.
*   **Description**: Raw data extraction for statistics.
*   **Controls**: Minimal configuration.
*   **Action**: **[ Run Full Analysis ]** (Executes `miner_analysis.py`).

---

## 6. Technology Stack
*   **Library**: `customtkinter` + `CTkMessagebox` (optional) / Custom Logic for dropdowns.
*   **Config Parsing**: `PyYAML` for reading/writing `launcher_text.yaml` and `mining_config.yaml`.
