"""Módulo de autenticación (Unidad 2): login, registro, recuperación de contraseña."""
import re
from datetime import date, datetime, timedelta

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, session, url_for)

from app.core import bitacora, db_meta
from app.core.seguridad import (generar_token, hash_token, hashear_password,
                                validar_fortaleza, verificar_password)

bp = Blueprint("auth", __name__, url_prefix="/auth")

PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if "id_usuario" in session:
        return redirect(url_for("inicio.home"))

    errores, correo = {}, ""
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "")

        if not correo:
            errores["correo"] = "El correo es requerido."
        if not password:
            errores["password"] = "La contraseña es requerida."

        if not errores:
            usuario = db_meta.consultar_uno(
                """SELECT u.*, r.nombre AS rol FROM dbo.usuarios u
                   JOIN dbo.roles r ON r.id_rol = u.id_rol WHERE u.correo = ?""", correo)
            ahora = datetime.now()

            if usuario and usuario["bloqueado_hasta"] and usuario["bloqueado_hasta"] > ahora:
                minutos = int((usuario["bloqueado_hasta"] - ahora).total_seconds() // 60) + 1
                errores["general"] = f"Cuenta bloqueada por intentos fallidos. Intenta en {minutos} min."
            elif not usuario or not verificar_password(password, usuario["password_hash"]):
                errores["general"] = "Correo o contraseña incorrectos."
                if usuario:
                    _registrar_intento_fallido(usuario)
                bitacora.registrar("LOGIN_FALLIDO", f"Correo: {correo}",
                                   id_usuario=usuario["id_usuario"] if usuario else None)
            elif not usuario["activo"]:
                errores["general"] = "Tu cuenta está deshabilitada. Contacta al administrador."
            elif usuario["fecha_expiracion"] and _a_fecha(usuario["fecha_expiracion"]) < date.today():
                errores["general"] = "Tu cuenta expiró. Contacta al administrador."
            else:
                db_meta.ejecutar(
                    "UPDATE dbo.usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL, "
                    "ultimo_acceso = ? WHERE id_usuario = ?", ahora, usuario["id_usuario"])
                session.clear()
                session.permanent = True
                session["id_usuario"] = usuario["id_usuario"]
                session["nombre"] = usuario["nombre"]
                session["correo"] = usuario["correo"]
                session["rol"] = usuario["rol"]
                bitacora.registrar("LOGIN", "Inicio de sesión exitoso", id_usuario=usuario["id_usuario"])
                siguiente = request.args.get("siguiente", "")
                return redirect(siguiente if siguiente.startswith("/") else url_for("inicio.home"))

    return render_template("auth/login.html", errores=errores, correo=correo)


def _a_fecha(valor):
    if isinstance(valor, str):
        return date.fromisoformat(valor[:10])
    return valor.date() if isinstance(valor, datetime) else valor


def _registrar_intento_fallido(usuario):
    intentos = usuario["intentos_fallidos"] + 1
    bloqueo = None
    if intentos >= current_app.config["MAX_INTENTOS_LOGIN"]:
        bloqueo = datetime.now() + timedelta(minutes=current_app.config["MINUTOS_BLOQUEO"])
        intentos = 0
        bitacora.registrar("CUENTA_BLOQUEADA", "Demasiados intentos fallidos",
                           id_usuario=usuario["id_usuario"])
    db_meta.ejecutar("UPDATE dbo.usuarios SET intentos_fallidos = ?, bloqueado_hasta = ? WHERE id_usuario = ?",
                     intentos, bloqueo, usuario["id_usuario"])


@bp.route("/logout")
def logout():
    if "id_usuario" in session:
        bitacora.registrar("LOGOUT", "Cierre de sesión")
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    errores, datos = {}, {}
    if request.method == "POST":
        datos = {k: request.form.get(k, "").strip() for k in ("nombre", "correo")}
        datos["correo"] = datos["correo"].lower()
        password = request.form.get("password", "")
        confirmar = request.form.get("confirmar", "")

        if not datos["nombre"]:
            errores["nombre"] = "El nombre es requerido."
        if not datos["correo"]:
            errores["correo"] = "El correo es requerido."
        elif not PATRON_CORREO.match(datos["correo"]):
            errores["correo"] = "El correo no tiene un formato válido."
        elif db_meta.consultar_uno("SELECT 1 AS x FROM dbo.usuarios WHERE correo = ?", datos["correo"]):
            errores["correo"] = "Ya existe una cuenta con ese correo."
        if not password:
            errores["password"] = "La contraseña es requerida."
        else:
            fallas = validar_fortaleza(password)
            if fallas:
                errores["password"] = " ".join(fallas)
        if password != confirmar:
            errores["confirmar"] = "Las contraseñas no coinciden."

        if not errores:
            id_rol = db_meta.consultar_uno("SELECT id_rol FROM dbo.roles WHERE nombre = 'Usuario'")["id_rol"]
            nuevo_id = db_meta.insertar(
                """INSERT INTO dbo.usuarios (nombre, correo, password_hash, id_rol)
                   OUTPUT INSERTED.id_usuario VALUES (?, ?, ?, ?)""",
                datos["nombre"], datos["correo"], hashear_password(password), id_rol)
            bitacora.registrar("REGISTRO_USUARIO", f"Nueva cuenta: {datos['correo']}", id_usuario=nuevo_id)
            flash("Cuenta creada. Ya puedes iniciar sesión.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/registro.html", errores=errores, datos=datos)


@bp.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    errores, correo = {}, ""
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        if not correo:
            errores["correo"] = "El correo es requerido."
        else:
            usuario = db_meta.consultar_uno("SELECT id_usuario FROM dbo.usuarios WHERE correo = ?", correo)
            if usuario:
                token, token_hash = generar_token()
                db_meta.ejecutar("UPDATE dbo.tokens_recuperacion SET usado = 1 WHERE id_usuario = ?",
                                 usuario["id_usuario"])
                db_meta.ejecutar(
                    "INSERT INTO dbo.tokens_recuperacion (id_usuario, token_hash, expira) VALUES (?, ?, ?)",
                    usuario["id_usuario"], token_hash, datetime.now() + timedelta(minutes=30))
                bitacora.registrar("SOLICITUD_RECUPERACION", correo, id_usuario=usuario["id_usuario"])
                enlace = url_for("auth.restablecer", token=token, _external=True)
                # En producción este enlace se enviaría por correo electrónico.
                # Para la demostración se muestra en pantalla (solo en modo DEBUG).
                if current_app.config["DEBUG"]:
                    flash(f"[Modo demostración] Enlace de recuperación: {enlace}", "secondary")
            flash("Si el correo está registrado, recibirás un enlace para restablecer tu contraseña "
                  "(válido por 30 minutos).", "info")
            return redirect(url_for("auth.login"))
    return render_template("auth/recuperar.html", errores=errores, correo=correo)


@bp.route("/restablecer/<token>", methods=["GET", "POST"])
def restablecer(token):
    registro_token = db_meta.consultar_uno(
        "SELECT * FROM dbo.tokens_recuperacion WHERE token_hash = ? AND usado = 0", hash_token(token))
    if not registro_token or registro_token["expira"] < datetime.now():
        flash("El enlace no es válido o ya expiró. Solicita uno nuevo.", "danger")
        return redirect(url_for("auth.recuperar"))

    errores = {}
    if request.method == "POST":
        password = request.form.get("password", "")
        confirmar = request.form.get("confirmar", "")
        if not password:
            errores["password"] = "La contraseña es requerida."
        else:
            fallas = validar_fortaleza(password)
            if fallas:
                errores["password"] = " ".join(fallas)
        if password != confirmar:
            errores["confirmar"] = "Las contraseñas no coinciden."
        if not errores:
            db_meta.ejecutar(
                "UPDATE dbo.usuarios SET password_hash = ?, intentos_fallidos = 0, bloqueado_hasta = NULL "
                "WHERE id_usuario = ?", hashear_password(password), registro_token["id_usuario"])
            db_meta.ejecutar("UPDATE dbo.tokens_recuperacion SET usado = 1 WHERE id_token = ?",
                             registro_token["id_token"])
            bitacora.registrar("PASSWORD_RESTABLECIDA", "Por enlace de recuperación",
                               id_usuario=registro_token["id_usuario"])
            flash("Contraseña actualizada. Inicia sesión con tu nueva contraseña.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/restablecer.html", errores=errores, token=token)
