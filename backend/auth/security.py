"""
Hash y verificación de contraseña — Argon2id (design.md — D2).

`argon2-cffi` directo, sin `passlib` de por medio (su desarrollo está
efectivamente discontinuado). Argon2id es la recomendación vigente de OWASP
para hash de contraseñas.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Devuelve el hash Argon2id de `password`. Nunca guardar la contraseña en sí."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifica `password` contra `password_hash`.

    Devuelve `False` ante una contraseña incorrecta o un hash mal formado —
    nunca propaga la excepción de `argon2`, para que el llamador no tenga que
    conocer sus tipos de error.
    """
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
