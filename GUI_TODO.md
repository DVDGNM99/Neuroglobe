# Neuroglobe GUI Implementation Checklist

## Phase 1: Setup & Launcher <!-- id: 0 -->
- [x] Create `GUI_caller` directory structure <!-- id: 1 -->
- [x] Create `launcher_text.yaml` with configurable text <!-- id: 2 -->
- [x] Implement `launcher.py` (Main Menu) with `customtkinter` <!-- id: 3 -->
- [ ] Connect Launcher buttons to placeholders for Miner and Viewer <!-- id: 4 -->

## Phase 2: Miner GUI Infrastructure <!-- id: 5 -->
- [x] Create `miner_gui.py` skeleton <!-- id: 6 -->
- [x] Implement "About" Tab (Workflow info) <!-- id: 7 -->
- [x] Implement "Mining Processor" Tab Layout <!-- id: 8 -->

## Phase 3: Smart Configuration (Miner) <!-- id: 9 -->
- [x] Load `regions.json` for autocomplete <!-- id: 10 -->
- [x] Implement Smart Search Dropdown module <!-- id: 11 -->
- [x] Implement Target List management (+/- buttons) <!-- id: 12 -->
- [x] Implement Config Loading/Saving (`mining_config.yaml`) <!-- id: 13 -->

## Phase 4: Process Integration (Miner) <!-- id: 14 -->
- [x] Implement Script Runner (Subprocess management) <!-- id: 15 -->
- [x] Connect "Fetch Experiments" button <!-- id: 16 -->
- [x] Connect "Extract Tracts" button <!-- id: 17 -->
- [x] Connect "Aggregate" button <!-- id: 18 -->
- [x] Connect "Filter" button <!-- id: 19 -->
- [x] Implement Real-time Console Output widget <!-- id: 20 -->

## Phase 5: Finalization <!-- id: 21 -->
- [x] Implement Analysis Tab <!-- id: 22 -->
- [x] Final Integration Test (Launcher -> Miner -> Viewer) <!-- id: 23 -->
