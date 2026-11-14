"""Mecanismos de seguridad de Atalaya DB.

* Contraseñas de USUARIOS de la plataforma -> hash bcrypt (irreversible).
* Contraseñas de SERVIDORES enrolados     -> cifrado Fernet/AES (reversible),
  porque el sistema necesita recuperarlas para conectarse al motor.
"""
import hashlib
import re
import secrets

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


# ---------- Hash de contraseñas (bcrypt) ----------
def hashear_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def validar_fortaleza(password: str):
    """Regresa una lista de errores; vacía si la contraseña es aceptable."""
    errores = []
    if len(password) < 8:
        errores.append("La contraseña debe tener al menos 8 caracteres.")
    if not re.search(r"[A-Z]", password):
        errores.append("La contraseña debe incluir al menos una mayúscula.")
    if not re.search(r"[a-z]", password):
        errores.append("La contraseña debe incluir al menos una minúscula.")
    if not re.search(r"\d", password):
        errores.append("La contraseña debe incluir al menos un número.")
    return errores


# ---------- Cifrado reversible (Fernet) ----------
def _fernet(clave=None):
    clave = clave or current_app.config["FERNET_KEY"]
    return Fernet(clave.encode() if isinstance(clave, str) else clave)


def cifrar(texto: str, clave=None) -> str:
    if not texto:
        return None
    return _fernet(clave).encrypt(texto.encode("utf-8")).decode("utf-8")


def descifrar(texto_cifrado: str, clave=None) -> str:
    if not texto_cifrado:
        return None
    try:
        return _fernet(clave).decrypt(texto_cifrado.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise ValueError("No se pudo descifrar la credencial (¿cambió FERNET_KEY?).")


# ---------- Tokens de recuperación ----------
def generar_token():
    """Regresa (token_en_claro, hash_sha256). Solo el hash se guarda en la BD."""
    token = secrets.token_urlsafe(32)
    return token, hashlib.sha256(token.encode()).hexdigest()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
