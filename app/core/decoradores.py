"""Decoradores de autorización: sesión, rol y acceso por servidor."""
from functools import wraps

from flask import abort, flash, redirect, request, session, url_for

from app.core import db_meta


def login_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if "id_usuario" not in session:
            flash("Inicia sesión para continuar.", "warning")
            return redirect(url_for("auth.login", siguiente=request.path))
        return vista(*args, **kwargs)
    return envoltura


def rol_requerido(*roles):
    def decorador(vista):
        @wraps(vista)
        @login_requerido
        def envoltura(*args, **kwargs):
            if session.get("rol") not in roles:
                abort(403)
            return vista(*args, **kwargs)
        return envoltura
    return decorador


def es_admin():
    return session.get("rol") == "Administrador"


def puede_ver_servidor(id_servidor: int) -> bool:
    if es_admin():
        return True
    fila = db_meta.consultar_uno(
        "SELECT 1 AS ok FROM dbo.usuario_servidor WHERE id_usuario = ? AND id_servidor = ?",
        session.get("id_usuario"), id_servidor,
    )
    return fila is not None


def acceso_servidor(vista):
    """Verifica el checklist de permisos (usuario_servidor) antes de mostrar un servidor."""
    @wraps(vista)
    @login_requerido
    def envoltura(*args, **kwargs):
        id_servidor = kwargs.get("id_servidor")
        if id_servidor is not None and not puede_ver_servidor(id_servidor):
            abort(403)
        return vista(*args, **kwargs)
    return envoltura
