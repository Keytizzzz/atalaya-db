"""Operaciones de administración del almacenamiento (Unidad 3).

Todas se ejecutan con T-SQL real sobre la instancia:
  * cambiar el modelo de recuperación     -> ALTER DATABASE ... SET RECOVERY
  * copiar una base de datos              -> BACKUP ... COPY_ONLY + RESTORE ... WITH MOVE
  * generar un snapshot                   -> CREATE DATABASE ... AS SNAPSHOT OF
  * mover archivos de datos / log         -> BACKUP + RESTORE ... WITH MOVE, REPLACE
  * simular crecimiento (para la demo)    -> INSERT masivo en TiendaDemo
"""
import re
from datetime import datetime

from app.servicios.catalogo_sqlserver import archivos_bd, rutas_por_defecto
from app.core.conector import consultar_uno

PATRON_NOMBRE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{0,99}$")
BASES_SISTEMA = {"master", "model", "msdb", "tempdb"}
MODELOS = {"SIMPLE": "Simple", "FULL": "Completo", "BULK_LOGGED": "Con registro masivo"}


class ErrorOperacion(Exception):
    pass


# ----------------------------------------------------------------- utilidades
def _q(nombre: str) -> str:
    """Encierra un identificador entre corchetes de forma segura."""
    return "[" + nombre.replace("]", "]]") + "]"


def _s(texto: str) -> str:
    """Escapa un texto para usarlo como literal N'...'."""
    return "N'" + texto.replace("'", "''") + "'"


def _ejecutar(conn, sql):
    """Ejecuta sentencias administrativas y espera a que terminen.

    BACKUP/RESTORE envían mensajes de avance; hay que consumirlos todos
    (nextset) o pyodbc regresaría antes de que la operación concluya.
    """
    conn.timeout = 900
    cur = conn.cursor()
    cur.execute(sql)
    while cur.nextset():
        pass
    cur.close()


def _validar_existente(conn, nombre, permitir_sistema=False):
    fila = consultar_uno(conn, "SELECT name, source_database_id FROM sys.databases WHERE name = ?", nombre)
    if not fila:
        raise ErrorOperacion(f"La base de datos '{nombre}' no existe.")
    if not permitir_sistema and nombre.lower() in BASES_SISTEMA:
        raise ErrorOperacion("Esta operación no se permite sobre bases de datos del sistema.")
    return fila


def _validar_nuevo(conn, nombre):
    if not PATRON_NOMBRE.match(nombre or ""):
        raise ErrorOperacion("El nombre debe iniciar con letra y solo usar letras, números, guion o guion bajo.")
    if consultar_uno(conn, "SELECT 1 AS x FROM sys.databases WHERE name = ?", nombre):
        raise ErrorOperacion(f"Ya existe una base de datos llamada '{nombre}'.")


def _marca_tiempo():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _extension(archivo):
    if archivo["tipo"] == "LOG":
        return ".ldf"
    return ".mdf" if archivo["file_id"] == 1 else ".ndf"


# ----------------------------------------------------------------- operaciones
def cambiar_recuperacion(conn, nombre, modelo):
    _validar_existente(conn, nombre)
    if modelo not in MODELOS:
        raise ErrorOperacion("Modelo de recuperación no válido.")
    _ejecutar(conn, f"ALTER DATABASE {_q(nombre)} SET RECOVERY {modelo};")
    return f"El modelo de recuperación de '{nombre}' ahora es {MODELOS[modelo]}."


def copiar(conn, origen, destino):
    fila = _validar_existente(conn, origen)
    if fila["source_database_id"] is not None:
        raise ErrorOperacion("No se puede copiar un snapshot.")
    _validar_nuevo(conn, destino)
    rutas = rutas_por_defecto(conn)
    respaldo = f"{rutas['respaldo']}{origen}_copia_{_marca_tiempo()}.bak"
    archivos = archivos_bd(conn, origen)

    _ejecutar(conn, f"BACKUP DATABASE {_q(origen)} TO DISK = {_s(respaldo)} WITH COPY_ONLY, INIT, COMPRESSION;")
    movimientos = ", ".join(
        f"MOVE {_s(a['nombre_logico'])} TO {_s((rutas['log'] if a['tipo'] == 'LOG' else rutas['datos']) + destino + '_' + a['nombre_logico'] + _extension(a))}"
        for a in archivos)
    _ejecutar(conn, f"RESTORE DATABASE {_q(destino)} FROM DISK = {_s(respaldo)} WITH {movimientos}, RECOVERY;")
    return f"Se creó la copia '{destino}' a partir de '{origen}' (respaldo intermedio: {respaldo})."


