from pathlib import Path
import subprocess


MAX_TRACKED_FILE_BYTES = 1_000_000
DISALLOWED_ARTIFACT_SUFFIXES = {
    ".ipynb",
    ".mhd",
    ".nrrd",
    ".obj",
    ".png",
    ".raw",
    ".tiff",
    ".vtk",
}


def _tracked_files(repository: Path) -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repository.as_posix()}",
            "ls-files",
            "-z",
        ],
        cwd=repository,
        check=True,
        capture_output=True,
    )
    return [repository / path for path in result.stdout.decode().split("\0") if path]


def test_git_index_contains_no_large_or_generated_artifacts():
    repository = Path(__file__).resolve().parents[1]
    violations: list[str] = []
    for path in _tracked_files(repository):
        if not path.is_file():
            continue
        relative = path.relative_to(repository).as_posix()
        size = path.stat().st_size
        if size > MAX_TRACKED_FILE_BYTES:
            violations.append(f"{relative}: {size} bytes")
        if path.suffix.lower() in DISALLOWED_ARTIFACT_SUFFIXES:
            violations.append(f"{relative}: generated artifact")

    assert not violations, "Disallowed Git payload:\n" + "\n".join(violations)
