"""Administración de bases de datos y almacenamiento (Unidad 3)."""
import pyodbc
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.core import bitacora, db_meta, visitas
from app.core.conector import ErrorConexion, conectar
from app.core.decoradores import acceso_servidor, es_admin, login_requerido
from app.core.seleccion import servidor_seleccionado
from app.servicios import catalogo_sqlserver as cat
from app.servicios import operaciones_bd as ops

bp = Blueprint("bases_datos", __name__, url_prefix="/bases-datos")


def _servidor(id_servidor):
    srv = db_meta.consultar_uno("SELECT * FROM dbo.servidores WHERE id_servidor = ?", id_servidor)
    if not srv:
        abort(404)
    return srv


def _excluidas(id_servidor):
    return {f["nombre_bd"] for f in db_meta.consultar(
        "SELECT nombre_bd FROM dbo.bd_excluidas WHERE id_servidor = ?", id_servidor)}


@bp.route("/")
@login_requerido
def lista():
    servidores, srv = servidor_seleccionado()
    bases, rutas, error = [], None, None
    if srv:
        try:
            conn = conectar(srv)
            try:
                bases = cat.listar_bases_datos(conn)
                rutas = cat.rutas_por_defecto(conn)
            finally:
                conn.close()
        except (ErrorConexion, ValueError, pyodbc.Error) as e:
            error = str(e)
        excluidas = _excluidas(srv["id_servidor"])
        for b in bases:
            b["excluida"] = b["nombre"] in excluidas
    resumen = {
        "total": len([b for b in bases if not b["es_sistema"] and not b["es_snapshot"]]),
        "snapshots": len([b for b in bases if b["es_snapshot"]]),
        "tamano_mb": sum(b["tamano_mb"] for b in bases),
        "memoria_mb": sum(float(b["memoria_mb"]) for b in bases),
    }
    visitas.registrar_visita("Bases de datos")
    return render_template("bases_datos/lista.html", servidores=servidores, srv=srv, bases=bases,
                           rutas=rutas, error=error, resumen=resumen)


@bp.route("/<int:id_servidor>/bd/<nombre>")
@acceso_servidor
def detalle(id_servidor, nombre):
    srv = _servidor(id_servidor)
    try:
        conn = conectar(srv)
        try:
            bases = cat.listar_bases_datos(conn)
            bd = next((b for b in bases if b["nombre"] == nombre), None)
            if not bd:
                abort(404)
            archivos = cat.archivos_bd(conn, nombre)
            rutas = cat.rutas_por_defecto(conn)
            snapshots = [b for b in bases if b["source_database_id"] == bd["database_id"]]
        finally:
            conn.close()
    except (ErrorConexion, ValueError) as e:
        flash(str(e), "danger")
        return redirect(url_for("bases_datos.lista", servidor=id_servidor))
    bd["excluida"] = nombre in _excluidas(id_servidor)
    historial = db_meta.consultar(
        """SELECT TOP 300 fecha, datos_mb, log_mb FROM dbo.metricas_bd
           WHERE id_servidor = ? AND nombre_bd = ? ORDER BY fecha DESC""", id_servidor, nombre)
    historial.reverse()
    visitas.registrar_visita(f"BD · {nombre}")
    return render_template("bases_datos/detalle.html", srv=srv, bd=bd, archivos=archivos, rutas=rutas,
                           snapshots=snapshots, historial=historial, modelos=ops.MODELOS,
                           es_favorito=visitas.es_favorito(request.path))


def _operar(id_servidor, nombre, accion, funcion, *args, volver_a_lista=False):
    """Ejecuta una operación sobre la instancia con manejo de errores y bitácora."""
    if not es_admin():
        abort(403)
    srv = _servidor(id_servidor)
    try:
        conn = conectar(srv, timeout=15)
        try:
            mensaje = funcion(conn, *args)
        finally:
            conn.close()
        bitacora.registrar(accion, f"{srv['alias']} · {nombre} · {mensaje}")
        flash(mensaje, "success")
    except (ops.ErrorOperacion, ErrorConexion, ValueError) as e:
        flash(str(e), "danger")
    except pyodbc.Error as e:
        bitacora.registrar(accion + "_ERROR", f"{srv['alias']} · {nombre} · {e}")
        flash(f"SQL Server rechazó la operación: {str(e)[:400]}", "danger")
    if volver_a_lista:
        return redirect(url_for("bases_datos.lista", servidor=id_servidor))
    return redirect(url_for("bases_datos.detalle", id_servidor=id_servidor, nombre=nombre))


@bp.route("/<int:id_servidor>/bd/<nombre>/recuperacion", methods=["POST"])
@acceso_servidor
def recuperacion(id_servidor, nombre):
    return _operar(id_servidor, nombre, "CAMBIAR_RECUPERACION", ops.cambiar_recuperacion,
                   nombre, request.form.get("modelo", ""))


@bp.route("/<int:id_servidor>/bd/<nombre>/copiar", methods=["POST"])
@acceso_servidor
def copiar(id_servidor, nombre):
    destino = request.form.get("destino", "").strip()
    respuesta = _operar(id_servidor, nombre, "COPIAR_BD", ops.copiar, nombre, destino, volver_a_lista=True)
    return respuesta


@bp.route("/<int:id_servidor>/bd/<nombre>/snapshot", methods=["POST"])
@acceso_servidor
def snapshot(id_servidor, nombre):
    return _operar(id_servidor, nombre, "CREAR_SNAPSHOT", ops.crear_snapshot, nombre)


@bp.route("/<int:id_servidor>/snapshot/<nombre>/eliminar", methods=["POST"])
@acceso_servidor
def eliminar_snapshot(id_servidor, nombre):
    origen = request.form.get("origen", "")
    _operar(id_servidor, nombre, "ELIMINAR_SNAPSHOT", ops.eliminar_snapshot, nombre)
    if origen:
        return redirect(url_for("bases_datos.detalle", id_servidor=id_servidor, nombre=origen))
    return redirect(url_for("bases_datos.lista", servidor=id_servidor))


@bp.route("/<int:id_servidor>/bd/<nombre>/mover", methods=["POST"])
@acceso_servidor
def mover(id_servidor, nombre):
    return _operar(id_servidor, nombre, "MOVER_ARCHIVOS", ops.mover_archivos, nombre,
                   request.form.get("ruta_datos", ""), request.form.get("ruta_log", ""))


@bp.route("/<int:id_servidor>/bd/<nombre>/excluir", methods=["POST"])
@acceso_servidor
def excluir(id_servidor, nombre):
    srv = _servidor(id_servidor)
    if nombre in _excluidas(id_servidor):
        db_meta.ejecutar("DELETE FROM dbo.bd_excluidas WHERE id_servidor = ? AND nombre_bd = ?", id_servidor, nombre)
        bitacora.registrar("BD_INCLUIDA_MONITOREO", f"{srv['alias']} · {nombre}")
        flash(f"'{nombre}' vuelve a estar incluida en el monitoreo.", "info")
    else:
        db_meta.ejecutar("INSERT INTO dbo.bd_excluidas (id_servidor, nombre_bd) VALUES (?, ?)", id_servidor, nombre)
        bitacora.registrar("BD_EXCLUIDA_MONITOREO", f"{srv['alias']} · {nombre}")
        flash(f"'{nombre}' se excluyó del monitoreo (no cuenta para salud ni capacidad).", "warning")
    destino = request.form.get("volver")
    if destino == "lista":
        return redirect(url_for("bases_datos.lista", servidor=id_servidor))
    return redirect(url_for("bases_datos.detalle", id_servidor=id_servidor, nombre=nombre))
