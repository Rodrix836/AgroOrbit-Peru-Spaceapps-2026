# Backend de AgroOrbit Perú

API inicial de AgroOrbit Perú para consultar datos agroclimáticos diarios de NASA POWER a partir de coordenadas y fechas. La base de datos ya contiene el esquema del MVP; la ruta POWER todavía no guarda automáticamente sus respuestas.

## Tecnología

- Python 3.11 o posterior
- FastAPI y Pydantic para la API y la validación
- Pydantic Settings para la configuración y las variables de entorno
- Uvicorn para ejecutar el servidor
- HTTPX para consultar NASA POWER de forma asíncrona
- SQLAlchemy y psycopg 3 para PostgreSQL de Supabase

## Estructura

```text
backend/
├── requirements.txt
├── .env.example
├── README.md
└── app/
    ├── main.py                 # Aplicación y endpoints de estado
    ├── api/
    │   ├── router.py           # Registro central de rutas
    │   └── routes/            # NASA, usuarios, parcelas y observaciones
    ├── core/
    │   ├── config.py           # Configuración de aplicación y NASA POWER
    │   ├── logging.py          # Formato y nivel de logs
    │   └── exceptions.py       # Excepciones compartidas
    ├── database/
    │   ├── connection.py       # DATABASE_URL y motor SQLAlchemy
    │   ├── session.py          # Sesiones para rutas y servicios
    │   └── models/            # Los 14 modelos del esquema del MVP
    └── services/
        ├── auth.py             # Validación de identidad con Supabase Auth
        └── nasa/               # Cliente POWER y normalización de observaciones
```

Las migraciones están en `../supabase/migrations/`: la inicial crea `plot` y `nasa_observation`; `20261029043058_complete_agroorbit_schema.sql` agrega el resto del esquema.

La carpeta `services/nasa/` permite incorporar después `lgrip30_service.py` como integración local independiente. LGRIP30 no forma parte de esta rama.

## Instalación y ejecución

Desde la carpeta `backend/` del repositorio, crea un entorno virtual e instala las dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

En macOS o Linux, activa el entorno con `source .venv/bin/activate`.

Inicia el servidor **desde `backend/`**:

```powershell
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000/docs` para usar Swagger. Los endpoints `GET /` y `GET /health` permiten comprobar que la API está activa.

La configuración se lee de variables de entorno o de `backend/.env`, si existe. Puedes copiar `.env.example` a `.env` para personalizarla; `.env` está ignorado por Git. Sin ese archivo, funcionan los valores predeterminados. `NASA_POWER_TIMEOUT` controla el tiempo máximo de espera de la consulta externa, en segundos, y debe ser mayor que cero. Su valor predeterminado es 30.

`APP_NAME`, `APP_VERSION`, `APP_ENV` y `DEBUG` configuran la aplicación. `NASA_POWER_BASE_URL`, `NASA_POWER_COMMUNITY` y `NASA_POWER_TIMEOUT` configuran la consulta externa. Los registros de la aplicación incluyen fecha, nivel, módulo y mensaje.

## Base de datos Supabase

1. Crea un proyecto Supabase para desarrollo y copia su cadena PostgreSQL desde **Connect**. Usa conexión directa si tu entorno admite IPv6; si solo admite IPv4, elige el pooler en modo **session**. No construyas la dirección del pooler manualmente.
2. En `backend/.env`, define `DATABASE_URL` con esa cadena y añade `sslmode=require` si no figura en ella. La aplicación puede iniciar sin esta variable; se exige al abrir una sesión de base de datos.
3. Aplica la migración desde la raíz del repositorio con Supabase CLI (`supabase link` y `supabase db push`). El equipo debe coordinar una sola persona para ejecutar `db push` contra el proyecto compartido. No crees tablas manualmente en el proyecto remoto después de empezar a usar migraciones.

El esquema contiene 14 tablas:

| Área | Tablas | Uso |
| --- | --- | --- |
| Identidad y parcela | `app_user`, `plot` | Perfil, ubicación y datos declarados por el agricultor |
| Catálogo agronómico | `agronomic_source`, `crop`, `crop_requirement`, `rotation_rule` | Cultivos y reglas con fuente y nivel de evidencia |
| Historial y campo | `crop_cycle`, `device`, `sensor_reading` | Campañas y mediciones IoT |
| Datos y cálculo | `nasa_observation`, `indicator` | Observaciones NASA con procedencia e indicadores derivados |
| Decisiones | `recommendation`, `recommendation_item`, `rotation_plan` | Entradas, candidatos, explicación y secuencia propuesta |

Las claves foráneas, restricciones e índices impiden duplicados de observaciones y lecturas, exigen una sola campaña activa por parcela y protegen la integridad de las recomendaciones. La rotación identifica si se basa en clima reciente o histórico. Los puntajes internos se guardan entre 0 y 1; la confianza se expresa por niveles.

El catálogo empieza vacío: no se insertan parámetros ni reglas agronómicas sin fuente verificable. `crop_requirement.value` almacena un objeto JSON; el servicio que cargue el catálogo debe validar la estructura de cada criterio y su unidad. Las migraciones habilitan RLS en las 14 tablas y retiran permisos directos de `anon` y `authenticated`. FastAPI accede mediante PostgreSQL; la cadena de conexión debe permanecer solo en el backend. Antes de exponer datos de varios usuarios, la API deberá autenticar cada solicitud y comprobar que el usuario es dueño de la parcela.

