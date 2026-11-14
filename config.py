"""Configuración central de Atalaya DB (se lee del archivo .env)."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-inseguro")
    FERNET_KEY = os.getenv("FERNET_KEY", "")
    DEBUG = os.getenv("FLASK_DEBUG", "0") == "1"

    # Base de datos propia del sistema
    META_SERVER = os.getenv("META_SERVER", "localhost")
    META_PORT = int(os.getenv("META_PORT", "1433"))
    META_DB = os.getenv("META_DB", "AtalayaMeta")
    META_USER = os.getenv("META_USER", "sa")
    META_PASSWORD = os.getenv("META_PASSWORD", "")
    ODBC_DRIVER = os.getenv("ODBC_DRIVER", "ODBC Driver 18 for SQL Server")

    # Seguridad de sesión
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8      # 8 horas
    MAX_INTENTOS_LOGIN = 5
    MINUTOS_BLOQUEO = 15

    # Recolector de métricas
    RECOLECTOR_INTERVALO = int(os.getenv("RECOLECTOR_INTERVALO", "60"))
