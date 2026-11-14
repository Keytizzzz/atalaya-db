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
    from app.modulos.auth.routes import bp as auth_bp
    from app.modulos.inicio.routes import bp as inicio_bp
    from app.modulos.servidores.routes import bp as servidores_bp
    from app.modulos.proximamente.routes import bp as proximamente_bp
    from app.modulos.bases_datos.routes import bp as bases_datos_bp
    from app.modulos.capacidad.routes import bp as capacidad_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(inicio_bp)
    app.register_blueprint(servidores_bp)
    app.register_blueprint(proximamente_bp)
    app.register_blueprint(bases_datos_bp)
    app.register_blueprint(capacidad_bp)

    # --- Datos disponibles en todas las plantillas ---
    import os
    from app.menu import MENU

    def _existe(nombre):
        return os.path.exists(os.path.join(app.static_folder, "img", nombre))

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