La dependencia `get_db_session` de `app.database.session` entrega una sesión por solicitud. La ruta o el servicio confirma escrituras con `session.commit()`. La ruta pública `GET /api/nasa/power` sigue siendo de solo lectura; la persistencia se realiza por parcela mediante el nuevo `POST` descrito abajo.

## Identidad, parcelas y observaciones

Configura `SUPABASE_URL` y `SUPABASE_PUBLISHABLE_KEY` en `backend/.env`. Las rutas privadas comprueban cada token de usuario con Supabase Auth (`/auth/v1/user`); el cliente nunca decide el `user_id` de una parcela. El frontend puede iniciar sesión con Supabase Auth, pero accede a las tablas solo a través de esta API. `DATABASE_URL` queda únicamente en `backend/.env`.

Con un token de usuario válido, el primer flujo es:

1. `POST /api/users/me` con `{"display_name":"Nombre"}` para crear el perfil `app_user`; `GET /api/users/me` permite leerlo.
2. `POST /api/plots` con `name`, `latitude` y `longitude` para crear una parcela. `GET /api/plots` y `GET /api/plots/{plot_id}` solo muestran parcelas del usuario autenticado.
3. `POST /api/plots/{plot_id}/nasa/power?start_date=20240101&end_date=20240103` consulta NASA con las coordenadas de la parcela y guarda las observaciones. La respuesta indica cuántas filas se insertaron, cuántas ya existían y cuántos valores faltantes se omitieron. Repetir la consulta no duplica filas.
4. `GET /api/plots/{plot_id}/nasa/observations` lee las observaciones guardadas. Admite `limit` entre 1 y 1000.

La versión guardada en `dataset_version` es la versión de la **API POWER** comunicada en su respuesta (`api-v...`), no una versión de cada fuente meteorológica subyacente. Cada fecha diaria se guarda como medianoche UTC para identificar el día; POWER entrega las series diarias en tiempo solar local por defecto. Los valores iguales al `fill_value` de NASA, no numéricos o no finitos se omiten. Las unidades se toman de los metadatos recibidos, sin inventarlas.

La propuesta de contrato para `POST /api/recommendations` está en [docs/recommendations-contract.md](docs/recommendations-contract.md). Se requiere revisión con Luis y Milene antes de activar esa ruta.

## Consultar NASA POWER

`GET /api/nasa/power` requiere:

| Parámetro | Descripción |
| --- | --- |
| `latitude` | Latitud entre -90 y 90 |
| `longitude` | Longitud entre -180 y 180 |
| `start_date` | Primera fecha, en formato `AAAAMMDD` |
| `end_date` | Última fecha, en formato `AAAAMMDD`; debe ser igual o posterior a `start_date` |

Ejemplo para Piura, Perú, con un período histórico:

```text
http://127.0.0.1:8000/api/nasa/power?latitude=-5.0&longitude=-80.6&start_date=20240101&end_date=20240103
```

También puedes abrir `/docs`, elegir **GET /api/nasa/power**, ingresar los cuatro parámetros y pulsar **Execute**.

La respuesta contiene `source`, `location`, `period` y `data`. `data` conserva las series diarias originales por variable; NASA POWER puede indicar datos faltantes con sus propios valores de relleno. La API no genera valores alternativos.

Se solicitan `T2M`, `T2M_MAX`, `T2M_MIN`, `PRECTOTCORR`, `RH2M`, `WS10M` y `ALLSKY_SFC_SW_DWN` con `community=AG`. Las fechas se envían a la [API diaria oficial de NASA POWER](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) en formato `AAAAMMDD`.

Los parámetros inválidos reciben HTTP 422. Si NASA POWER falla, la API informa el código recibido o distingue fallas de conexión y tiempo de espera.

## Pruebas

La instalación editable anterior registra el paquete `app` en el entorno virtual,
por lo que sus imports también funcionan desde la raíz del repositorio.
En VS Code selecciona `backend/.venv/Scripts/python.exe` como intérprete
(en Linux/macOS, `backend/.venv/bin/python`). La configuración
`pyrightconfig.json` incluye las rutas de aplicación y pruebas.

Desde la raíz, puedes comprobar específicamente el flujo API con:

```powershell
backend/.venv/Scripts/python -m unittest discover -s backend/tests -p test_api_flow.py -v
```

Desde `backend/`, con las dependencias instaladas, ejecuta:

```powershell
python -m unittest discover -s tests -v
```

Las pruebas automáticas usan una respuesta simulada para verificar la ruta NASA POWER sin depender de la red. Para comprobar la conexión real, inicia Uvicorn y ejecuta la consulta del ejemplo anterior.

`tests/test_database.py` usa SQLite temporal para comprobar modelos, relaciones, restricciones y un flujo completo de persistencia. No sustituye la verificación de la migración en Supabase.

`tests/test_api_flow.py` comprueba el flujo usuario → parcela → observaciones, el aislamiento entre usuarios y la ausencia de duplicados. Usa una respuesta POWER simulada; la comprobación contra Supabase real requiere las variables de entorno del proyecto y un token de usuario válido.
