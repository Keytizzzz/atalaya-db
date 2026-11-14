"""Servidores: enrolamiento (Unidad 2) y vista general / Overview (Unidad 1)."""
from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)

from app.core import bitacora, db_meta, visitas
from app.core.conector import ErrorConexion, conectar, conectar_con_parametros
from app.core.decoradores import acceso_servidor, login_requerido, rol_requerido
from app.core.seguridad import cifrar
from app.modulos.inicio.routes import servidores_visibles
from app.servicios import catalogo_sqlserver as cat
from app.servicios import health_score, recolector

bp = Blueprint("servidores", __name__, url_prefix="/servidores")

PLATAFORMAS = ["On-premise", "Nube", "Contenedor"]
MODOS_ACCESO = ["Directo", "Gateway"]
AUTENTICACIONES = [("SQL", "Autenticación de SQL Server"), ("Windows", "Autenticación de Windows")]


# ----------------------------------------------------------------- utilidades
def _obtener_servidor(id_servidor):
    srv = db_meta.consultar_uno("SELECT * FROM dbo.servidores WHERE id_servidor = ?", id_servidor)
    if not srv:
        abort(404)
    return srv


def _etiquetas_de(id_servidor):
    return db_meta.consultar(
        """SELECT e.* FROM dbo.etiquetas e JOIN dbo.servidor_etiqueta se ON se.id_etiqueta = e.id_etiqueta
           WHERE se.id_servidor = ? ORDER BY e.nombre""", id_servidor)


def _leer_formulario():
    f = request.form
    return {
        "alias": f.get("alias", "").strip(),
        "direccion": f.get("direccion", "").strip(),
        "puerto": f.get("puerto", "1433").strip(),
        "plataforma": f.get("plataforma", ""),
        "modo_acceso": f.get("modo_acceso", ""),
        "tipo_autenticacion": f.get("tipo_autenticacion", ""),
        "usuario": f.get("usuario", "").strip(),
        "password": f.get("password", ""),
        "cifrar_conexion": f.get("cifrar_conexion") == "on",
        "confiar_certificado": f.get("confiar_certificado") == "on",
        "so_usuario": f.get("so_usuario", "").strip(),
        "so_password": f.get("so_password", ""),
    }


def _validar(datos, id_servidor=None, password_guardada=False):
    """Validación de campos obligatorios con mensajes claros."""
    e = {}
    if not datos["alias"]:
        e["alias"] = "El nombre/alias es requerido."
    elif db_meta.consultar_uno("SELECT 1 AS x FROM dbo.servidores WHERE alias = ? AND id_servidor <> ?",
                               datos["alias"], id_servidor or 0):
        e["alias"] = "Ya existe un servidor con ese alias."
    if not datos["direccion"]:
        e["direccion"] = "La dirección del servidor es requerida."
    if not datos["puerto"].isdigit() or not 1 <= int(datos["puerto"]) <= 65535:
        e["puerto"] = "El puerto debe ser un número entre 1 y 65535."
    if datos["plataforma"] not in PLATAFORMAS:
        e["plataforma"] = "Selecciona una plataforma."
    if datos["modo_acceso"] not in MODOS_ACCESO:
        e["modo_acceso"] = "Selecciona un modo de acceso."
    if datos["tipo_autenticacion"] not in dict(AUTENTICACIONES):
        e["tipo_autenticacion"] = "Selecciona el tipo de autenticación."
    elif datos["tipo_autenticacion"] == "SQL":
        if not datos["usuario"]:
            e["usuario"] = "Usuario requerido."
        if not datos["password"] and not password_guardada:
            e["password"] = "Contraseña requerida."
    if datos["so_usuario"] and not datos["so_password"] and not password_guardada:
        e["so_password"] = "Indica la contraseña del usuario del sistema operativo."
    return e


