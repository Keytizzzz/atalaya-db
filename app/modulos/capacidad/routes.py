"""Planeación de capacidad y proyección de crecimiento (Unidad 3)."""
import pyodbc
from flask import Blueprint, abort, flash, redirect, render_template, url_for

from app.core import bitacora, db_meta, visitas
from app.core.conector import ErrorConexion, conectar
from app.core.decoradores import acceso_servidor, es_admin, login_requerido
from app.core.seleccion import servidor_seleccionado
from app.servicios import capacidad
from app.servicios import catalogo_sqlserver as cat
from app.servicios import operaciones_bd as ops
from app.servicios import recolector

bp = Blueprint("capacidad", __name__, url_prefix="/capacidad")


@bp.route("/")
@login_requerido
def panel():
    servidores, srv = servidor_seleccionado()
    contexto = {"servidores": servidores, "srv": srv, "error": None, "filas": [], "proyeccion": None,
                "grafica": None, "por_bd": []}
    if not srv:
        return render_template("capacidad/panel.html", **contexto)

    # Histórico guardado por el recolector (datos + log de todo el servidor)
    historia = db_meta.consultar(
        """SELECT fecha, ISNULL(datos_mb, 0) + ISNULL(log_mb, 0) AS total_mb FROM dbo.metricas_servidor
           WHERE id_servidor = ? AND fecha >= DATEADD(DAY, -30, SYSDATETIME()) ORDER BY fecha""",
        srv["id_servidor"])
    reg = capacidad.regresion_lineal([(h["fecha"], h["total_mb"]) for h in historia])

    try:
        conn = conectar(srv)
        try:
            m = cat.metricas_capacidad(conn)
            cpu = cat.historial_cpu(conn, minutos=60)
            volumenes = cat.discos(conn)
        finally:
            conn.close()
    except (ErrorConexion, ValueError, pyodbc.Error) as e:
        contexto["error"] = str(e)
        return render_template("capacidad/panel.html", **contexto)

    filas, extra = capacidad.evaluar(m, cpu, volumenes, reg)
    contexto["filas"] = filas

    if reg:
        libre = extra["disco_libre_mb"]
        dias_lleno = (libre / reg["pendiente_dia"]) if reg["pendiente_dia"] > 0 else None
        contexto["proyeccion"] = {
            "pendiente_dia": reg["pendiente_dia"], "actual": reg["actual"], "r2": reg["r2"],
            "horas": reg["horas_historia"], "muestras": reg["muestras"],
            "en_30": reg["en"](30), "en_90": reg["en"](90), "en_180": reg["en"](180),
            "dias_lleno": dias_lleno,
        }
        # Escala de la gráfica: en horas si la historia es corta, en días si es larga
        ahora = historia[-1]["fecha"]
        horas = reg["horas_historia"]
        if horas < 48:
            unidad, divisor = "Horas", 3600
            horizonte = [0] + [round(max(horas, 0.5) * k, 2) for k in (1, 2, 3)]
            proy = [{"x": h, "y": round(reg["en"](h / 24), 2)} for h in horizonte]
        else:
            unidad, divisor = "Días", 86400
            proy = [{"x": d, "y": round(reg["en"](d), 2)} for d in (0, 30, 90, 180)]
        contexto["grafica"] = {
            "unidad": unidad,
            "historia": [{"x": round((h["fecha"] - ahora).total_seconds() / divisor, 4), "y": float(h["total_mb"])}
                         for h in historia],
            "proyeccion": proy,
        }
    elif historia:
        contexto["horas_historia"] = round((historia[-1]["fecha"] - historia[0]["fecha"]).total_seconds() / 3600, 2)

    # Crecimiento por base de datos
    excluidas = {f["nombre_bd"] for f in db_meta.consultar(
        "SELECT nombre_bd FROM dbo.bd_excluidas WHERE id_servidor = ?", srv["id_servidor"])}
    filas_bd = db_meta.consultar(
        """SELECT nombre_bd, fecha, ISNULL(datos_mb, 0) + ISNULL(log_mb, 0) AS total_mb FROM dbo.metricas_bd
           WHERE id_servidor = ? AND fecha >= DATEADD(DAY, -30, SYSDATETIME()) ORDER BY nombre_bd, fecha""",
        srv["id_servidor"])
    por_bd = {}
    for f in filas_bd:
        por_bd.setdefault(f["nombre_bd"], []).append((f["fecha"], f["total_mb"]))
    for nombre, puntos in por_bd.items():
        if nombre in excluidas:
            continue
        r = capacidad.regresion_lineal(puntos)
        contexto["por_bd"].append({
            "nombre": nombre, "actual": float(puntos[-1][1]),
            "por_dia": r["pendiente_dia"] if r else None,
            "en_180": r["en"](180) if r else None, "muestras": len(puntos),
        })
    contexto["por_bd"].sort(key=lambda x: -(x["por_dia"] or 0))

    visitas.registrar_visita("Planeación de capacidad")
    return render_template("capacidad/panel.html", **contexto)


@bp.route("/<int:id_servidor>/simular", methods=["POST"])
@acceso_servidor
def simular(id_servidor):
    if not es_admin():
        abort(403)
    srv = db_meta.consultar_uno("SELECT * FROM dbo.servidores WHERE id_servidor = ?", id_servidor)
    try:
        conn = conectar(srv, timeout=15)
        try:
            mensaje = ops.simular_crecimiento(conn)
        finally:
            conn.close()
        recolector.tomar_muestra(srv)
        bitacora.registrar("SIMULAR_CRECIMIENTO", f"{srv['alias']} · {mensaje}")
        flash(mensaje, "success")
    except (ops.ErrorOperacion, ErrorConexion, pyodbc.Error) as e:
        flash(str(e)[:400], "danger")
    return redirect(url_for("capacidad.panel", servidor=id_servidor))
