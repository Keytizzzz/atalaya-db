# Atalaya DB 🗼

Suite web para la **administración y el monitoreo de instancias de SQL Server**.
Es el proyecto integrador de la materia *Administración de Bases de Datos* (Ingeniería en Sistemas Computacionales)
y toma como modelo funcional la plataforma AI-DBA.

| | |
|---|---|
| **Lenguaje** | Python 3.12 |
| **Framework web** | Flask (un *blueprint* por módulo) |
| **Motor monitoreado** | SQL Server 2022 Developer (2 instancias en Docker) |
| **Conexión** | pyodbc + ODBC Driver 18 for SQL Server |
| **Seguridad** | bcrypt (contraseñas de usuarios), Fernet/AES (credenciales de servidores) |
| **Interfaz** | Jinja2 + Bootstrap 5 + Chart.js |

---

## 1. Requisitos previos

| Programa | Descarga |
|---|---|
| Python 3.12 o superior | https://www.python.org/downloads/ (marca *Add Python to PATH*) |
| Docker Desktop | https://www.docker.com/products/docker-desktop/ |
| ODBC Driver 18 for SQL Server | https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server |
| Git | https://git-scm.com/ |
| (Opcional) SSMS o Azure Data Studio | para revisar las bases de datos a mano |

> Cada instancia de SQL Server necesita unos **2 GB de RAM**. Con 8 GB en la computadora alcanza para las dos.
> En Mac con chip Apple (M1/M2/M3), activa en Docker Desktop: *Settings → General → Use Rosetta for x86/amd64 emulation*.

## 2. Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/<usuario>/atalaya-db.git
cd atalaya-db

# 2. Entorno virtual de Python
py -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac / Linux

# 3. Dependencias
py -m pip install -r requirements.txt

# 4. Configuración
copy .env.example .env         # Windows   (cp .env.example .env en Mac/Linux)
py scripts/generar_claves.py
#   -> pega SECRET_KEY y FERNET_KEY en el archivo .env

# 5. Levantar las 2 instancias de SQL Server
docker compose up -d

# 6. Crear AtalayaMeta, la BD de demostración y el usuario administrador
py scripts/inicializar.py

# 7. Ejecutar
py run.py
```

Abrir **http://127.0.0.1:5000** e iniciar sesión con el administrador definido en `.env`
(por defecto `admin@atalaya.local` / `Admin123!`).

## 3. Enrolar las instancias de prueba

En **Servidores → Enrolar servidor** registra:

| Alias | Dirección | Puerto | Plataforma | Usuario | Contraseña |
|---|---|---|---|---|---|
| SQL Uno | localhost | 1433 | Contenedor | sa | la de `SA_PASSWORD` |
| SQL Dos | localhost | 1434 | Contenedor | sa | la de `SA_PASSWORD` |

Deja activadas *Cifrar la conexión* y *Confiar en el certificado del servidor*.

## 4. Módulos incluidos en este avance (Unidades 1, 2 y 3)

| Unidad | Módulo | Qué hace |
|---|---|---|
| U1 | Panel general / Overview | Indicadores, accesos rápidos, recientes y favoritos, ficha del servidor, Health Score, etiquetas, gráficas de datos vs log y CPU |
| U2 | Acceso y enrolamiento | Login, registro, recuperar contraseña, enrolar/editar servidores con prueba de conexión real |
| U3 | Bases de datos | Modelo de recuperación, estado, tamaño, memoria, CPU, IO Stall; copiar, snapshot, mover archivos, excluir del monitoreo |
| U3 | Planeación de capacidad | CPU, memoria y almacenamiento (disponible / en uso / ideal) con semáforo; latencias; proyección de crecimiento por regresión lineal |

## 5. Logo

Coloca tus imágenes en `app/static/img/` y reinicia la app:

| Archivo | Dónde aparece | Recomendación |
|---|---|---|
| `logo.png` | Barra superior y pantalla de inicio de sesión | Horizontal, fondo transparente, ~400×100 px |
| `logo-icono.png` | Esquina del menú de íconos y pestaña del navegador | Cuadrado, ~128×128 px |

Si no existen, se muestra el texto "Atalaya DB" y la letra "A".

## 6. Estructura del proyecto

```
atalaya-db/
├── run.py, config.py, requirements.txt, docker-compose.yml, .env.example
├── app/
│   ├── core/          conexión a AtalayaMeta, conector a instancias, seguridad, decoradores, bitácora
│   ├── modulos/       un blueprint por módulo del menú (auth, inicio, servidores, ...)
│   ├── servicios/     lógica de negocio: health score, recolector, consultas de catálogo (DMV)
│   ├── templates/     vistas HTML
│   └── static/        css / js / imágenes
├── database/          scripts SQL de AtalayaMeta + BD de demostración
├── scripts/           inicialización y generación de claves
├── docs/              diagramas, manuales, bitácora de pruebas, capturas
└── tests/             pruebas automáticas
```

## 7. Comandos útiles

```bash
docker compose ps              # ver estado de las instancias
docker compose stop            # apagar (conserva los datos)
docker compose down -v         # borrar TODO (contenedores y datos)
py -m unittest discover tests   # correr pruebas
```

## 8. Problemas comunes

| Mensaje | Solución |
|---|---|
| `No se encontró el driver ODBC` | Instala *ODBC Driver 18 for SQL Server* y revisa `ODBC_DRIVER` en `.env`. |
| `No se pudo alcanzar el servidor` | `docker compose ps` — los contenedores deben decir *running*. Espera ~30 s tras encenderlos. |
| `Falta FERNET_KEY` | Ejecuta `py scripts/generar_claves.py` y pega las claves en `.env`. |
| El contenedor se apaga solo | La contraseña `SA_PASSWORD` no cumple la política (mayúscula, minúscula, número y símbolo). |

## 9. Equipo

| Integrante | Rol |
|---|---|
| _Keyla Denisse Ortiz Moreno _ | Backend, conexión al motor y recolector |
| _Gomez Enciso Landon Donovan| Interfaz, dashboards y monitoreo |
| _Lizarraga Figueroa Samanta | Seguridad, respaldos, pruebas y documentación |
