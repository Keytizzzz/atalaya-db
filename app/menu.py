"""Menú lateral de Atalaya DB (nombres y orden propios).

Cada entrada: (clave, título, icono Bootstrap, unidad del temario)

Un módulo se considera "listo" cuando existe la carpeta app/modulos/<clave>/
con su routes.py y un Blueprint llamado igual que la clave. Mientras no exista,
el menú muestra la página "En desarrollo". La página principal de cada módulo
nuevo debe llamarse "principal" (endpoint "<clave>.principal").
"""
MENU = [
    ("inicio",          "Panel general",          "bi-grid-1x2",          "U1"),
    ("servidores",      "Servidores",             "bi-hdd-network",       "U1/U2"),
    ("bases_datos",     "Bases de datos",         "bi-database",          "U3"),
    ("capacidad",       "Planeación de capacidad", "bi-bar-chart-steps",  "U3"),
    ("configuracion",   "Configuración",          "bi-sliders",           "U4"),
    ("desempeno",       "Desempeño",              "bi-speedometer2",      "U4"),
    ("consultas",       "Consultas optimizadas",  "bi-lightning-charge",  "U4"),
    ("recomendaciones", "Recomendaciones",        "bi-lightbulb",         "U4"),
    ("respaldos",       "Respaldos",              "bi-cloud-arrow-up",    "U5"),
    ("alertas",         "Alertas",                "bi-bell",              "U6"),
    ("errores",         "Errores severos",        "bi-exclamation-octagon", "U6"),
    ("trazas",          "Análisis de trazas",     "bi-activity",          "U6"),
    ("predicciones",    "Advertencias y predicciones", "bi-graph-up-arrow", "U6"),
    ("clasificacion",   "Clasificación de datos", "bi-shield-lock",       "U6"),
    ("documentacion",   "Documentación",          "bi-journal-text",      "Extra"),
    ("control_acceso",  "Control de acceso",      "bi-people",            "U6"),
]

# Módulos anteriores a la convención "<clave>.principal"
PUNTOS_ENTRADA = {
    "inicio": "inicio.home",
    "servidores": "servidores.lista",
    "bases_datos": "bases_datos.lista",
    "capacidad": "capacidad.panel",
}

DESCRIPCIONES = {
    "bases_datos": "Listado de bases de datos por instancia: modelo de recuperación, estado, tamaño, memoria, CPU e IO Stall. Operaciones de copiar, snapshot, mover archivos y excluir del monitoreo.",
    "configuracion": "Lectura de sys.configurations, comparación contra buenas prácticas y cambios con sp_configure.",
    "desempeno": "Esperas principales, consultas más pesadas, sesiones activas y detección de bloqueos (head blocker).",
    "consultas": "Análisis de procedimientos y consultas con reglas heurísticas y porcentaje estimado de mejora.",
    "recomendaciones": "Chequeos de buenas prácticas con explicación y script de corrección.",
    "respaldos": "Respaldos completos, diferenciales y de log; restauración y limpieza con bitácora.",
    "alertas": "Reglas de umbral configurables que generan notificaciones.",
    "errores": "Errores y alertas severas del log de SQL Server con búsqueda y filtros.",
    "trazas": "Eventos capturados con Extended Events correlacionados con objetos de la base de datos.",
    "predicciones": "Proyección lineal de crecimiento de disco y de errores.",
    "capacidad": "Disponible vs. usado vs. ideal para CPU, memoria y almacenamiento con semáforo.",
    "clasificacion": "Detección de columnas sensibles y etiquetado con ADD SENSITIVITY CLASSIFICATION.",
    "documentacion": "Documentación automática del esquema de cada base de datos.",
    "control_acceso": "Usuarios de la plataforma, roles, expiración, permisos por servidor, reglas de login y bitácora de actividad.",
}
