"""Check the local OIDC setup command against private dotenv files."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from stat import S_IMODE

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from dotenv import dotenv_values

from speleodb.users.apps import OIDC_SIGNING_KEY_BITS

KEY_NAME = "DJANGO_OIDC_PRIVATE_KEY"
ENV_TEMPLATE = Path(__file__).resolve().parents[2] / ".env.dist"


def run_setup(env_file: Path, external_key: str = "") -> None:
    env = os.environ.copy()
    env.pop(KEY_NAME, None)
    if external_key:
        env[KEY_NAME] = external_key
    subprocess.run(  # noqa: S603 - fixed module and test-owned path
        [sys.executable, "-m", "compose.setup_local_oidc", str(env_file)],
        env=env,
        check=True,
        timeout=30,
    )


@pytest.mark.parametrize("initial", ["missing", "empty", "template"])
def test_setup_generates_and_reuses_private_rsa_key(
    tmp_path: Path, initial: str
) -> None:
    env_file = tmp_path / ".env"
    if initial == "template":
        env_file.write_bytes(ENV_TEMPLATE.read_bytes())
    elif initial == "empty":
        env_file.write_text(f"{KEY_NAME}=''\n", encoding="utf-8")
    with env_file.open("a", encoding="utf-8") as stream:
        stream.write("\n# Developer setting\nCUSTOM='line one\nline two'\n")

    run_setup(env_file)
    values = dotenv_values(env_file, interpolate=False)
    assert values["CUSTOM"] == "line one\nline two"
    pem = values[KEY_NAME]
    assert pem
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    assert isinstance(key, rsa.RSAPrivateKey)
    assert key.key_size == OIDC_SIGNING_KEY_BITS
    assert S_IMODE(env_file.stat().st_mode) == 0o600  # noqa: PLR2004

    original = env_file.read_bytes()
    run_setup(env_file)
    unchanged = env_file.read_bytes() == original
    assert unchanged


@pytest.mark.parametrize(
    ("contents", "external_key"),
    [(f"{KEY_NAME}='invalid user-supplied key'\n", ""), ("CUSTOM=value\n", "supplied")],
)
def test_setup_preserves_explicit_configuration(
    tmp_path: Path, contents: str, external_key: str
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(contents, encoding="utf-8")
    run_setup(env_file, external_key)
    assert env_file.read_text(encoding="utf-8") == contents
