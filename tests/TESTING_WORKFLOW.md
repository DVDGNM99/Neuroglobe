# Testing Workflow

This document outlines the standard procedures for running and maintaining the test suite for **NeuroGlobe**.

The project uses [pytest](https://docs.pytest.org/) for testing. The suite is designed to be lightweight and fast, using **mocks** to simulate heavy dependencies (like `brainrender`, `vedo`, and `allensdk` API calls) where appropriate. This allows you to run the entire suite without needing to launch a graphical environment or make live API requests.

---

## 🛠 Prerequisites
The test suite typically runs in the **`allensdk`** Conda environment.

We have created an automated script to handle this for you.

---

## 🚀 Running Tests (The Easy Way)

**Simply run the batch script:**

```bash
.\tests\run_tests.bat
```

This script will:
1. Check if Conda is installed.
2. Automatically enable the `allensdk` environment.
3. Run `pytest` with the correct flags.
4. Report Success or Failure.

### Manual Execution
If you prefer running tests manually:
```bash
conda activate allensdk
pytest
```

> [!NOTE]
> Even though the **Viewer** code runs in the `brainglobe_render` environment in production, the **Tests** for the viewer use mocks for the graphical libraries. Therefore, you do **not** need to switch environments to run the viewer tests. They run perfectly fine in `allensdk`.

---

## 🚀 Running Tests

### 1. Run the Entire Suite
To run all tests in the project, simply execute:

```bash
pytest
```

### 2. Run Specific Modules
You can run tests for specific components to save time:

**Miner Tests:**
```bash
pytest tests/miner
```

**Viewer Tests:**
```bash
pytest tests/viewer
```

**Environment Tests:**
```bash
pytest tests/environments
```

### 3. Verbose Output
To see a detailed list of every test being run and its status:

```bash
pytest -v
```

---

## 📂 Test Structure

The `tests/` directory mirrors the structure of `src/`:

- **`tests/miner/`**: Verifies data fetching and processing logic.
    - `test_fetch.py`: Mocks the Allen SDK to verify API query logic.
    - `test_extract_tracts.py`: Tests the extraction of tractography data.
    - `test_miner_analysis.py`: Verifies statistical calculations.
- **`tests/viewer/`**: Verifies the 3D viewer logic.
    - `test_rendering.py`: Tests the main `RenderEngine` class logic (using mocks).
    - `test_rendering_modes.py`: Verifies different visualization modes (Density, Streamlines).
    - `test_logic.py`: General logic tests.
- **`tests/environments/`**: Verifies that the codebase aligns with the environment definitions.
- **`tests/conftest.py`**: Global configuration. Automatically adds `src/` to the python path so tests can import modules easily.

---

## 📝 Writing New Tests

### General Guidelines
1.  **Scope**: Keep tests small and focused.
2.  **Naming**: Test files must start with `test_`. Test functions must start with `test_`.
3.  **Imports**: You can import directly from `src` (e.g., `from src.miner import fetch`). The `conftest.py` handles the path setup.

### Mocking Dependencies
If you are writing tests for the **Viewer** or **Miner**, avoid making real API calls or creating real 3D windows. Use `unittest.mock`.

**Example: Robust Global Mocking**
When mocking heavy libraries like `vedo` or `brainrender`, it is safer to mock them **globally** using `sys.modules` at the start of your test file, rather than using `patch.dict` context managers which can be brittle with import order.

```python
import sys
from unittest.mock import MagicMock

# 1. Globablly mock the module BEFORE importing your code
sys.modules['vedo'] = MagicMock()
sys.modules['brainrender'] = MagicMock()
sys.modules['brainrender.actors'] = MagicMock()

# 2. Add src to path if needed (or rely on conftest.py)
# ...

# 3. Import your module under test
from src.viewer import my_module

def test_my_function():
    # You can access the mock via sys.modules if needed
    mock_vedo = sys.modules['vedo']
    # ... your test code ...
```

---

## ❌ Troubleshooting

**Error: Module not found 'src'**
- Ensure you are running `pytest` from the **root** of the project (the folder containing `README.md`).
- Do not run `pytest` from inside the `tests/` folder directly (e.g., `cd tests && pytest`).

**Error: specific library missing**
- Double-check you are in the `allensdk` environment: `conda list`.
