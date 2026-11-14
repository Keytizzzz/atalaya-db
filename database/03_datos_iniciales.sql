-- ============================================================
-- Atalaya DB - 03: Datos iniciales (catálogos)
-- El usuario administrador lo crea scripts/inicializar.py
-- porque su contraseña debe guardarse con hash bcrypt.
-- ============================================================
USE AtalayaMeta;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.roles WHERE nombre = 'Administrador')
    INSERT INTO dbo.roles (nombre, descripcion) VALUES ('Administrador', 'Acceso total a la plataforma y a todos los servidores');
IF NOT EXISTS (SELECT 1 FROM dbo.roles WHERE nombre = 'Usuario')
    INSERT INTO dbo.roles (nombre, descripcion) VALUES ('Usuario', 'Acceso solo a los servidores asignados');
GO

MERGE dbo.etiquetas AS t
USING (VALUES ('Producción','danger'), ('Desarrollo','info'), ('Pruebas','secondary'),
              ('Crítico','warning'), ('Datos confidenciales','dark')) AS s(nombre, color)
ON t.nombre = s.nombre
WHEN NOT MATCHED THEN INSERT (nombre, color) VALUES (s.nombre, s.color);
GO
