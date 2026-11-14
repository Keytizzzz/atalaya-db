"""Acceso a la base de datos propia del sistema (AtalayaMeta).

Todas las consultas usan parámetros (?) para evitar inyección SQL.
"""
import pyodbc
from flask import current_app, g


def _cadena_conexion():
    c = current_app.config
    return (
        f"DRIVER={{{c['ODBC_DRIVER']}}};"
        f"SERVER={c['META_SERVER']},{c['META_PORT']};"
        f"DATABASE={c['META_DB']};"
        f"UID={c['META_USER']};PWD={c['META_PASSWORD']};"
        "Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=10;"
    )


def obtener_conexion():
    """Una conexión por petición HTTP (se guarda en flask.g)."""
    if "db_meta" not in g:
        g.db_meta = pyodbc.connect(_cadena_conexion(), autocommit=True)
    return g.db_meta


def cerrar_conexion(_=None):
    conn = g.pop("db_meta", None)
    if conn is not None:
        conn.close()


def _ejecutar(cur, sql, params):
    if params:
        cur.execute(sql, params)
    else:
        cur.execute(sql)


def _a_diccionarios(cursor):
    columnas = [col[0] for col in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def consultar(sql, *params):
    """Ejecuta un SELECT y regresa una lista de diccionarios."""
    cur = obtener_conexion().cursor()
    _ejecutar(cur, sql, params)
    return _a_diccionarios(cur)


def consultar_uno(sql, *params):
    filas = consultar(sql, *params)
    return filas[0] if filas else None


def ejecutar(sql, *params):
    """Ejecuta INSERT/UPDATE/DELETE. Regresa el número de filas afectadas."""
    cur = obtener_conexion().cursor()
    _ejecutar(cur, sql, params)
    return cur.rowcount


def insertar(sql, *params):
    """Ejecuta un INSERT con 'OUTPUT INSERTED.id' y regresa el id generado."""
    cur = obtener_conexion().cursor()
    _ejecutar(cur, sql, params)
    fila = cur.fetchone()
    return fila[0] if fila else None