def _probar(datos, password_actual=None):
    """Intenta conectarse con los datos del formulario. Regresa (ok, mensaje, info)."""
    try:
        conn = conectar_con_parametros(
            direccion=datos["direccion"], puerto=int(datos["puerto"]),
            tipo_autenticacion=datos["tipo_autenticacion"], usuario=datos["usuario"],
            password=datos["password"] or password_actual,
            cifrar_conexion=datos["cifrar_conexion"], confiar_certificado=datos["confiar_certificado"])
    except ErrorConexion as ex:
        return False, str(ex), None
    try:
        info = cat.info_general(conn)
    finally:
        conn.close()
    return True, f"Conexión exitosa: {info['instancia']} · SQL Server {info['version_num']} ({info['edicion']})", info


# ---------------------------------------------------------------------- vistas
@bp.route("/")
@login_requerido
def lista():
    servidores = servidores_visibles()
    for s in servidores:
        s["etiquetas"] = _etiquetas_de(s["id_servidor"])
        s["estado_salud"] = health_score.clasificar(s["health_score"])
    visitas.registrar_visita("Servidores")
    return render_template("servidores/lista.html", servidores=servidores)


@bp.route("/nuevo", methods=["GET", "POST"])
@login_requerido
def nuevo():
    datos = {"puerto": "1433", "plataforma": "Contenedor", "modo_acceso": "Directo",
             "tipo_autenticacion": "SQL", "cifrar_conexion": True, "confiar_certificado": True}
    errores, resultado = {}, None

    if request.method == "POST":
        datos = _leer_formulario()
        errores = _validar(datos)
        if not errores:
            ok, mensaje, info = _probar(datos)
            resultado = {"ok": ok, "mensaje": mensaje}
            if ok and request.form.get("accion") == "guardar":
                nuevo_id = db_meta.insertar(
                    """INSERT INTO dbo.servidores
                       (alias, direccion, puerto, plataforma, modo_acceso, tipo_autenticacion, usuario,
                        password_cifrada, cifrar_conexion, confiar_certificado, so_usuario, so_password_cifrada,
                        nombre_instancia, version_motor, edicion, num_bases_datos, estado_conexion, registrado_por)
                       OUTPUT INSERTED.id_servidor
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OK', ?)""",
                    datos["alias"], datos["direccion"], int(datos["puerto"]), datos["plataforma"],
                    datos["modo_acceso"], datos["tipo_autenticacion"], datos["usuario"] or None,
                    cifrar(datos["password"]), datos["cifrar_conexion"], datos["confiar_certificado"],
                    datos["so_usuario"] or None, cifrar(datos["so_password"]),
                    info["instancia"], info["version_num"], info["edicion"], info["num_bases_datos"],
                    session["id_usuario"])
                # Quien registra el servidor obtiene acceso a él automáticamente
                db_meta.ejecutar("INSERT INTO dbo.usuario_servidor (id_usuario, id_servidor) VALUES (?, ?)",
                                 session["id_usuario"], nuevo_id)
                db_meta.ejecutar("INSERT INTO dbo.notificaciones (id_servidor, tipo, mensaje) VALUES (?, 'info', ?)",
                                 nuevo_id, f"Se enroló el servidor '{datos['alias']}'.")
                bitacora.registrar("ENROLAR_SERVIDOR",
                                   f"{datos['alias']} ({datos['direccion']},{datos['puerto']})")
                recolector.tomar_muestra(_obtener_servidor(nuevo_id))
                flash(f"Servidor '{datos['alias']}' enrolado correctamente.", "success")
                return redirect(url_for("servidores.overview", id_servidor=nuevo_id))

    return render_template("servidores/formulario.html", datos=datos, errores=errores, resultado=resultado,
                           plataformas=PLATAFORMAS, modos=MODOS_ACCESO, autenticaciones=AUTENTICACIONES,
                           editando=False)


