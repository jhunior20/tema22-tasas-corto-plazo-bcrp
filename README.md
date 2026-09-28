# Tasas de corto plazo en el Perú: interbancaria, certificados del BCRP y tasa de referencia

## 1. Identificación del estudiante

| Campo | Dato |
|---|---|
| Nombres y apellidos completos | Isai Jhunior Laymito Tacza |
| Código de matrícula | 2024200505K |

## 2. Tema

**N.º 22 – Tasas de corto plazo en el Perú: interbancaria, certificados del BCRP y tasa de referencia**

**Objetivo de investigación:** analizar la formación de las tasas de muy corto plazo y su desvío respecto de la tasa de política.

Modelo estimado (series de tiempo diarias, MCO con errores Newey-West/HAC):

```
interbancaria = b0 + b1·referencia + b2·CD_BCRP
              + b3·ln(depósitos_sector_público)
              + b4·ln(cuentas_corrientes_bancos_L1) + error
```

| Rol | Código BCRP | Variable | Unidad |
|---|---|---|---|
| Endógena | PD04692MD | Tasa de interés interbancaria overnight, S/ | % |
| Exógena 1 | PD12301MD | Tasa de Referencia de la Política Monetaria | % |
| Exógena 2 | PD04679MD | Tasa de interés del saldo de CD BCRP | % |
| Exógena 3 | PD04668MD | Depósitos del sector público en el BCRP (saldo) | millones S/ |
| Exógena 4 | PD04665MD | Cuentas corrientes de bancos en el BCRP (saldo), **rezagada 1 día** | millones S/ |

En `04_analisis.py` la tasa de referencia entra como **variable de escalones**: la última tasa publicada por el BCRP sigue vigente hasta la siguiente decisión del Directorio (no se usa la interpolación de `03`, porque la tasa cambia por decisiones discretas). La primera fila, sin cuenta corriente rezagada, se elimina (n = 2869).

Desvío respecto de la tasa de política: `desvío = interbancaria − referencia (escalones)` (puntos porcentuales), calculado sobre las jornadas con ambas tasas publicadas (muestra principal) y sobre la muestra completa (robustez).

Además del modelo en niveles, el análisis incluye pruebas de raíz unitaria (ADF, KPSS), cointegración de Engle-Granger, el vector de largo plazo (MCO-HAC y DOLS, con la prueba de traspaso unitario θ₁ = 1) y un modelo de corrección de errores (MCE) con su vida media.

## 3. Fuentes y endpoints

**Fuente única:** API BCRPData del Banco Central de Reserva del Perú (pública, no requiere token).
Documentación: https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/api

Cada serie se consulta en una solicitud GET independiente (formato JSON, idioma español):

| Serie | Endpoint exacto |
|---|---|
| PD04692MD | https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04692MD/json/2015-01-01/2025-12-31/esp |
| PD12301MD | https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD12301MD/json/2015-01-01/2025-12-31/esp |
| PD04679MD | https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04679MD/json/2015-01-01/2025-12-31/esp |
| PD04668MD | https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04668MD/json/2015-01-01/2025-12-31/esp |
| PD04665MD | https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PD04665MD/json/2015-01-01/2025-12-31/esp |

Se consulta una serie por solicitud porque, cuando se piden varias juntas, la API las devuelve reordenadas y sin el código en el nombre, lo que impide asignar cada valor a su serie con seguridad.

## 4. Fecha de corte

| Parámetro | Valor (congelado en `01_extraccion_api.py`) |
|---|---|
| Fecha de inicio | `FECHA_INICIO = "2015-01-01"` |
| Fecha de fin | `FECHA_CORTE = "2025-12-31"` |
| Observaciones diarias obtenidas | 2870 |
| Fecha de extracción | 24/09/2026 |

## 5. Orden de ejecución

Desde la carpeta `codigo/`:

```
python 01_extraccion_api.py
python 03_limpieza_datos.py
python 04_analisis.py
```

