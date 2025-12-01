# 🗺️ Project Roadmap

## 🚧 In Progress
- [ ] **Advanced Analysis**: Inter-animal variability, normalized connectivity indices.
- [ ] **Viewer Enhancements**: 
    - [ ] **Click-to-Info**: Select a brain region to see statistics (Currently disabled).
    - [ ] **2D Slicing**: Coronal/Sagittal views.
- [ ] **Multi-Atlas Support**: Support for rat and zebrafish atlases.

## ✅ Completed
- [x] **Native Workflow**: Automatic metadata fixing (`fix_volume_metadata.py`).
- [x] **Alignment System**: Consistent alignment for Raw and Filtered clouds using Fixed Pivot.
- [x] **GUI Redesign**: Improved layout with Top/Bottom bars and CSV auto-detection.
- [x] **Documentation**: Comprehensive `TUTORIAL.md` and updated README.

## ⚠️ Developer Notes (CRITICAL)
- **Manual Alignment Controls**: The manual shift (`SHIFT_X/Y/Z`) and rotation (`ROTATE_X/Y/Z`) constants in `src/viewer/rendering.py` **MUST BE PRESERVED**. Even if the native workflow works, the user requires the ability to manually fine-tune the alignment at any time. **DO NOT REMOVE THIS LOGIC.**