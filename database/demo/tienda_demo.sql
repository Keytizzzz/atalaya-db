-- ============================================================
-- Atalaya DB - Base de datos de DEMOSTRACIÓN (TiendaDemo)
-- Se crea en AMBAS instancias (SQL1 y SQL2) para tener algo
-- que monitorear. Está hecha "con errores a propósito":
--   * tablas sin índices en columnas de búsqueda
--   * procedimientos con SELECT *
--   * columnas con datos sensibles (correo, RFC, teléfono, tarjeta)
-- Así los módulos de Consultas optimizadas, Recomendaciones y
-- Clasificación de datos tendrán hallazgos reales.
-- ============================================================
IF DB_ID('TiendaDemo') IS NULL
    CREATE DATABASE TiendaDemo;
GO
ALTER DATABASE TiendaDemo SET RECOVERY FULL;
GO
USE TiendaDemo;
GO

IF OBJECT_ID('dbo.clientes') IS NULL
CREATE TABLE dbo.clientes (
    id_cliente      INT IDENTITY PRIMARY KEY,
    nombre          NVARCHAR(100),
    correo          NVARCHAR(150),
    telefono        NVARCHAR(20),
    rfc             NVARCHAR(13),
    numero_tarjeta  NVARCHAR(20),
    ciudad          NVARCHAR(60),
    fecha_alta      DATETIME2 DEFAULT SYSDATETIME()
);
GO

IF OBJECT_ID('dbo.productos') IS NULL
CREATE TABLE dbo.productos (
    id_producto   INT IDENTITY PRIMARY KEY,
    nombre        NVARCHAR(100),
    categoria     NVARCHAR(50),
    precio        DECIMAL(10,2),
    existencia    INT
);
GO

IF OBJECT_ID('dbo.ventas') IS NULL
CREATE TABLE dbo.ventas (
    id_venta      INT IDENTITY PRIMARY KEY,
    id_cliente    INT,              -- sin llave foránea ni índice (a propósito)
    id_producto   INT,
    cantidad      INT,
    total         DECIMAL(12,2),
    fecha         DATETIME2
);
GO

-- Datos de prueba (solo si la tabla está vacía)
IF NOT EXISTS (SELECT 1 FROM dbo.clientes)
BEGIN
    ;WITH n AS (SELECT TOP (2000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
                FROM sys.all_objects a CROSS JOIN sys.all_objects b)
    INSERT INTO dbo.clientes (nombre, correo, telefono, rfc, numero_tarjeta, ciudad)
    SELECT CONCAT('Cliente ', i), CONCAT('cliente', i, '@correo.com'),
           CONCAT('664', RIGHT(CONCAT('0000000', i), 7)),
           CONCAT('XAXX', RIGHT(CONCAT('000000', i), 6), 'AB1'),
           CONCAT('4152', RIGHT(CONCAT('000000000000', i), 12)),
           CHOOSE(i % 5 + 1, 'Tijuana', 'Mexicali', 'Ensenada', 'Tecate', 'Rosarito')
    FROM n;

    ;WITH n AS (SELECT TOP (200) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i FROM sys.all_objects)
    INSERT INTO dbo.productos (nombre, categoria, precio, existencia)
    SELECT CONCAT('Producto ', i), CHOOSE(i % 4 + 1, 'Electrónica', 'Hogar', 'Ropa', 'Papelería'),
           CAST(50 + (i * 37) % 950 AS DECIMAL(10,2)), (i * 13) % 300
    FROM n;

    ;WITH n AS (SELECT TOP (50000) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
                FROM sys.all_objects a CROSS JOIN sys.all_objects b)
    INSERT INTO dbo.ventas (id_cliente, id_producto, cantidad, total, fecha)
    SELECT (i * 7) % 2000 + 1, (i * 11) % 200 + 1, i % 5 + 1,
           CAST(((i * 37) % 950 + 50) * (i % 5 + 1) AS DECIMAL(12,2)),
           DATEADD(MINUTE, -i * 13, SYSDATETIME())
    FROM n;
END
GO

-- Procedimientos "mal escritos" para el módulo de Consultas optimizadas
CREATE OR ALTER PROCEDURE dbo.sp_VentasPorCliente @id_cliente INT
AS
    SELECT * FROM dbo.ventas WHERE id_cliente = @id_cliente;
GO

CREATE OR ALTER PROCEDURE dbo.sp_VentasDelAnio @anio INT
AS
    SELECT * FROM dbo.ventas v
    JOIN dbo.clientes c ON c.id_cliente = v.id_cliente
    WHERE YEAR(v.fecha) = @anio;      -- función sobre la columna: impide usar índices
GO

CREATE OR ALTER PROCEDURE dbo.sp_BuscarCliente @texto NVARCHAR(50)
AS
    SELECT * FROM dbo.clientes WHERE nombre LIKE '%' + @texto + '%';
GO
