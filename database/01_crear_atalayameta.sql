-- ============================================================
-- Atalaya DB - 01: Creación de la base de datos propia del sistema
-- Se ejecuta en la instancia SQL1 (localhost,1433)
-- ============================================================
IF DB_ID('AtalayaMeta') IS NULL
BEGIN
    CREATE DATABASE AtalayaMeta;
END
GO

ALTER DATABASE AtalayaMeta SET RECOVERY SIMPLE;
GO
