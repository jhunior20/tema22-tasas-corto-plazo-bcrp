# Tasas de corto plazo en el Perú: interbancaria, certificados del BCRP y tasa de referencia

## 1. Identificación del estudiante

| Campo | Dato |
|---|---|
| Nombres y apellidos completos | Isai Jhunior Laymito Tacza |
| Código de matrícula | 2024200505K |

## 2. Tema

**N.º 22 – Tasas de corto plazo en el Perú: interbancaria, certificados del BCRP y tasa de referencia**

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
| `04_analisis.py` | Guarda la base exacta que entra al modelo (`datos_analisis`) y genera descriptivos, correlaciones, figuras y la regresión MCO con errores Newey-West en `salidas/`. |

Cada ejecución queda registrada en `log_ejecucion.txt`.

## 6. Versión del lenguaje y de las librerías

**Python 3.11.9**

| Librería | Versión |
|---|---|
| requests | 2.34.2 |
| pandas | 3.0.6 |
| numpy | 2.4.6 |
| matplotlib | 3.11.2 |
| statsmodels | 0.15.0 |

Instalación exacta:

```
pip install -r requirements.txt
```

## 7. Hash SHA-256 del archivo procesado

Archivo: `datos_procesados/datos_procesados_2024200505K.csv`

```
8c3a2a07b92ac92b5369bd69e96a3bcb2d89b1398f8f4915a413930abdb97c59
```

## 8. Repositorio de GitHub

https://github.com/jhunior20/tema22-tasas-corto-plazo-bcrp
