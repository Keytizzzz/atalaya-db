"""Panel general / pantalla de inicio (Unidad 1)."""
from flask import Blueprint, redirect, render_template, request, session, url_for

from app.core import db_meta, visitas
from app.core.decoradores import es_admin, login_requerido

bp = Blueprint("inicio", __name__)


def servidores_visibles():
    """Servidores que el usuario puede ver según su rol y el checklist de acceso."""
    if es_admin():
        return db_meta.consultar("SELECT * FROM dbo.servidores ORDER BY alias")
    return db_meta.consultar(
        """SELECT s.* FROM dbo.servidores s
           JOIN dbo.usuario_servidor us ON us.id_servidor = s.id_servidor
           WHERE us.id_usuario = ? ORDER BY s.alias""", session["id_usuario"])


@bp.route("/")
@login_requerido
def home():
    servidores = servidores_visibles()
    con_score = [s["health_score"] for s in servidores if s["health_score"] is not None]
    resumen = {
        "total": len(servidores),
        "en_linea": sum(1 for s in servidores if s["estado_conexion"] == "OK"),
        "con_error": sum(1 for s in servidores if s["estado_conexion"] == "ERROR"),
        "salud_promedio": round(sum(con_score) / len(con_score)) if con_score else None,
        "bases_datos": sum(s["num_bases_datos"] or 0 for s in servidores),
    }
    pagina_recientes = visitas.recientes()
    pagina_favoritos = visitas.favoritos()
    visitas.registrar_visita("Panel general")
    return render_template("inicio/home.html", resumen=resumen, servidores=servidores,
                           recientes=pagina_recientes, favoritos=pagina_favoritos)


@bp.route("/favorito", methods=["POST"])
@login_requerido
def favorito():
    url = request.form.get("url", "/")
    titulo = request.form.get("titulo", "Página")
    if url.startswith("/"):
        visitas.alternar_favorito(url, titulo)
    return redirect(url if url.startswith("/") else url_for("inicio.home"))


@bp.route("/notificaciones")
@login_requerido
def notificaciones():
    lista = db_meta.consultar(
        """SELECT TOP 100 n.*, s.alias FROM dbo.notificaciones n
           LEFT JOIN dbo.servidores s ON s.id_servidor = n.id_servidor
           WHERE n.id_usuario IS NULL OR n.id_usuario = ? ORDER BY n.fecha DESC""", session["id_usuario"])
    visitas.registrar_visita("Notificaciones")
    return render_template("inicio/notificaciones.html", notificaciones=lista)


@bp.route("/notificaciones/leer", methods=["POST"])
@login_requerido
def marcar_leidas():
    db_meta.ejecutar("UPDATE dbo.notificaciones SET leida = 1 WHERE leida = 0 AND (id_usuario IS NULL OR id_usuario = ?)",
                     session["id_usuario"])
    return redirect(url_for("inicio.notificaciones"))
