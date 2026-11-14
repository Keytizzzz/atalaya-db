"""Consultas de catálogo y vistas de administración dinámica (DMV) de SQL Server.

Todas son de solo lectura. Cada función recibe una conexión abierta a la
instancia (ver app/core/conector.py).
"""
from app.core.conector import consultar, consultar_uno


def info_general(conn):
    """Datos para la vista Overview (Unidad 1)."""
    info = consultar_uno(conn, """
        SET NOCOUNT ON;
        SELECT
            CAST(SERVERPROPERTY('MachineName')     AS NVARCHAR(128)) AS host,
            CAST(SERVERPROPERTY('ServerName')      AS NVARCHAR(128)) AS instancia,
            CAST(SERVERPROPERTY('Edition')         AS NVARCHAR(128)) AS edicion,
            CAST(SERVERPROPERTY('ProductVersion')  AS NVARCHAR(128)) AS version_num,
            CAST(SERVERPROPERTY('ProductLevel')    AS NVARCHAR(128)) AS nivel,
            CAST(SERVERPROPERTY('Collation')       AS NVARCHAR(128)) AS intercalacion,
            CAST(CONNECTIONPROPERTY('local_net_address') AS NVARCHAR(50)) AS ip,
            CAST(CONNECTIONPROPERTY('local_tcp_port')    AS NVARCHAR(10)) AS puerto_tcp,
            LEFT(@@VERSION, CHARINDEX(CHAR(10), @@VERSION + CHAR(10)) - 1) AS version_texto,
            (SELECT COUNT(*) FROM sys.databases WHERE database_id > 4) AS num_bases_datos
    """)
    sistema = consultar_uno(conn, """
        SELECT cpu_count                     AS nucleos,
               physical_memory_kb / 1024     AS memoria_total_mb,
               sqlserver_start_time          AS hora_arranque
        FROM sys.dm_os_sys_info
    """)
    so = consultar_uno(conn, """
        SELECT host_platform AS plataforma_so,
               host_distribution AS distribucion_so,
               host_release AS version_so
        FROM sys.dm_os_host_info
    """)
    memoria = consultar_uno(conn, """
        SELECT physical_memory_in_use_kb / 1024 AS memoria_sql_mb
        FROM sys.dm_os_process_memory
    """)
    for parte in (sistema, so, memoria):
        info.update(parte or {})
    return info


def espacio_datos_log(conn):
    """Espacio asignado a archivos de datos vs log (gráfica de dona)."""
    filas = consultar(conn, """
        SELECT type_desc AS tipo, CAST(SUM(CAST(size AS BIGINT)) * 8 / 1024.0 AS DECIMAL(18,2)) AS mb
        FROM sys.master_files
        GROUP BY type_desc
    """)
    datos = sum(float(f["mb"]) for f in filas if f["tipo"] == "ROWS")
    log = sum(float(f["mb"]) for f in filas if f["tipo"] == "LOG")
    return {"datos_mb": round(datos, 2), "log_mb": round(log, 2)}


def discos(conn):
    """Volúmenes donde viven los archivos de las bases de datos."""
    return consultar(conn, """
        SELECT DISTINCT
            vs.volume_mount_point AS volumen,
            CAST(vs.total_bytes     / 1048576.0 AS DECIMAL(18,2)) AS total_mb,
            CAST(vs.available_bytes / 1048576.0 AS DECIMAL(18,2)) AS libre_mb
        FROM sys.master_files mf
        CROSS APPLY sys.dm_os_volume_stats(mf.database_id, mf.file_id) vs
    """)


def historial_cpu(conn, minutos=60):
    """Uso de CPU por minuto (SQL Server guarda ~256 min en el ring buffer)."""
    filas = consultar(conn, f"""
        SET NOCOUNT ON;
        DECLARE @ahora BIGINT = (SELECT ms_ticks FROM sys.dm_os_sys_info);
        SELECT TOP ({int(minutos)})
            DATEADD(ms, -1 * (@ahora - [timestamp]), GETDATE()) AS fecha,
            registro.value('(./Record/SchedulerMonitorEvent/SystemHealth/ProcessUtilization)[1]', 'int') AS cpu_sql,
            registro.value('(./Record/SchedulerMonitorEvent/SystemHealth/SystemIdle)[1]', 'int') AS cpu_libre
        FROM (
            SELECT [timestamp], CONVERT(XML, record) AS registro
            FROM sys.dm_os_ring_buffers
            WHERE ring_buffer_type = N'RING_BUFFER_SCHEDULER_MONITOR'
              AND record LIKE N'%<SystemHealth>%'
        ) AS x
        ORDER BY fecha DESC
    """)
    filas.reverse()
    for f in filas:
        libre = f["cpu_libre"] or 0
        f["cpu_otros"] = max(0, 100 - libre - (f["cpu_sql"] or 0)) if libre else 0
        f["hora"] = f["fecha"].strftime("%H:%M")
    return filas


