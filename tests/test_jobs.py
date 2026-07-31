import sys

from neuroglobe.core.jobs import run_streaming_job


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