@bp.route("/<int:id_servidor>/editar", methods=["GET", "POST"])
@acceso_servidor
def editar(id_servidor):
    srv = _obtener_servidor(id_servidor)
    datos = {k: srv[k] for k in ("alias", "direccion", "plataforma", "modo_acceso", "tipo_autenticacion",
                                 "cifrar_conexion", "confiar_certificado")}
    datos.update(puerto=str(srv["puerto"]), usuario=srv["usuario"] or "", so_usuario=srv["so_usuario"] or "")
    errores, resultado = {}, None

    if request.method == "POST":
        datos = _leer_formulario()
        errores = _validar(datos, id_servidor=id_servidor, password_guardada=True)
        if not errores:
            from app.core.seguridad import descifrar
            actual = descifrar(srv["password_cifrada"]) if srv["password_cifrada"] else None
            ok, mensaje, info = _probar(datos, password_actual=actual)
            resultado = {"ok": ok, "mensaje": mensaje}
            if ok and request.form.get("accion") == "guardar":
                db_meta.ejecutar(
                    """UPDATE dbo.servidores SET alias = ?, direccion = ?, puerto = ?, plataforma = ?, modo_acceso = ?,
                       tipo_autenticacion = ?, usuario = ?, cifrar_conexion = ?, confiar_certificado = ?,
                       so_usuario = ?, version_motor = ?, edicion = ?, nombre_instancia = ?
                       WHERE id_servidor = ?""",
                    datos["alias"], datos["direccion"], int(datos["puerto"]), datos["plataforma"],
                    datos["modo_acceso"], datos["tipo_autenticacion"], datos["usuario"] or None,
                    datos["cifrar_conexion"], datos["confiar_certificado"], datos["so_usuario"] or None,
                    info["version_num"], info["edicion"], info["instancia"], id_servidor)
                if datos["password"]:
                    db_meta.ejecutar("UPDATE dbo.servidores SET password_cifrada = ? WHERE id_servidor = ?",
                                     cifrar(datos["password"]), id_servidor)
                if datos["so_password"]:
                    db_meta.ejecutar("UPDATE dbo.servidores SET so_password_cifrada = ? WHERE id_servidor = ?",
                                     cifrar(datos["so_password"]), id_servidor)
                bitacora.registrar("EDITAR_SERVIDOR", datos["alias"])
                flash("Servidor actualizado.", "success")
                return redirect(url_for("servidores.overview", id_servidor=id_servidor))

    return render_template("servidores/formulario.html", datos=datos, errores=errores, resultado=resultado,
                           plataformas=PLATAFORMAS, modos=MODOS_ACCESO, autenticaciones=AUTENTICACIONES,
                           editando=True, srv=srv)


@bp.route("/<int:id_servidor>")
@acceso_servidor
def overview(id_servidor):
    srv = _obtener_servidor(id_servidor)
    muestra = recolector.tomar_muestra(srv) if srv["monitoreo_activo"] else None
    srv = _obtener_servidor(id_servidor)       # recarga con el estado actualizado

    info, espacio, volumenes, cpu, respaldos, error = None, None, [], [], [], None
    try:
        conn = conectar(srv)
        try:
            info = cat.info_general(conn)
            espacio = cat.espacio_datos_log(conn)
            volumenes = cat.discos(conn)
            cpu = cat.historial_cpu(conn, minutos=60)
            respaldos = cat.ultimo_respaldo_por_bd(conn)
        finally:
            conn.close()
    except (ErrorConexion, ValueError) as ex:
        error = str(ex)

    todas = db_meta.consultar("SELECT * FROM dbo.etiquetas ORDER BY nombre")
    visitas.registrar_visita(f"Overview · {srv['alias']}")
    return render_template(
        "servidores/overview.html", srv=srv, info=info, espacio=espacio, volumenes=volumenes,
        cpu=cpu, respaldos=respaldos, error=error, etiquetas=_etiquetas_de(id_servidor), todas_etiquetas=todas,
        detalle_score=(muestra or {}).get("detalle", []), estado_salud=health_score.clasificar(srv["health_score"]),
        es_favorito=visitas.es_favorito(request.path))