def ultimo_respaldo_por_bd(conn):
    """Último respaldo completo de cada base de datos de usuario."""
    return consultar(conn, """
        SELECT d.name AS base_datos, d.recovery_model_desc AS modelo_recuperacion,
               MAX(b.backup_finish_date) AS ultimo_respaldo
        FROM sys.databases d
        LEFT JOIN msdb.dbo.backupset b ON b.database_name = d.name AND b.type = 'D'
        WHERE d.database_id > 4 AND d.source_database_id IS NULL
        GROUP BY d.name, d.recovery_model_desc
        ORDER BY d.name
    """)


def errores_recientes(conn, horas=24):
    """Cuenta errores de severidad alta del log de SQL Server (aprox.)."""
    try:
        filas = consultar(conn, "SET NOCOUNT ON; EXEC sys.xp_readerrorlog 0, 1, N'Severity';")
    except Exception:  # noqa: BLE001  (requiere permisos de sysadmin)
        return 0
    from datetime import datetime, timedelta
    limite = datetime.now() - timedelta(hours=horas)
    return sum(1 for f in filas if f.get("LogDate") and f["LogDate"] >= limite)


# =====================================================================
#  UNIDAD 3 · Bases de datos y espacio en disco
# =====================================================================
def listar_bases_datos(conn):
    """Bases de datos con modelo de recuperación, estado, tamaño, memoria, CPU e IO Stall."""
    filas = consultar(conn, """
        SET NOCOUNT ON;
        WITH tam AS (
            SELECT database_id,
                   SUM(CASE WHEN type = 0 THEN CAST(size AS BIGINT) ELSE 0 END) * 8 / 1024.0 AS datos_mb,
                   SUM(CASE WHEN type = 1 THEN CAST(size AS BIGINT) ELSE 0 END) * 8 / 1024.0 AS log_mb
            FROM sys.master_files GROUP BY database_id
        ), mem AS (
            SELECT database_id, COUNT_BIG(*) * 8 / 1024.0 AS memoria_mb
            FROM sys.dm_os_buffer_descriptors GROUP BY database_id
        ), io AS (
            SELECT database_id, SUM(io_stall) AS io_stall_ms,
                   SUM(num_of_reads + num_of_writes) AS operaciones
            FROM sys.dm_io_virtual_file_stats(NULL, NULL) GROUP BY database_id
        ), cpu AS (
            SELECT CONVERT(INT, pa.value) AS database_id, SUM(qs.total_worker_time) / 1000 AS cpu_ms
            FROM sys.dm_exec_query_stats qs
            CROSS APPLY sys.dm_exec_plan_attributes(qs.plan_handle) pa
            WHERE pa.attribute = 'dbid'
            GROUP BY CONVERT(INT, pa.value)
        )
        SELECT d.database_id, d.name AS nombre, d.recovery_model_desc AS modelo_recuperacion,
               d.state_desc AS estado, d.source_database_id, d.create_date AS fecha_creacion,
               d.compatibility_level AS compatibilidad,
               CAST(ISNULL(t.datos_mb, 0) AS DECIMAL(18,2)) AS datos_mb,
               CAST(ISNULL(t.log_mb, 0)   AS DECIMAL(18,2)) AS log_mb,
               CAST(ISNULL(m.memoria_mb, 0) AS DECIMAL(18,2)) AS memoria_mb,
               ISNULL(c.cpu_ms, 0) AS cpu_ms,
               ISNULL(i.io_stall_ms, 0) AS io_stall_ms,
               ISNULL(i.operaciones, 0) AS operaciones
        FROM sys.databases d
        LEFT JOIN tam t ON t.database_id = d.database_id
        LEFT JOIN mem m ON m.database_id = d.database_id
        LEFT JOIN io  i ON i.database_id = d.database_id
        LEFT JOIN cpu c ON c.database_id = d.database_id
        ORDER BY CASE WHEN d.database_id <= 4 THEN 1 ELSE 0 END, d.name
    """)
    total_cpu = sum(int(f["cpu_ms"] or 0) for f in filas) or 1
    for f in filas:
        f["tamano_mb"] = float(f["datos_mb"]) + float(f["log_mb"])
        f["cpu_pct"] = round(int(f["cpu_ms"] or 0) * 100 / total_cpu, 1)
        f["latencia_ms"] = round(int(f["io_stall_ms"]) / int(f["operaciones"]), 2) if f["operaciones"] else 0
        f["es_sistema"] = f["database_id"] <= 4
        f["es_snapshot"] = f["source_database_id"] is not None
    return filas


