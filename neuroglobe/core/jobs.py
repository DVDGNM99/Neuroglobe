"""Subprocess supervision shared by desktop GUIs."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


@dataclass(frozen=True)
class JobResult:
    args: tuple[str, ...]
    returncode: int

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


def run_streaming_job(
    args: Sequence[str],
    *,
    cwd: Path,
    on_output: Callable[[str], None],
    timeout_seconds: float | None = None,
) -> JobResult:
    """Run a child with merged streams so neither pipe can deadlock."""

    command = tuple(str(part) for part in args)
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None
    try:
        for line in process.stdout:
            on_output(line.rstrip())
        returncode = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            returncode = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait()
        on_output("[ERROR] Process timed out and was terminated.")
    return JobResult(command, returncode)
