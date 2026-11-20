# -*- coding: utf-8 -*-

from __future__ import annotations

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from django.apps import AppConfig
from django.conf import settings
from django.core import checks

OIDC_SIGNING_KEY_BITS = 4096


@checks.register("oidc", deploy=True)
def check_oidc_signing_key(**kwargs: object) -> list[checks.Error]:
    pem: str = settings.IDP_OIDC_PRIVATE_KEY
    if not pem.strip():
        reason = "is missing or empty."
    else:
        try:
            key = load_pem_private_key(pem.encode(), password=None)
        except TypeError, ValueError, UnsupportedAlgorithm:
            reason = (
                "is invalid. Expected a complete, unencrypted RSA private key in PEM "
                "format with real line breaks."
            )
        else:
            if not isinstance(key, rsa.RSAPrivateKey):
                reason = (
                    "has the wrong key type. Expected an unencrypted RSA private "
                    "key in PEM format."
                )
            elif key.key_size == OIDC_SIGNING_KEY_BITS:
                return []
            else:
                reason = (
                    f"has {key.key_size} bits. Exactly {OIDC_SIGNING_KEY_BITS} bits "
                    "are required."
                )
    return [
        checks.Error(
            f"DJANGO_OIDC_PRIVATE_KEY {reason}",
            hint=(
                "Generate a key with openssl genpkey -algorithm RSA "
                f"-pkeyopt rsa_keygen_bits:{OIDC_SIGNING_KEY_BITS} and set the full "
                "multiline PEM on the Django web service."
            ),
            id="users.E001",
        )
    ]


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "speleodb.users"
    verbose_name = "Users"

    def ready(self) -> None:
        import speleodb.users.oidc_cors  # noqa: PLC0415
        import speleodb.users.signals  # noqa: F401, PLC0415