def tamanos_bd(conn):
    """Versión ligera (solo tamaños) que usa el recolector para el histórico."""
    return consultar(conn, """
        SELECT DB_NAME(database_id) AS nombre,
               CAST(SUM(CASE WHEN type = 0 THEN CAST(size AS BIGINT) ELSE 0 END) * 8 / 1024.0 AS DECIMAL(18,2)) AS datos_mb,
               CAST(SUM(CASE WHEN type = 1 THEN CAST(size AS BIGINT) ELSE 0 END) * 8 / 1024.0 AS DECIMAL(18,2)) AS log_mb
        FROM sys.master_files WHERE database_id > 4
        GROUP BY database_id
    """)


def archivos_bd(conn, nombre_bd):
    return consultar(conn, """
        SELECT file_id, name AS nombre_logico, physical_name AS ruta, type_desc AS tipo,
               CAST(CAST(size AS BIGINT) * 8 / 1024.0 AS DECIMAL(18,2)) AS tamano_mb,
               growth, is_percent_growth
        FROM sys.master_files WHERE database_id = DB_ID(?) ORDER BY type, file_id
    """, nombre_bd)


def rutas_por_defecto(conn):
    r = consultar_uno(conn, """
        SELECT CAST(SERVERPROPERTY('InstanceDefaultDataPath')   AS NVARCHAR(400)) AS datos,
               CAST(SERVERPROPERTY('InstanceDefaultLogPath')    AS NVARCHAR(400)) AS log,
               CAST(SERVERPROPERTY('InstanceDefaultBackupPath') AS NVARCHAR(400)) AS respaldo
    """)
    sep = "\\" if "\\" in (r["datos"] or "") else "/"
    for k in ("datos", "log", "respaldo"):
        if r[k] and not r[k].endswith(sep):
            r[k] += sep
    r["separador"] = sep
    return r


# =====================================================================
#  UNIDAD 3 · Planeación de capacidad
# =====================================================================
def metricas_capacidad(conn):
    """Valores actuales de CPU, memoria y almacenamiento, con sus latencias."""
    datos = consultar_uno(conn, """
        SET NOCOUNT ON;
        SELECT si.cpu_count AS nucleos,
               si.physical_memory_kb / 1024 AS memoria_total_mb,
               pm.physical_memory_in_use_kb / 1024 AS memoria_sql_mb,
               (SELECT CAST(value_in_use AS INT) FROM sys.configurations
                 WHERE name = 'max server memory (MB)') AS max_server_memory_mb,
               (SELECT TOP 1 cntr_value FROM sys.dm_os_performance_counters
                 WHERE counter_name = 'Page life expectancy' AND object_name LIKE '%Buffer Manager%') AS ple_seg,
               (SELECT CAST(100.0 * SUM(signal_wait_time_ms) / NULLIF(SUM(wait_time_ms), 0) AS DECIMAL(6,2))
                  FROM sys.dm_os_wait_stats
                 WHERE wait_time_ms > 0 AND wait_type NOT LIKE '%SLEEP%' AND wait_type NOT LIKE '%IDLE%'
                   AND wait_type NOT LIKE '%QUEUE%' AND wait_type NOT LIKE 'XE%'
                   AND wait_type NOT IN ('CHECKPOINT_QUEUE','LAZYWRITER_SLEEP','WAITFOR','BROKER_TASK_STOP',
                                         'SQLTRACE_BUFFER_FLUSH','DIRTY_PAGE_POLL','HADR_FILESTREAM_IOMGR_IOCOMPLETION')
               ) AS signal_wait_pct,
               (SELECT CAST(SUM(io_stall_read_ms) * 1.0 / NULLIF(SUM(num_of_reads), 0) AS DECIMAL(10,2))
                  FROM sys.dm_io_virtual_file_stats(NULL, NULL)) AS latencia_lectura_ms,
               (SELECT CAST(SUM(io_stall_write_ms) * 1.0 / NULLIF(SUM(num_of_writes), 0) AS DECIMAL(10,2))
                  FROM sys.dm_io_virtual_file_stats(NULL, NULL)) AS latencia_escritura_ms
        FROM sys.dm_os_sys_info si CROSS JOIN sys.dm_os_process_memory pm
    """)
    return datos
