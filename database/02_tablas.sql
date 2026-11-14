-- ============================================================
-- Atalaya DB - 02: Tablas de la base de datos propia (AtalayaMeta)
-- Cubre el modelo completo del proyecto (las 6 unidades).
-- Es seguro ejecutarlo varias veces: solo crea lo que no existe.
-- ============================================================
USE AtalayaMeta;
GO

-- ---------- SEGURIDAD Y USUARIOS (Unidad 6 / Unidad 2) ----------
IF OBJECT_ID('dbo.roles') IS NULL
CREATE TABLE dbo.roles (
    id_rol        INT IDENTITY PRIMARY KEY,
    nombre        NVARCHAR(50)  NOT NULL UNIQUE,
    descripcion   NVARCHAR(200) NULL
);
GO

IF OBJECT_ID('dbo.usuarios') IS NULL
CREATE TABLE dbo.usuarios (
    id_usuario         INT IDENTITY PRIMARY KEY,
    nombre             NVARCHAR(100) NOT NULL,
    correo             NVARCHAR(150) NOT NULL UNIQUE,
    password_hash      NVARCHAR(100) NOT NULL,          -- hash bcrypt (nunca texto plano)
    id_rol             INT NOT NULL REFERENCES dbo.roles(id_rol),
    activo             BIT NOT NULL DEFAULT 1,
    fecha_expiracion   DATE NULL,                        -- NULL = no expira
    intentos_fallidos  INT NOT NULL DEFAULT 0,
    bloqueado_hasta    DATETIME2 NULL,
    ultimo_acceso      DATETIME2 NULL,
    fecha_creacion     DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

IF OBJECT_ID('dbo.tokens_recuperacion') IS NULL
CREATE TABLE dbo.tokens_recuperacion (
    id_token      INT IDENTITY PRIMARY KEY,
    id_usuario    INT NOT NULL REFERENCES dbo.usuarios(id_usuario) ON DELETE CASCADE,
    token_hash    NVARCHAR(100) NOT NULL,                -- SHA-256 del token
    expira        DATETIME2 NOT NULL,
    usado         BIT NOT NULL DEFAULT 0
);
GO

-- ---------- SERVIDORES / INSTANCIAS (Unidad 1 y 2) ----------
IF OBJECT_ID('dbo.servidores') IS NULL
CREATE TABLE dbo.servidores (
    id_servidor          INT IDENTITY PRIMARY KEY,
    alias                NVARCHAR(100) NOT NULL UNIQUE,
    direccion            NVARCHAR(200) NOT NULL,
    puerto               INT NOT NULL DEFAULT 1433,
    plataforma           NVARCHAR(30)  NOT NULL,          -- On-premise / Nube / Contenedor
    modo_acceso          NVARCHAR(30)  NOT NULL,          -- Directo / Gateway
    tipo_autenticacion   NVARCHAR(30)  NOT NULL,          -- SQL / Windows
    usuario              NVARCHAR(100) NULL,
    password_cifrada     NVARCHAR(500) NULL,              -- cifrado Fernet (reversible)
    cifrar_conexion      BIT NOT NULL DEFAULT 1,
    confiar_certificado  BIT NOT NULL DEFAULT 1,
    so_usuario           NVARCHAR(100) NULL,              -- credenciales admin del SO (opcional)
    so_password_cifrada  NVARCHAR(500) NULL,
    -- datos detectados al conectar
    nombre_instancia     NVARCHAR(200) NULL,
    version_motor        NVARCHAR(100) NULL,
    edicion              NVARCHAR(100) NULL,
    num_bases_datos      INT NULL,
    health_score         INT NULL,
    monitoreo_activo     BIT NOT NULL DEFAULT 1,
    ultimo_heartbeat     DATETIME2 NULL,
    ultimo_chequeo       DATETIME2 NULL,
    estado_conexion      NVARCHAR(20) NULL,               -- OK / ERROR
    registrado_por       INT NULL REFERENCES dbo.usuarios(id_usuario),
    fecha_registro       DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

IF OBJECT_ID('dbo.etiquetas') IS NULL
CREATE TABLE dbo.etiquetas (
    id_etiqueta   INT IDENTITY PRIMARY KEY,
    nombre        NVARCHAR(50) NOT NULL UNIQUE,
    color         NVARCHAR(20) NOT NULL DEFAULT 'secondary'
);
GO

IF OBJECT_ID('dbo.servidor_etiqueta') IS NULL
CREATE TABLE dbo.servidor_etiqueta (
    id_servidor   INT NOT NULL REFERENCES dbo.servidores(id_servidor) ON DELETE CASCADE,
    id_etiqueta   INT NOT NULL REFERENCES dbo.etiquetas(id_etiqueta) ON DELETE CASCADE,
    PRIMARY KEY (id_servidor, id_etiqueta)
);
GO

-- Checklist de acceso por servidor (Unidad 6)
IF OBJECT_ID('dbo.usuario_servidor') IS NULL
CREATE TABLE dbo.usuario_servidor (
    id_usuario    INT NOT NULL REFERENCES dbo.usuarios(id_usuario) ON DELETE CASCADE,
    id_servidor   INT NOT NULL REFERENCES dbo.servidores(id_servidor) ON DELETE CASCADE,
    PRIMARY KEY (id_usuario, id_servidor)
);
GO

-- ---------- MÉTRICAS (Unidad 1, 3 y 6) ----------
IF OBJECT_ID('dbo.metricas_servidor') IS NULL
CREATE TABLE dbo.metricas_servidor (
    id_metrica      BIGINT IDENTITY PRIMARY KEY,
    id_servidor     INT NOT NULL REFERENCES dbo.servidores(id_servidor) ON DELETE CASCADE,
    fecha           DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    cpu_sql         INT NULL,          -- % CPU usado por SQL Server
    cpu_otros       INT NULL,          -- % CPU de otros procesos
    memoria_mb      INT NULL,          -- memoria usada por SQL Server
    datos_mb        DECIMAL(18,2) NULL,
    log_mb          DECIMAL(18,2) NULL,
    disco_total_mb  DECIMAL(18,2) NULL,
    disco_libre_mb  DECIMAL(18,2) NULL
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_metricas_servidor_fecha')
    CREATE INDEX IX_metricas_servidor_fecha ON dbo.metricas_servidor(id_servidor, fecha);
GO

IF OBJECT_ID('dbo.metricas_bd') IS NULL
CREATE TABLE dbo.metricas_bd (
    id_metrica      BIGINT IDENTITY PRIMARY KEY,
    id_servidor     INT NOT NULL REFERENCES dbo.servidores(id_servidor) ON DELETE CASCADE,
    nombre_bd       NVARCHAR(128) NOT NULL,
    fecha           DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    datos_mb        DECIMAL(18,2) NULL,
    log_mb          DECIMAL(18,2) NULL
);
GO

-- Bases de datos excluidas del monitoreo (Unidad 3)
IF OBJECT_ID('dbo.bd_excluidas') IS NULL
CREATE TABLE dbo.bd_excluidas (
    id_servidor   INT NOT NULL REFERENCES dbo.servidores(id_servidor) ON DELETE CASCADE,
    nombre_bd     NVARCHAR(128) NOT NULL,
    fecha         DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    PRIMARY KEY (id_servidor, nombre_bd)
);
GO

-- ---------- MONITOREO Y AUDITORÍA (Unidad 6) ----------
IF OBJECT_ID('dbo.eventos_error') IS NULL
CREATE TABLE dbo.eventos_error (
    id_evento     BIGINT IDENTITY PRIMARY KEY,
    id_servidor   INT NOT NULL REFERENCES dbo.servidores(id_servidor) ON DELETE CASCADE,
    origen        NVARCHAR(100) NULL,
    id_error      INT NULL,
    severidad     INT NULL,
    fecha_evento  DATETIME2 NOT NULL,
    mensaje       NVARCHAR(MAX) NULL
);
GO

IF OBJECT_ID('dbo.trazas') IS NULL
CREATE TABLE dbo.trazas (
    id_traza      BIGINT IDENTITY PRIMARY KEY,
    id_servidor   INT NOT NULL REFERENCES dbo.servidores(id_servidor) ON DELETE CASCADE,
    evento        NVARCHAR(100) NULL,
    fecha_evento  DATETIME2 NOT NULL,
    base_datos    NVARCHAR(128) NULL,
    objeto        NVARCHAR(256) NULL,
    login         NVARCHAR(128) NULL,
    duracion_ms   BIGINT NULL,
    texto_sql     NVARCHAR(MAX) NULL
);
GO

IF OBJECT_ID('dbo.notificaciones') IS NULL
CREATE TABLE dbo.notificaciones (
    id_notificacion BIGINT IDENTITY PRIMARY KEY,
    id_servidor     INT NULL REFERENCES dbo.servidores(id_servidor) ON DELETE CASCADE,
    id_usuario      INT NULL REFERENCES dbo.usuarios(id_usuario),   -- NULL = para todos
    tipo            NVARCHAR(30) NOT NULL DEFAULT 'info',            -- info / warning / danger
    mensaje         NVARCHAR(500) NOT NULL,
    leida           BIT NOT NULL DEFAULT 0,
    fecha           DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

IF OBJECT_ID('dbo.bitacora_actividad') IS NULL
CREATE TABLE dbo.bitacora_actividad (
    id_bitacora   BIGINT IDENTITY PRIMARY KEY,
    id_usuario    INT NULL REFERENCES dbo.usuarios(id_usuario),
    accion        NVARCHAR(100) NOT NULL,
    detalle       NVARCHAR(1000) NULL,
    ip            NVARCHAR(50) NULL,
    fecha         DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

IF OBJECT_ID('dbo.reglas_login') IS NULL
CREATE TABLE dbo.reglas_login (
    id_regla      INT IDENTITY PRIMARY KEY,
    id_servidor   INT NOT NULL REFERENCES dbo.servidores(id_servidor) ON DELETE CASCADE,
    login         NVARCHAR(128) NOT NULL,
    ip_permitida  NVARCHAR(50) NULL,
    hora_inicio   TIME NULL,
    hora_fin      TIME NULL,
    activa        BIT NOT NULL DEFAULT 1
);
GO

-- ---------- OPERACIÓN (Unidad 4 y 5) ----------
IF OBJECT_ID('dbo.analisis_consultas') IS NULL
CREATE TABLE dbo.analisis_consultas (
    id_analisis       BIGINT IDENTITY PRIMARY KEY,
    id_servidor       INT NOT NULL REFERENCES dbo.servidores(id_servidor) ON DELETE CASCADE,
    base_datos        NVARCHAR(128) NULL,
    objeto            NVARCHAR(256) NULL,
    texto_consulta    NVARCHAR(MAX) NULL,
    problemas         NVARCHAR(1000) NULL,
    mejora_estimada   INT NULL,           -- porcentaje
    fecha_analisis    DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO

IF OBJECT_ID('dbo.operaciones_respaldo') IS NULL
CREATE TABLE dbo.operaciones_respaldo (
    id_operacion     BIGINT IDENTITY PRIMARY KEY,
    id_servidor      INT NOT NULL REFERENCES dbo.servidores(id_servidor) ON DELETE CASCADE,
    base_datos       NVARCHAR(128) NOT NULL,
    operacion        NVARCHAR(20) NOT NULL,      -- RESPALDO / RESTAURACION / LIMPIEZA
    tipo             NVARCHAR(20) NULL,          -- COMPLETO / DIFERENCIAL / LOG
    destino          NVARCHAR(500) NULL,
    opciones         NVARCHAR(200) NULL,
    estado           NVARCHAR(20) NOT NULL DEFAULT 'EN_PROCESO',
    archivo          NVARCHAR(500) NULL,
    mensaje_error    NVARCHAR(MAX) NULL,
    solicitado_por   INT NULL REFERENCES dbo.usuarios(id_usuario),
    fecha_solicitud  DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
    fecha_fin        DATETIME2 NULL
);
GO

-- ---------- INTERFAZ (Unidad 1: recientes y favoritos) ----------
IF OBJECT_ID('dbo.paginas_visitadas') IS NULL
CREATE TABLE dbo.paginas_visitadas (
    id_pagina     BIGINT IDENTITY PRIMARY KEY,
    id_usuario    INT NOT NULL REFERENCES dbo.usuarios(id_usuario) ON DELETE CASCADE,
    titulo        NVARCHAR(150) NOT NULL,
    url           NVARCHAR(300) NOT NULL,
    favorito      BIT NOT NULL DEFAULT 0,
    fecha         DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);
GO
