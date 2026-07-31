import sys
import threading
import time

from neuroglobe.core.jobs import CancellationToken, run_streaming_job


def test_subprocess_supervisor_merges_streams_and_returns_exit_code(tmp_path):
    output = []
    result = run_streaming_job(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "print('stdout-line'); "
                "print('stderr-line', file=sys.stderr); "
                "raise SystemExit(3)"
            ),
        ],
        cwd=tmp_path,
        on_output=output.append,
    )
    assert result.returncode == 3
    assert set(output) == {"stdout-line", "stderr-line"}


def test_subprocess_supervisor_times_out_while_output_is_open(tmp_path):
    started = time.monotonic()
    result = run_streaming_job(
        [sys.executable, "-u", "-c", "import time; print('started'); time.sleep(10)"],
        cwd=tmp_path,
        on_output=lambda _line: None,
        timeout_seconds=0.2,
        terminate_grace_seconds=0.2,
    )

    assert result.timed_out
    assert not result.succeeded
    assert time.monotonic() - started < 3


def test_subprocess_supervisor_supports_cancellation_and_progress(tmp_path):
    token = CancellationToken()
    progress = []
    timer = threading.Timer(0.2, token.cancel)
    timer.start()
    try:
        result = run_streaming_job(
            [sys.executable, "-u", "-c", "import time; print('started'); time.sleep(10)"],
            cwd=tmp_path,
            on_output=lambda _line: None,
            cancellation_token=token,
            on_progress=progress.append,
            progress_interval_seconds=0.05,
            terminate_grace_seconds=0.2,
        )
    finally:
        timer.cancel()

    assert result.cancelled
    assert not result.succeeded
    assert progress
    assert progress[-1].lines_emitted >= 1
