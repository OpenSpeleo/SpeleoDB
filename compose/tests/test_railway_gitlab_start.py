from __future__ import annotations

import socket
import subprocess
from pathlib import Path

START: Path = Path(__file__).resolve().parents[1] / "gitlab-railway" / "start"


def run_start_function(function: str, *paths: Path) -> None:
    subprocess.run(  # noqa: S603
        [
            "/bin/bash",
            "-c",
            'source "$1"; shift; "$@"',
            "bash",
            str(START),
            function,
            *(str(path) for path in paths),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_configuration_survives_image_replacement(tmp_path: Path) -> None:
    image: Path = tmp_path / "image-config"
    volume: Path = tmp_path / "data" / "config"
    image.mkdir()
    (image / "gitlab.rb").write_text("original configuration")
    run_start_function("persist_directory", image, volume)
    assert image.is_symlink()
    assert (volume / "gitlab.rb").read_text() == "original configuration"
    (volume / "gitlab-secrets.json").write_text("persistent encryption keys")

    image.unlink()
    image.mkdir()
    (image / "gitlab.rb").write_text("new image defaults")
    run_start_function("persist_directory", image, volume)

    assert (image / "gitlab.rb").read_text() == "original configuration"
    assert (image / "gitlab-secrets.json").read_text() == "persistent encryption keys"


def test_restart_removes_stale_runtime_files_through_symlink(tmp_path: Path) -> None:
    volume: Path = tmp_path / "gitlab"
    database: Path = volume / "postgresql" / "data"
    database.mkdir(parents=True)
    pid: Path = database / "postmaster.pid"
    pid.write_text("123")
    contents: Path = database / "PG_VERSION"
    contents.write_text("17")
    link: Path = tmp_path / "var-opt-gitlab"
    link.symlink_to(volume, target_is_directory=True)
    runtime_socket: Path = volume / "socket.1"
    with socket.socket(socket.AF_UNIX) as connection:
        connection.bind(str(runtime_socket))

    run_start_function("cleanup_runtime_files", link)

    assert not pid.exists()
    assert not runtime_socket.exists()
    assert contents.read_text() == "17"
