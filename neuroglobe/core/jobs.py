"""Subprocess supervision shared by desktop GUIs."""

from __future__ import annotations

import subprocess
import threading
import time
from queue import Empty, Queue
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


@dataclass(frozen=True)
class JobResult:
    args: tuple[str, ...]
    returncode: int
    duration_seconds: float = 0.0
    timed_out: bool = False
    cancelled: bool = False

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.cancelled


@dataclass(frozen=True)
class JobProgress:
    elapsed_seconds: float
    lines_emitted: int
    process_id: int


class CancellationToken:
    """Thread-safe cooperative cancellation signal for a supervised process."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()


def _stop_process(process: subprocess.Popen[str], grace_seconds: float) -> int:
    if process.poll() is not None:
        return int(process.returncode)
    process.terminate()
    try:
        return process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        return process.wait()


def run_streaming_job(
    args: Sequence[str],
    *,
    cwd: Path,
    on_output: Callable[[str], None],
    timeout_seconds: float | None = None,
    cancellation_token: CancellationToken | None = None,
    on_progress: Callable[[JobProgress], None] | None = None,
    progress_interval_seconds: float = 0.5,
    terminate_grace_seconds: float = 5.0,
) -> JobResult:
    """Run a child with merged streams, live timeout, progress, and cancellation."""

    if timeout_seconds is not None and timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive when provided.")
    if progress_interval_seconds <= 0:
        raise ValueError("progress_interval_seconds must be positive.")

    command = tuple(str(part) for part in args)
    started_at = time.monotonic()
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
    output_queue: Queue[str | object] = Queue()
    stream_closed = object()

    def read_output() -> None:
        for line in process.stdout:
            output_queue.put(line.rstrip())
        output_queue.put(stream_closed)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    lines_emitted = 0
    reader_finished = False
    timed_out = False
    cancelled = False
    last_progress_at = started_at - progress_interval_seconds

    while True:
        try:
            item = output_queue.get(timeout=min(progress_interval_seconds, 0.1))
        except Empty:
            item = None
        if item is stream_closed:
            reader_finished = True
        elif isinstance(item, str):
            on_output(item)
            lines_emitted += 1

        now = time.monotonic()
        elapsed = now - started_at
        if on_progress is not None and now - last_progress_at >= progress_interval_seconds:
            on_progress(JobProgress(elapsed, lines_emitted, process.pid))
            last_progress_at = now

        if process.poll() is None and cancellation_token is not None:
            if cancellation_token.is_cancelled:
                cancelled = True
                on_output("[CANCELLED] Process cancellation requested.")
                _stop_process(process, terminate_grace_seconds)
        if process.poll() is None and timeout_seconds is not None:
            if elapsed >= timeout_seconds:
                timed_out = True
                on_output("[ERROR] Process timed out and was terminated.")
                _stop_process(process, terminate_grace_seconds)

        if process.poll() is not None and reader_finished and output_queue.empty():
            break

    reader.join(timeout=terminate_grace_seconds)
    returncode = process.wait()
    duration = time.monotonic() - started_at
    if on_progress is not None:
        on_progress(JobProgress(duration, lines_emitted, process.pid))
    return JobResult(
        command,
        returncode,
        duration_seconds=duration,
        timed_out=timed_out,
        cancelled=cancelled,
    )
