"""Development reloads own real child groups and ignore generated/test files."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PROCESS_PROBE = """
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

events, stop = map(Path, sys.argv[1:])
def record(event, **extra):
    with events.open('a') as output:
        output.write(json.dumps({'event': event, **extra}) + '\\n')

if os.environ.get('RELOAD_PROBE_CHILD'):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    print('ready', flush=True)
    while not stop.exists():
        time.sleep(0.02)
    time.sleep(0.2)
    record('child-stopped', pid=os.getpid())
else:
    stop.unlink(missing_ok=True)
    with subprocess.Popen(
        [sys.executable, __file__, str(events), str(stop)],
        env=os.environ | {'RELOAD_PROBE_CHILD': '1'},
        stdout=subprocess.PIPE, text=True,
    ) as child:
        assert child.stdout.readline().strip() == 'ready'
        def shutdown(signum, frame):
            stop.touch()
            child.wait()
            record('stopped', pid=os.getpid())
            raise SystemExit(0)
        signal.signal(signal.SIGINT, shutdown)
        record('ready', pid=os.getpid(), child_pid=child.pid)
        while True:
            signal.pause()
"""


def test_local_worker_and_beat_commands_enable_source_reloading() -> None:
    configuration: dict[str, Any] = yaml.safe_load(
        (REPOSITORY_ROOT / "local.yml").read_text()
    )
    for role in ("worker", "beat"):
        assert configuration["services"][f"celery-{role}"]["command"] == [
            "python",
            "-m",
            "compose.celery.autoreload",
            role,
        ]


def test_reloader_waits_for_children_and_reloads_application_and_overlay_sources(
    tmp_path: Path,
) -> None:
    app: Path = tmp_path / "app"
    source: Path = app / "speleodb" / "task.py"
    library: Path = tmp_path / "overlay" / "survey_lib"
    source.parent.mkdir(parents=True)
    library.mkdir(parents=True)
    source.write_text("VALUE = 1\n")
    (library / "__init__.py").write_text("VALUE = 1\n")
    events: Path = tmp_path / "events.jsonl"
    probe: Path = tmp_path / "process_probe.py"
    probe.write_text(PROCESS_PROBE)
    log_path: Path = tmp_path / "reloader.log"
    command: list[str] = [
        sys.executable,
        "-c",
        "import sys; from pathlib import Path; "
        "from compose.celery.autoreload import run, source_paths; "
        "sys.exit(run(sys.argv[3:], source_paths(Path(sys.argv[1]), sys.argv[2])))",
        str(app),
        str(library.parent),
        sys.executable,
        str(probe),
        str(events),
        str(tmp_path / "stop"),
    ]

    def records() -> list[dict[str, Any]]:
        if not events.exists():
            return []
        return [json.loads(line) for line in events.read_text().splitlines()]

    def wait_for_starts(count: int) -> list[dict[str, Any]]:
        deadline: float = time.monotonic() + 10
        while time.monotonic() < deadline:
            assert process.poll() is None, log_path.read_text()
            found: list[dict[str, Any]] = records()
            if sum(item["event"] == "ready" for item in found) >= count:
                return found
            time.sleep(0.05)
        raise AssertionError(log_path.read_text())

    # The probe replaces only the service command: watcher, filesystem events,
    # native signals, process groups and parent/child shutdown all remain real.
    with (
        log_path.open("w") as output,
        subprocess.Popen(  # noqa: S603
            command, cwd=REPOSITORY_ROOT, stdout=output, stderr=subprocess.STDOUT
        ) as process,
    ):
        try:
            wait_for_starts(1)
            ignored: tuple[str, ...] = (
                "tests/test_task.py",
                ".workdir/generated.py",
                "__pycache__/task.pyc",
            )
            for relative in ignored:
                path: Path = source.parent / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("generated")
            time.sleep(1)
            assert [item["event"] for item in records()] == ["ready"]
            source.write_text("VALUE = 2\n")
            wait_for_starts(2)
            (library / "__init__.py").write_text("VALUE = 2\n")
            observed: list[dict[str, Any]] = wait_for_starts(3)
            assert [item["event"] for item in observed] == [
                "ready",
                "child-stopped",
                "stopped",
                "ready",
                "child-stopped",
                "stopped",
                "ready",
            ]
        finally:
            process.terminate()
            process.wait(timeout=10)
    assert process.returncode == 0, log_path.read_text()
    assert [item["event"] for item in records()][-2:] == ["child-stopped", "stopped"]
    for item in records():
        if item["event"] == "ready":
            assert not Path(f"/proc/{item['pid']}").exists()
            assert not Path(f"/proc/{item['child_pid']}").exists()
