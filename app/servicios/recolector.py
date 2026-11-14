"""Recolector automático de métricas (heartbeat).

Cada RECOLECTOR_INTERVALO segundos recorre los servidores con monitoreo activo,
se conecta, toma una muestra (CPU, memoria, espacio) y la guarda en
metricas_servidor. Ese historial alimenta gráficas, capacidad y predicciones.
"""
import os

from app.core import db_meta
from app.core.conector import ErrorConexion, conectar
from app.servicios import catalogo_sqlserver as cat
from app.servicios import health_score


def tomar_muestra(servidor: dict) -> dict:
    """Se conecta al servidor, guarda una métrica y actualiza su estado.

    Regresa un diccionario con el resultado (ok, score, mensaje).
    """
    id_srv = servidor["id_servidor"]
    estado_anterior = servidor.get("estado_conexion")
    try:
        conn = conectar(servidor, timeout=5)
    except (ErrorConexion, ValueError) as e:
        db_meta.ejecutar(
            "UPDATE dbo.servidores SET estado_conexion = 'ERROR', health_score = 0, "
            "ultimo_chequeo = SYSDATETIME() WHERE id_servidor = ?", id_srv)
        if estado_anterior != "ERROR":
            db_meta.ejecutar(
                "INSERT INTO dbo.notificaciones (id_servidor, tipo, mensaje) VALUES (?, 'danger', ?)",
                id_srv, f"El servidor '{servidor['alias']}' no responde: {e}")
        return {"ok": False, "score": 0, "mensaje": str(e)}

    try:
        cpu = cat.historial_cpu(conn, minutos=1)
        cpu_sql = cpu[-1]["cpu_sql"] if cpu else None
        cpu_otros = cpu[-1]["cpu_otros"] if cpu else None
        espacio = cat.espacio_datos_log(conn)
        volumenes = cat.discos(conn)
        total = sum(float(v["total_mb"]) for v in volumenes) or None
        libre = sum(float(v["libre_mb"]) for v in volumenes) if volumenes else None
        info = cat.info_general(conn)
        excluidas = {f["nombre_bd"] for f in db_meta.consultar(
            "SELECT nombre_bd FROM dbo.bd_excluidas WHERE id_servidor = ?", id_srv)}
        respaldos = [r for r in cat.ultimo_respaldo_por_bd(conn) if r["base_datos"] not in excluidas]
        errores = cat.errores_recientes(conn)
        _guardar_tamanos_bd(conn, id_srv, excluidas)
    finally:
        conn.close()

    alertas = db_meta.consultar_uno(
        "SELECT COUNT(*) AS n FROM dbo.notificaciones WHERE id_servidor = ? AND leida = 0", id_srv)["n"]
    disco_pct = (libre / total * 100) if total else None
    score, detalle = health_score.calcular(
        cpu=cpu_sql, disco_libre_pct=disco_pct, errores_24h=errores, alertas_activas=alertas,
        bd_sin_respaldo=health_score.contar_sin_respaldo(respaldos))

    db_meta.ejecutar(
        """INSERT INTO dbo.metricas_servidor
           (id_servidor, cpu_sql, cpu_otros, memoria_mb, datos_mb, log_mb, disco_total_mb, disco_libre_mb)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        id_srv, cpu_sql, cpu_otros, info.get("memoria_sql_mb"), espacio["datos_mb"],
        espacio["log_mb"], total, libre)
    db_meta.ejecutar(
        """UPDATE dbo.servidores SET estado_conexion = 'OK', health_score = ?, ultimo_heartbeat = SYSDATETIME(),
           ultimo_chequeo = SYSDATETIME(), num_bases_datos = ?, version_motor = ?, edicion = ?
           WHERE id_servidor = ?""",
        score, info["num_bases_datos"], info["version_num"], info["edicion"], id_srv)
    if estado_anterior == "ERROR":
        db_meta.ejecutar(
            "INSERT INTO dbo.notificaciones (id_servidor, tipo, mensaje) VALUES (?, 'success', ?)",
            id_srv, f"El servidor '{servidor['alias']}' volvió a responder.")
    return {"ok": True, "score": score, "detalle": detalle, "mensaje": "Muestra registrada"}


def _guardar_tamanos_bd(conn, id_srv, excluidas, minutos=5):
    """Guarda el tamaño de cada BD (máx. una vez cada 'minutos') para la proyección de crecimiento."""
    ultima = db_meta.consultar_uno(
        "SELECT DATEDIFF(SECOND, MAX(fecha), SYSDATETIME()) AS seg FROM dbo.metricas_bd WHERE id_servidor = ?", id_srv)
    if ultima and ultima["seg"] is not None and ultima["seg"] < minutos * 60:
        return
    for bd in cat.tamanos_bd(conn):
        if bd["nombre"] and bd["nombre"] not in excluidas:
            db_meta.ejecutar("INSERT INTO dbo.metricas_bd (id_servidor, nombre_bd, datos_mb, log_mb) VALUES (?, ?, ?, ?)",
                             id_srv, bd["nombre"], bd["datos_mb"], bd["log_mb"])


def ejecutar_ciclo(app):
    with app.app_context():
        try:
            servidores = db_meta.consultar("SELECT * FROM dbo.servidores WHERE monitoreo_activo = 1")
        except Exception as e:  # noqa: BLE001
            print(f"[recolector] No hay conexión a AtalayaMeta: {e}")
            return
        for srv in servidores:
            try:
                tomar_muestra(srv)
            except Exception as e:  # noqa: BLE001
                print(f"[recolector] Error con {srv['alias']}: {e}")
        db_meta.cerrar_conexion()


def iniciar(app):
    """Arranca el planificador en segundo plano (una sola vez)."""
    # Con el modo debug Flask arranca dos procesos; solo el "hijo" debe recolectar.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    from apscheduler.schedulers.background import BackgroundScheduler

    planificador = BackgroundScheduler(daemon=True)
    planificador.add_job(ejecutar_ciclo, "interval", args=[app],
                         seconds=app.config["RECOLECTOR_INTERVALO"], id="recolector",
                         max_instances=1, coalesce=True)
    planificador.start()
    print(f"[recolector] Activo cada {app.config['RECOLECTOR_INTERVALO']} s")
