"""Fábrica de la aplicación Atalaya DB."""
import pyodbc
from flask import Flask, render_template, session

from config import Config


def create_app(config_class=Config, iniciar_recolector=True):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if not app.config["FERNET_KEY"] or app.config["FERNET_KEY"] == "cambia-esto":
        raise RuntimeError("Falta FERNET_KEY en .env. Ejecuta: python scripts/generar_claves.py")

    # --- Conexión a la BD propia: se cierra al terminar cada petición ---
    from app.core import db_meta
    app.teardown_appcontext(db_meta.cerrar_conexion)

    # --- Módulos (blueprints) ---
    # Cada carpeta app/modulos/<nombre>/routes.py que defina "bp" se registra sola.
    # Así cada integrante agrega su módulo sin tocar este archivo (evita conflictos en Git).
    import importlib
    import os

    carpeta_modulos = os.path.join(os.path.dirname(__file__), "modulos")
    for nombre in sorted(os.listdir(carpeta_modulos)):
        if os.path.isfile(os.path.join(carpeta_modulos, nombre, "routes.py")):
            modulo = importlib.import_module(f"app.modulos.{nombre}.routes")
            bp = getattr(modulo, "bp", None)
            if bp is not None and bp.name not in app.blueprints:
                app.register_blueprint(bp)

    # --- Datos disponibles en todas las plantillas ---
    from flask import url_for
    from app.menu import MENU, PUNTOS_ENTRADA

    def _existe(nombre):
        return os.path.exists(os.path.join(app.static_folder, "img", nombre))

    def modulo_listo(clave):
        """Un módulo está listo cuando existe su blueprint (app/modulos/<clave>/routes.py)."""
        return clave in app.blueprints

    def enlace_menu(clave):
        if modulo_listo(clave):
            return url_for(PUNTOS_ENTRADA.get(clave, f"{clave}.principal"))
        return url_for("proximamente.modulo", clave=clave)

    app.jinja_env.globals.update(modulo_listo=modulo_listo, enlace_menu=enlace_menu)

    @app.context_processor
    def datos_globales():
        notificaciones = 0
        if "id_usuario" in session:
            try:
                fila = db_meta.consultar_uno(
                    "SELECT COUNT(*) AS n FROM dbo.notificaciones "
                    "WHERE leida = 0 AND (id_usuario IS NULL OR id_usuario = ?)",
                    session["id_usuario"])
                notificaciones = fila["n"] if fila else 0
            except pyodbc.Error:
                pass
        return {"MENU": MENU, "notificaciones_no_leidas": notificaciones,
                "hay_logo": _existe("logo.png"), "hay_logo_icono": _existe("logo-icono.png"),
                "hay_logo_claro": _existe("logo-claro.png")}

    # --- Manejo de errores amigable ---
    @app.errorhandler(403)
    def prohibido(_):
        return render_template("errores/error.html", codigo=403,
                               mensaje="No tienes permiso para ver esta sección."), 403

    @app.errorhandler(404)
    def no_encontrado(_):
        return render_template("errores/error.html", codigo=404,
                               mensaje="La página que buscas no existe."), 404

    @app.errorhandler(pyodbc.Error)
    def error_bd(e):
        app.logger.exception(e)
        return render_template("errores/error.html", codigo=503,
                               mensaje="No fue posible comunicarse con la base de datos del sistema. "
                                       "Verifica que los contenedores de SQL Server estén encendidos."), 503

    @app.errorhandler(500)
    def error_interno(_):
        return render_template("errores/error.html", codigo=500,
                               mensaje="Ocurrió un error inesperado. Se registró para su revisión."), 500

    if iniciar_recolector:
        from app.servicios import recolector
        recolector.iniciar(app)

    return app
