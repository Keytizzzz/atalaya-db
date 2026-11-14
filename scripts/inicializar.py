"""Inicializa las bases de datos de Atalaya DB.

    python scripts/inicializar.py

1. Espera a que los contenedores SQL1 y SQL2 estén listos.
2. Crea la BD propia AtalayaMeta (scripts 01, 02 y 03) en SQL1.
3. Crea la BD de demostración TiendaDemo en SQL1 y SQL2.
4. Crea el usuario administrador inicial (contraseña con bcrypt).
"""
import os
import re
import sys
import time
from pathlib import Path

import bcrypt
import pyodbc
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

DRIVER = os.getenv("ODBC_DRIVER", "ODBC Driver 18 for SQL Server")
SA_PASSWORD = os.getenv("SA_PASSWORD")
INSTANCIAS = {"SQL1": ("localhost", 1433), "SQL2": ("localhost", 1434)}


def conectar(host, puerto, intentos=30):
    cadena = (f"DRIVER={{{DRIVER}}};SERVER={host},{puerto};DATABASE=master;UID=sa;PWD={{{SA_PASSWORD}}};"
              "Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=5;")
    for i in range(1, intentos + 1):
        try:
            return pyodbc.connect(cadena, autocommit=True)
        except pyodbc.Error as e:
            print(f"   Esperando a {host}:{puerto} ({i}/{intentos})... {str(e)[:80]}")
            time.sleep(3)
    sys.exit(f"No se pudo conectar a {host}:{puerto}. ¿Ejecutaste 'docker compose up -d'?")


def ejecutar_script(conn, ruta: Path):
    """Ejecuta un archivo .sql separando los lotes por la palabra GO."""
    texto = ruta.read_text(encoding="utf-8")
    lotes = [l for l in re.split(r"^\s*GO\s*$", texto, flags=re.MULTILINE | re.IGNORECASE) if l.strip()]
    cur = conn.cursor()
    for lote in lotes:
        cur.execute(lote)
        while cur.nextset():
            pass
    print(f"   ✔ {ruta.relative_to(RAIZ)} ({len(lotes)} lotes)")


def crear_admin(conn):
    nombre = os.getenv("ADMIN_NOMBRE", "Administrador")
    correo = os.getenv("ADMIN_EMAIL", "admin@atalaya.local").lower()
    password = os.getenv("ADMIN_PASSWORD", "Admin123!")
    cur = conn.cursor()
    cur.execute("USE AtalayaMeta;")
    cur.execute("SELECT 1 FROM dbo.usuarios WHERE correo = ?", correo)
    if cur.fetchone():
        print(f"   ✔ El administrador {correo} ya existía")
        return
    hash_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()
    cur.execute("""INSERT INTO dbo.usuarios (nombre, correo, password_hash, id_rol)
                   SELECT ?, ?, ?, id_rol FROM dbo.roles WHERE nombre = 'Administrador'""",
                nombre, correo, hash_pw)
    print(f"   ✔ Administrador creado: {correo} / {password}  (cámbiala después)")


def main():
    if not SA_PASSWORD:
        sys.exit("Falta SA_PASSWORD en el archivo .env")

    print("1) Conectando a las instancias...")
    conexiones = {n: conectar(*hp) for n, hp in INSTANCIAS.items()}

    print("2) Creando la base de datos propia AtalayaMeta en SQL1...")
    for nombre in ("01_crear_atalayameta.sql", "02_tablas.sql", "03_datos_iniciales.sql"):
        ejecutar_script(conexiones["SQL1"], RAIZ / "database" / nombre)

    print("3) Creando la base de datos de demostración TiendaDemo...")
    for nombre, conn in conexiones.items():
        print(f"   [{nombre}]")
        ejecutar_script(conn, RAIZ / "database" / "demo" / "tienda_demo.sql")

    print("4) Usuario administrador...")
    crear_admin(conexiones["SQL1"])

    for conn in conexiones.values():
        conn.close()
    print("\nListo. Ahora ejecuta:  python run.py   y abre http://127.0.0.1:5000")


if __name__ == "__main__":
    main()