def crear_snapshot(conn, origen):
    fila = _validar_existente(conn, origen)
    if fila["source_database_id"] is not None:
        raise ErrorOperacion("No se puede crear un snapshot de otro snapshot.")
    rutas = rutas_por_defecto(conn)
    nombre = f"{origen}_snap_{_marca_tiempo()}"
    datos = [a for a in archivos_bd(conn, origen) if a["tipo"] == "ROWS"]
    archivos = ", ".join(
        f"(NAME = {_s(a['nombre_logico'])}, FILENAME = {_s(rutas['datos'] + nombre + '_' + a['nombre_logico'] + '.ss')})"
        for a in datos)
    _ejecutar(conn, f"CREATE DATABASE {_q(nombre)} ON {archivos} AS SNAPSHOT OF {_q(origen)};")
    return f"Snapshot '{nombre}' creado. Es una vista de solo lectura de '{origen}' en este momento."


def eliminar_snapshot(conn, nombre):
    fila = _validar_existente(conn, nombre)
    if fila["source_database_id"] is None:
        raise ErrorOperacion("Por seguridad, aquí solo se pueden eliminar snapshots.")
    _ejecutar(conn, f"DROP DATABASE {_q(nombre)};")
    return f"Snapshot '{nombre}' eliminado."


def mover_archivos(conn, nombre, ruta_datos, ruta_log):
    """Reubica los archivos físicos mediante respaldo + restauración con MOVE.

    En un servidor Windows con acceso al sistema operativo también se puede hacer con
    ALTER DATABASE ... MODIFY FILE + OFFLINE + mover el archivo + ONLINE; este método
    funciona igual en Linux/contenedores porque todo ocurre dentro del motor.
    """
    fila = _validar_existente(conn, nombre)
    if fila["source_database_id"] is not None:
        raise ErrorOperacion("No se pueden mover los archivos de un snapshot.")
    if consultar_uno(conn, "SELECT 1 AS x FROM sys.databases WHERE source_database_id = DB_ID(?)", nombre):
        raise ErrorOperacion("Esta base de datos tiene snapshots. Elimínalos antes de mover sus archivos.")
    rutas = rutas_por_defecto(conn)
    sep = rutas["separador"]
    ruta_datos = (ruta_datos or "").strip()
    ruta_log = (ruta_log or "").strip() or ruta_datos
    if not ruta_datos:
        raise ErrorOperacion("Indica la carpeta destino para los archivos de datos.")
    ruta_datos = ruta_datos if ruta_datos.endswith(sep) else ruta_datos + sep
    ruta_log = ruta_log if ruta_log.endswith(sep) else ruta_log + sep
    if "'" in ruta_datos + ruta_log or ".." in ruta_datos + ruta_log:
        raise ErrorOperacion("La ruta contiene caracteres no permitidos.")

    for carpeta in {ruta_datos, ruta_log}:     # crea la carpeta si no existe
        try:
            _ejecutar(conn, f"EXEC master.dbo.xp_create_subdir {_s(carpeta)};")
        except Exception:  # noqa: BLE001  - si ya existe o no hay permiso, el RESTORE lo reportará
            pass

    archivos = archivos_bd(conn, nombre)
    respaldo = f"{rutas['respaldo']}{nombre}_mover_{_marca_tiempo()}.bak"
    _ejecutar(conn, f"BACKUP DATABASE {_q(nombre)} TO DISK = {_s(respaldo)} WITH COPY_ONLY, INIT, COMPRESSION;")
    movimientos = ", ".join(
        f"MOVE {_s(a['nombre_logico'])} TO {_s((ruta_log if a['tipo'] == 'LOG' else ruta_datos) + a['ruta'].replace(chr(92), '/').split('/')[-1])}"
        for a in archivos)
    try:
        _ejecutar(conn, f"ALTER DATABASE {_q(nombre)} SET SINGLE_USER WITH ROLLBACK IMMEDIATE;")
        _ejecutar(conn, f"RESTORE DATABASE {_q(nombre)} FROM DISK = {_s(respaldo)} WITH {movimientos}, REPLACE, RECOVERY;")
    finally:
        try:
            _ejecutar(conn, f"ALTER DATABASE {_q(nombre)} SET MULTI_USER;")
        except Exception:  # noqa: BLE001
            pass
    return f"Archivos de '{nombre}' reubicados en {ruta_datos} (datos) y {ruta_log} (log)."


def simular_crecimiento(conn, filas=50000):
    """Inserta ventas en TiendaDemo para generar crecimiento real (útil en la demostración)."""
    if not consultar_uno(conn, "SELECT 1 AS x FROM sys.databases WHERE name = 'TiendaDemo'"):
        raise ErrorOperacion("La base TiendaDemo no existe en este servidor (ejecuta scripts/inicializar.py).")
    _ejecutar(conn, f"""
        SET NOCOUNT ON;
        ;WITH n AS (SELECT TOP ({int(filas)}) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
                    FROM sys.all_objects a CROSS JOIN sys.all_objects b)
        INSERT INTO TiendaDemo.dbo.ventas (id_cliente, id_producto, cantidad, total, fecha)
        SELECT (i * 7) % 2000 + 1, (i * 11) % 200 + 1, i % 5 + 1,
               CAST(((i * 37) % 950 + 50) * (i % 5 + 1) AS DECIMAL(12,2)), SYSDATETIME()
        FROM n;""")
    return f"Se insertaron {filas:,} ventas en TiendaDemo para simular crecimiento."
