# Backend de AgroOrbit Perú

API inicial de AgroOrbit Perú para consultar datos agroclimáticos diarios de NASA POWER a partir de coordenadas y fechas. Esta etapa no incluye base de datos, recomendaciones ni clasificación de terreno.

## Tecnología

- Python 3.11 o posterior
- FastAPI y Pydantic para la API y la validación
- Pydantic Settings para la configuración y las variables de entorno
- Uvicorn para ejecutar el servidor
- HTTPX para consultar NASA POWER de forma asíncrona

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
    │   └── routes/nasa.py      # Validación y endpoint NASA
    ├── core/
    │   ├── config.py           # Configuración de aplicación y NASA POWER
    │   ├── logging.py          # Formato y nivel de logs
    │   └── exceptions.py       # Excepciones compartidas
    └── services/nasa/
        └── power_service.py    # Cliente HTTP de NASA POWER
```

La carpeta `services/nasa/` permite incorporar después `lgrip30_service.py` como integración local independiente. LGRIP30 no forma parte de esta rama.

## Instalación y ejecución

Desde la carpeta `backend/` del repositorio, crea un entorno virtual e instala las dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

En macOS o Linux, activa el entorno con `source .venv/bin/activate`.

Inicia el servidor **desde `backend/`**:

```powershell
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000/docs` para usar Swagger. Los endpoints `GET /` y `GET /health` permiten comprobar que la API está activa.

La configuración se lee de variables de entorno o de `backend/.env`, si existe. Puedes copiar `.env.example` a `.env` para personalizarla; `.env` está ignorado por Git. Sin ese archivo, funcionan los valores predeterminados. `NASA_POWER_TIMEOUT` controla el tiempo máximo de espera de la consulta externa, en segundos, y debe ser mayor que cero. Su valor predeterminado es 30.

`APP_NAME`, `APP_VERSION`, `APP_ENV` y `DEBUG` configuran la aplicación. `NASA_POWER_BASE_URL`, `NASA_POWER_COMMUNITY` y `NASA_POWER_TIMEOUT` configuran la consulta externa. Los registros de la aplicación incluyen fecha, nivel, módulo y mensaje.

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

Desde `backend/`, con las dependencias instaladas, ejecuta:

```powershell
python -m unittest discover -s tests -v
```

Las pruebas automáticas usan una respuesta simulada para verificar la ruta NASA POWER sin depender de la red. Para comprobar la conexión real, inicia Uvicorn y ejecuta la consulta del ejemplo anterior.