@bp.route("/<int:id_servidor>/metricas.json")
@acceso_servidor
def metricas_json(id_servidor):
    """Historial guardado por el recolector (para gráficas y la proyección futura)."""
    filas = db_meta.consultar(
        """SELECT TOP 500 fecha, cpu_sql, memoria_mb, datos_mb, log_mb, disco_libre_mb
           FROM dbo.metricas_servidor WHERE id_servidor = ? ORDER BY fecha DESC""", id_servidor)
    for f in filas:
        f["fecha"] = f["fecha"].isoformat()
        for k in ("datos_mb", "log_mb", "disco_libre_mb"):
            f[k] = float(f[k]) if f[k] is not None else None
    return jsonify(list(reversed(filas)))


@bp.route("/<int:id_servidor>/etiquetas", methods=["POST"])
@acceso_servidor
def agregar_etiqueta(id_servidor):
    srv = _obtener_servidor(id_servidor)
    nombre = request.form.get("nueva", "").strip()
    id_etiqueta = request.form.get("id_etiqueta", "")
    if nombre:
        existente = db_meta.consultar_uno("SELECT id_etiqueta FROM dbo.etiquetas WHERE nombre = ?", nombre)
        id_etiqueta = existente["id_etiqueta"] if existente else db_meta.insertar(
            "INSERT INTO dbo.etiquetas (nombre) OUTPUT INSERTED.id_etiqueta VALUES (?)", nombre[:50])
    if id_etiqueta:
        if not db_meta.consultar_uno("SELECT 1 AS x FROM dbo.servidor_etiqueta WHERE id_servidor = ? AND id_etiqueta = ?",
                                     id_servidor, int(id_etiqueta)):
            db_meta.ejecutar("INSERT INTO dbo.servidor_etiqueta (id_servidor, id_etiqueta) VALUES (?, ?)",
                             id_servidor, int(id_etiqueta))
            bitacora.registrar("ETIQUETA_AGREGADA", f"{srv['alias']} · etiqueta {id_etiqueta}")
    return redirect(url_for("servidores.overview", id_servidor=id_servidor))


@bp.route("/<int:id_servidor>/etiquetas/<int:id_etiqueta>/quitar", methods=["POST"])
@acceso_servidor
def quitar_etiqueta(id_servidor, id_etiqueta):
    db_meta.ejecutar("DELETE FROM dbo.servidor_etiqueta WHERE id_servidor = ? AND id_etiqueta = ?",
                     id_servidor, id_etiqueta)
    bitacora.registrar("ETIQUETA_QUITADA", f"Servidor {id_servidor} · etiqueta {id_etiqueta}")
    return redirect(url_for("servidores.overview", id_servidor=id_servidor))


@bp.route("/<int:id_servidor>/monitoreo", methods=["POST"])
@acceso_servidor
def alternar_monitoreo(id_servidor):
    srv = _obtener_servidor(id_servidor)
    nuevo = 0 if srv["monitoreo_activo"] else 1
    db_meta.ejecutar("UPDATE dbo.servidores SET monitoreo_activo = ? WHERE id_servidor = ?", nuevo, id_servidor)
    bitacora.registrar("MONITOREO_" + ("ACTIVADO" if nuevo else "PAUSADO"), srv["alias"])
    flash(f"Monitoreo {'activado' if nuevo else 'pausado'} para '{srv['alias']}'.", "info")
    return redirect(url_for("servidores.overview", id_servidor=id_servidor))


@bp.route("/<int:id_servidor>/eliminar", methods=["POST"])
@rol_requerido("Administrador")
def eliminar(id_servidor):
    srv = _obtener_servidor(id_servidor)
    db_meta.ejecutar("DELETE FROM dbo.servidores WHERE id_servidor = ?", id_servidor)
    bitacora.registrar("ELIMINAR_SERVIDOR", srv["alias"])
    flash(f"Servidor '{srv['alias']}' eliminado de Atalaya DB.", "warning")
    return redirect(url_for("servidores.lista"))
