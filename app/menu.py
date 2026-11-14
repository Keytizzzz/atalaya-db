"""Menú lateral de Atalaya DB (nombres y orden propios).

Cada entrada: (clave, título, icono Bootstrap, unidad del temario, listo?)
Las que tienen listo=False se muestran con la página "En desarrollo"
hasta que se programe su módulo.
"""
MENU = [
    ("inicio",          "Panel general",          "bi-grid-1x2",          "U1", True),
    ("servidores",      "Servidores",             "bi-hdd-network",       "U1/U2", True),
    ("bases_datos",     "Bases de datos",         "bi-database",          "U3", True),
    ("capacidad",       "Planeación de capacidad", "bi-bar-chart-steps",  "U3", True),
    ("configuracion",   "Configuración",          "bi-sliders",           "U4", False),
    ("desempeno",       "Desempeño",              "bi-speedometer2",      "U4", False),
    ("consultas",       "Consultas optimizadas",  "bi-lightning-charge",  "U4", False),
    ("recomendaciones", "Recomendaciones",        "bi-lightbulb",         "U4", False),
    ("respaldos",       "Respaldos",              "bi-cloud-arrow-up",    "U5", False),
    ("alertas",         "Alertas",                "bi-bell",              "U6", False),
    ("errores",         "Errores severos",        "bi-exclamation-octagon", "U6", False),
    ("trazas",          "Análisis de trazas",     "bi-activity",          "U6", False),
    ("predicciones",    "Advertencias y predicciones", "bi-graph-up-arrow", "U6", False),
    ("clasificacion",   "Clasificación de datos", "bi-shield-lock",       "U6", False),
    ("documentacion",   "Documentación",          "bi-journal-text",      "Extra", False),
    ("control_acceso",  "Control de acceso",      "bi-people",            "U6", False),
]

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
