"""Conexión a las instancias de SQL Server enroladas (servidores monitoreados).

Es la pieza que demuestra la arquitectura cliente-servidor (Unidad 2):
Atalaya DB actúa como cliente que se conecta por TCP/IP, con autenticación
SQL o Windows y con opciones de cifrado TLS.
"""
import pyodbc
from flask import current_app

from app.core.seguridad import descifrar


class ErrorConexion(Exception):
    """Error de conexión con un mensaje entendible para el usuario."""


def construir_cadena(direccion, puerto, tipo_autenticacion, usuario=None, password=None,
                     cifrar_conexion=True, confiar_certificado=True, base_datos="master",
                     timeout=8, driver=None):
    driver = driver or current_app.config["ODBC_DRIVER"]
    partes = [
        f"DRIVER={{{driver}}}",
        f"SERVER={direccion},{int(puerto)}",
        f"DATABASE={base_datos}",
        f"Encrypt={'yes' if cifrar_conexion else 'no'}",
        f"TrustServerCertificate={'yes' if confiar_certificado else 'no'}",
        f"Connection Timeout={timeout}",
        "APP=Atalaya DB",
    ]
    if tipo_autenticacion == "Windows":
        partes.append("Trusted_Connection=yes")
    else:
        partes.append(f"UID={usuario}")
        partes.append("PWD={" + (password or "").replace("}", "}}") + "}")
    return ";".join(partes) + ";"


def traducir_error(e: Exception) -> str:
    """Convierte errores técnicos de ODBC en mensajes claros."""
    texto = str(e)
    if "18456" in texto or "Login failed" in texto:
        return "Usuario o contraseña incorrectos para el servidor."
    if "HYT00" in texto or "Login timeout" in texto or "08001" in texto:
        return "No se pudo alcanzar el servidor. Revisa la dirección, el puerto y que el servicio esté encendido."
    if "certificate" in texto.lower() or "SSL" in texto:
        return "Error de certificado TLS. Activa 'Confiar en el certificado del servidor' o instala un certificado válido."
    if "IM002" in texto or "Data source name not found" in texto:
        return "No se encontró el driver ODBC. Instala 'ODBC Driver 18 for SQL Server'."
    if "Trusted_Connection" in texto or "SSPI" in texto or "Kerberos" in texto:
        return "La autenticación de Windows no está disponible para este servidor."
    return f"Error de conexión: {texto[:300]}"


def conectar_con_parametros(**kwargs):
    try:
        return pyodbc.connect(construir_cadena(**kwargs), autocommit=True)
    except pyodbc.Error as e:
        raise ErrorConexion(traducir_error(e)) from e


def conectar(servidor: dict, base_datos="master", timeout=8):
    """Conecta a un servidor usando el registro guardado en la tabla 'servidores'."""
    return conectar_con_parametros(
        direccion=servidor["direccion"],
        puerto=servidor["puerto"],
        tipo_autenticacion=servidor["tipo_autenticacion"],
        usuario=servidor["usuario"],
        password=descifrar(servidor["password_cifrada"]) if servidor["password_cifrada"] else None,
        cifrar_conexion=bool(servidor["cifrar_conexion"]),
        confiar_certificado=bool(servidor["confiar_certificado"]),
        base_datos=base_datos,
        timeout=timeout,
    )


def consultar(conn, sql, *params):
    """Ejecuta una consulta en la instancia y regresa lista de diccionarios.

    Si el lote tiene varias sentencias (DECLARE, SET...), salta los
    conjuntos de resultados vacíos hasta llegar al que tiene columnas.
    """
    cur = conn.cursor()
    if params:
        cur.execute(sql, params)
    else:
        cur.execute(sql)
    while cur.description is None:
        if not cur.nextset():
            return []
    columnas = [c[0] for c in cur.description]
    return [dict(zip(columnas, fila)) for fila in cur.fetchall()]


def consultar_uno(conn, sql, *params):
    filas = consultar(conn, sql, *params)
    return filas[0] if filas else None
