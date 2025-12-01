import pytest
from pathlib import Path
import yaml

ENV_DIR = Path(__file__).resolve().parent.parent.parent / "envs"

def test_allensdk_env_valid():
    env_file = ENV_DIR / "allensdk.yml"
    # If envs/ is gitignored, the file might still exist locally.
    # We check if it exists.
    if not env_file.exists():
        pytest.skip("Environment file not found (maybe ignored?)")
    
    with open(env_file, "r") as f:
        env = yaml.safe_load(f)
        
    assert "name" in env
    assert "dependencies" in env
    
    # Check for critical packages
    deps = str(env["dependencies"])
    assert "allensdk" in deps or "pip" in deps

def test_brainglobe_env_valid():
    env_file = ENV_DIR / "brainglobe_render.yml"
    if not env_file.exists():
        pytest.skip("Environment file not found")
        
    with open(env_file, "r") as f:
        env = yaml.safe_load(f)
        
    assert "name" in env
    assert "dependencies" in env
    
    deps = str(env["dependencies"])
    assert "brainglobe" in deps or "brainrender" in deps or "vedo" in deps
