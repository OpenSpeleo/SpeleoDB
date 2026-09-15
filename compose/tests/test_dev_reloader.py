"""Development code reloads must ignore generated Git and test data."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

RELOADER_PROBE: str = """
import json
import os
import sys
from pathlib import Path

import django
django.setup()

from django.conf import settings
from django_extensions.management.commands.runserver_plus import Command
from werkzeug._reloader import StatReloaderLoop

options = Command().create_parser('manage.py', 'runserver_plus').parse_args([])
assert options.reloader_type == 'stat'
root = Path(sys.argv[1])
source = root / 'application.py'
scratch = root / '.workdir/git_projects/project/generated.py'
scratch.parent.mkdir(parents=True)
source.write_text('SOURCE = 1\\n')
scratch.write_text('GENERATED = 1\\n')
with StatReloaderLoop(
    extra_files=[str(source), str(scratch)],
    exclude_patterns=settings.RUNSERVER_PLUS_EXCLUDE_PATTERNS,
) as reloader:
    assert str(source) in reloader.mtimes
    assert str(scratch) not in reloader.mtimes
    changed_at = source.stat().st_mtime + 10
    os.utime(scratch, (changed_at, changed_at))
    reloader.run_step()
    scratch.unlink()
    reloader.run_step()
    os.utime(source, (changed_at, changed_at))
    try:
        reloader.run_step()
    except SystemExit as changed:
        assert changed.code == 3
    else:
        raise AssertionError('Application code changes must still reload.')
print(json.dumps({'scratch_ignored': True, 'source_reload_preserved': True}))
"""


def test_local_reloader_ignores_scratch_changes_but_reloads_code(
    tmp_path: Path,
) -> None:
    environment: dict[str, str] = os.environ | {
        "DJANGO_SETTINGS_MODULE": "config.settings.local",
        "DJANGO_READ_DOT_ENV_FILE": "False",
        "DJANGO_SECRET_KEY": "reloader-test-only-secret",
    }
    result: subprocess.CompletedProcess[str] = subprocess.run(  # noqa: S603
        [sys.executable, "-c", RELOADER_PROBE, str(tmp_path)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert '"scratch_ignored": true' in result.stdout
    assert '"source_reload_preserved": true' in result.stdout
