"""Provision the signing key for the local Django OIDC provider."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from dotenv import dotenv_values
from dotenv import set_key

from speleodb.users.apps import OIDC_SIGNING_KEY_BITS


def ensure_local_oidc_key(env_file: Path) -> None:
    name = "DJANGO_OIDC_PRIVATE_KEY"
    if os.environ.get(name, "").strip():
        return
    value = (dotenv_values(env_file, interpolate=False).get(name) or "").strip()
    # The template shows the multiline syntax with this placeholder as its body.
    if value and "<paste all key lines here>" not in value.splitlines():
        return

    key = rsa.generate_private_key(
        public_exponent=65537, key_size=OIDC_SIGNING_KEY_BITS
    )
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    if env_file.exists():
        env_file.chmod(0o600)
    set_key(env_file, name, pem.decode("ascii").rstrip("\n"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("env_file", type=Path)
    ensure_local_oidc_key(parser.parse_args().env_file)