| Script | Qué hace |
|---|---|
| `01_extraccion_api.py` | Descarga las 5 series de la API BCRPData y guarda el crudo intacto (JSON y CSV) en `datos_crudos/`. |
| `02_scraping_web.py` | **No aplica.** La vía 2 (scraping) es opcional en la Unidad I y no se implementó: todas las series del modelo están disponibles en la API oficial del BCRP. `03` detecta que el archivo no existe y continúa solo con la API. |
| `03_limpieza_datos.py` | Tipifica, imputa faltantes (tasas: interpolación lineal; saldos: forward-fill máx. 5 días; bordes iniciales: bfill), marca outliers (±4 desv. est.), crea el rezago `_L1` y guarda `datos_procesados/` con su SHA-256. |
| `04_analisis.py` | (1) Separa valores publicados e imputados (cobertura); (2) reconstruye la tasa de referencia en escalones; (3) elimina la fila de borde del rezago; (4) calcula el desvío (muestra publicada y completa, por año, por etapa de política y los 10 mayores); (5) ADF, KPSS y Engle-Granger; (6) vector de largo plazo por MCO-HAC y DOLS; (7) regresión ampliada en niveles y MCE con diagnósticos (Durbin-Watson, Ljung-Box, Breusch-Pagan, Jarque-Bera); (8) vida media con la dinámica completa y robustez sin tramos imputados, más las cifras citadas en el texto del artículo (`tabla_cifras_texto`); (9) figuras; (10) guarda `datos_analisis` y su SHA-256 en `hash_2024200505K.txt`. |

Cada ejecución queda registrada en `log_ejecucion.txt`.

## 6. Estructura de carpetas

```
├── codigo/                01, 03 y 04 (ver sección 5)
├── datos_crudos/          respuesta de la API sin editar: JSON + CSV combinado + un CSV por serie
├── datos_procesados/      base limpia que usa el análisis (su hash está en la sección 8)
├── salidas/               resultados de 04_analisis.py
│   ├── datos_analisis_*.csv      base exacta que entra a los modelos
│   ├── hash_*.txt                SHA-256 de datos_analisis
│   ├── tabla_*.csv               15 tablas (cobertura, descriptivos, correlación, desvío,
│   │                             raíz unitaria, cointegración, largo plazo, regresión, MCE,
│   │                             diagnósticos y robustez del MCE,
│   │                             cifras citadas en el texto)
│   └── fig_*.png                 9 figuras (tasas, desvío, liquidez, autocorrelación del MCE)
├── diccionario_variables.md   definición de cada variable y columna
├── incidencias_fuente.md      problemas encontrados en los datos de la API y su tratamiento
├── log_ejecucion.txt          registro de cada ejecución de los scripts
├── requirements.txt           versiones exactas de las librerías
└── .env.example               plantilla de variables de entorno (no se necesita ninguna clave)
```

Todos los archivos de datos y salidas llevan el código de matrícula (`2024200505K`) en el nombre.

## 7. Versión del lenguaje y de las librerías

**Python 3.11.9**

| Librería | Versión |
|---|---|
| requests | 2.34.2 |
| pandas | 3.0.6 |
| numpy | 2.4.6 |
| matplotlib | 3.11.2 |
| statsmodels | 0.15.0 |
| scipy | 1.17.1 |

Instalación exacta:

```
pip install -r requirements.txt
```

## 8. Hash SHA-256 del archivo procesado

Archivo: `datos_procesados/datos_procesados_2024200505K.csv`

```
8c3a2a07b92ac92b5369bd69e96a3bcb2d89b1398f8f4915a413930abdb97c59
```

### Cómo verificar el hash

Desde la carpeta raíz del proyecto, con cualquiera de estas opciones:

```
# Windows (PowerShell)
Get-FileHash datos_procesados\datos_procesados_2024200505K.csv -Algorithm SHA256

# Linux / macOS / Git Bash
sha256sum datos_procesados/datos_procesados_2024200505K.csv

# Python (cualquier sistema)
python -c "import hashlib; print(hashlib.sha256(open('datos_procesados/datos_procesados_2024200505K.csv','rb').read()).hexdigest())"
```

El resultado debe ser idéntico al hash de arriba (PowerShell lo muestra en mayúsculas; es el mismo valor). El repositorio guarda los CSV, JSON y TXT sin convertir los saltos de línea (`.gitattributes`), para que el hash coincida también al descargarlos de GitHub. Si se vuelve a ejecutar `03_limpieza_datos.py` con el mismo crudo, el hash que imprime en `log_ejecucion.txt` debe ser el mismo.

## 9. Repositorio de GitHub

https://github.com/jhunior20/tema22-tasas-corto-plazo-bcrp
