"""
Tests de hash y verificación de contraseña — Argon2id (tarea 2.1).

spec `autenticacion-medicos` / `registro-medicos` — Requirement: Contraseña
nunca en texto plano.
"""

from backend.auth.security import hash_password, verify_password


def test_el_hash_nunca_contiene_la_contrasena_en_texto_plano():
    contrasena = "ContraseñaSegura123"
    hashed = hash_password(contrasena)
    assert contrasena not in hashed
    assert hashed.startswith("$argon2id$")


def test_verify_acepta_la_contrasena_correcta():
    contrasena = "ContraseñaSegura123"
    hashed = hash_password(contrasena)
    assert verify_password(contrasena, hashed) is True


def test_verify_rechaza_una_contrasena_incorrecta():
    hashed = hash_password("ContraseñaSegura123")
    assert verify_password("otra-contraseña", hashed) is False


def test_verify_rechaza_un_hash_invalido_sin_romper():
    assert verify_password("cualquiera", "no-es-un-hash-valido") is False


def test_dos_hashes_de_la_misma_contrasena_son_distintos():
    """Argon2id salatea: dos hashes de la misma contraseña no coinciden byte a byte."""
    contrasena = "ContraseñaSegura123"
    assert hash_password(contrasena) != hash_password(contrasena)
