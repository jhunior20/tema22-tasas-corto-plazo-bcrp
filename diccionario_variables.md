# Diccionario de variables

Tema 22 – Isai Jhunior Laymito Tacza (2024200505K)

Fuente de todas las series: API BCRPData del Banco Central de Reserva del Perú. Frecuencia diaria, del 01/01/2015 al 31/12/2025 (2870 observaciones).

## 1. Variables del modelo (`datos_procesados_2024200505K.csv`)

| Variable | Descripción | Código BCRP | Unidad | Tipo | Rol en el modelo | Tratamiento de faltantes |
|---|---|---|---|---|---|---|
| `fecha` | Fecha de la observación (día hábil reportado por el BCRP) | – | AAAA-MM-DD | fecha | Llave de unión | – |
| `tasa_interbancaria_on_end` | Tasa de interés interbancaria overnight en soles | PD04692MD | % anual | decimal | Endógena | Interpolación lineal |
| `tasa_referencia_exo` | Tasa de Referencia de la Política Monetaria | PD12301MD | % anual | decimal | Exógena 1 | Interpolación lineal |
| `tasa_cdbcrp_saldo_exo` | Tasa de interés del saldo de Certificados de Depósito del BCRP | PD04679MD | % anual | decimal | Exógena 2 | Interpolación lineal; bfill al inicio de la serie |
| `depositos_sector_publico_saldo_exo` | Depósitos del sector público en el BCRP (saldo) | PD04668MD | millones de S/ | decimal | Exógena 3 | Forward-fill (máx. 5 días); bfill al inicio de la serie |
| `cuentas_corrientes_bancos_bcrp_saldo_exo` | Cuentas corrientes de los bancos en el BCRP (saldo) | PD04665MD | millones de S/ | decimal | Base de la exógena 4 (sin rezago) | Forward-fill (máx. 5 días); bfill al inicio de la serie |
| `cuentas_corrientes_bancos_bcrp_saldo_exo_L1` | Cuentas corrientes de los bancos en el BCRP, rezagada 1 día | PD04665MD | millones de S/ | decimal | Exógena 4 (la que entra al modelo) | bfill en la primera fila (no hay día anterior) |

## 2. Columnas de trazabilidad (`datos_procesados_2024200505K.csv`)

| Variable | Descripción | Tipo | Valores posibles |
|---|---|---|---|
| `<variable>_metodo_imputacion` | Método con que se rellenó cada celda. Vacío = dato real del BCRP, sin modificar | texto | vacío, `interpolacion_lineal`, `forward_fill_max5`, `bfill_borde_inicial`, `ffill_borde_final` |
| `<variable>_outlier` | Marca si el valor está a más de ±4 desviaciones estándar de la media de la serie. Solo se marca; no se elimina ni corrige | booleano | `True`, `False` |

## 3. Variables transformadas para la regresión (`salidas/datos_analisis_2024200505K.csv`)

| Variable | Descripción | Unidad | Construcción |
|---|---|---|---|
| `ln_depositos` | Logaritmo natural de los depósitos del sector público | ln(millones de S/) | `ln(depositos_sector_publico_saldo_exo)` |
| `ln_ctacte_L1` | Logaritmo natural de las cuentas corrientes de bancos, rezagada 1 día | ln(millones de S/) | `ln(cuentas_corrientes_bancos_bcrp_saldo_exo_L1)` |

Las tres tasas entran a la regresión en nivel (%), con el mismo nombre que en la sección 1.

## 4. Desvío respecto de la tasa de política (`salidas/tabla_desvio_por_anio_2024200505K.csv`)

El desvío se calcula en memoria en `04_analisis.py` (no se guarda en `datos_procesados`):

| Variable | Descripción | Unidad | Construcción |
|---|---|---|---|
| `desvio_interbancaria_referencia_pp` | Desvío diario de la interbancaria respecto de la tasa de referencia. Positivo = la interbancaria está por encima de la tasa de política | puntos porcentuales | `tasa_interbancaria_on_end − tasa_referencia_exo` |

Columnas de la tabla por año (la última fila resume toda la muestra). `salidas/tabla_desvio_por_etapa_2024200505K.csv` tiene las mismas columnas, pero agrupadas por las 5 etapas de política monetaria (columnas `etapa`, `fecha_inicio` y `fecha_fin` en lugar de `periodo`):

| Columna | Descripción |
|---|---|
| `periodo` | Año, o `2015-2025` para toda la muestra |
| `n_dias` | Número de días del periodo |
| `desvio_medio_pp` | Promedio del desvío (pp) |
| `desvio_absoluto_medio_pp` | Promedio del valor absoluto del desvío (pp): cuánto se aleja, sin importar el signo |
| `desv_estandar_pp` | Desviación estándar del desvío (pp) |
| `desvio_min_pp`, `desvio_max_pp` | Desvío mínimo y máximo del periodo (pp) |
| `pct_dias_sobre_referencia`, `pct_dias_igual_referencia`, `pct_dias_bajo_referencia` | % de días en que la interbancaria quedó por encima, igual o por debajo de la tasa de referencia |

## 5. Archivos crudos (`datos_crudos/`)

| Variable | Descripción |
|---|---|
| `fecha_bcrp` | Fecha tal como la entrega la API, en texto (ej. `05.Ene.15`; setiembre aparece como `Set`) |
| Demás columnas | Mismos nombres que la sección 1, con los valores en texto tal como salen de la API. `n.d.` = dato no disponible según el BCRP |
