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

## 3. Base de los modelos (`salidas/datos_analisis_2024200505K.csv`)

Generada por `04_analisis.py`; 2869 filas (se elimina la primera, que no tiene cuenta corriente rezagada). Su SHA-256 queda en `salidas/hash_2024200505K.txt`.

| Variable | Descripción | Unidad | Construcción |
|---|---|---|---|
| `fecha` | Fecha de la observación | AAAA-MM-DD | – |
| `tasa_interbancaria_on_end` | Tasa interbancaria overnight (endógena) | % anual | igual que en la sección 1 |
| `tasa_referencia_escalon` | Tasa de referencia como variable de escalones: la última tasa publicada sigue vigente hasta la siguiente decisión del Directorio | % anual | forward-fill de los valores publicados de `tasa_referencia_exo` (se descartan los interpolados en `03`) |
| `tasa_cdbcrp_saldo_exo` | Tasa del saldo de CD BCRP | % anual | igual que en la sección 1 |
| `ln_depositos` | Logaritmo natural de los depósitos del sector público | ln(millones de S/) | `ln(depositos_sector_publico_saldo_exo)` |
| `ln_ctacte_L1` | Logaritmo natural de las cuentas corrientes de bancos, rezagada 1 día | ln(millones de S/) | `ln(cuentas_corrientes_bancos_bcrp_saldo_exo_L1)` |

## 4. Desvío respecto de la tasa de política

`desvío = tasa_interbancaria_on_end − tasa_referencia_escalon`, en puntos porcentuales (pp). Positivo = la interbancaria está por encima de la tasa de política. Se calcula en memoria en `04_analisis.py`. La **muestra publicada** son las jornadas en que el BCRP publicó la interbancaria y la referencia (sin imputación); la **completa** incluye los días imputados.

Columnas de `tabla_desvio_por_anio` (columna `fecha` = año), `tabla_desvio_por_etapa` (columna `etapa`) y `tabla_comparacion_desvio` (columna `muestra`):

| Columna | Descripción |
|---|---|
| `n` | Número de jornadas |
| `medio` | Promedio del desvío (pp) |
| `abs_medio` | Promedio del valor absoluto del desvío (pp): cuánto se aleja, sin importar el signo |
| `de` | Desviación estándar del desvío (pp) |
| `min`, `max` | Desvío mínimo y máximo (pp) |
| `pct_sobre`, `pct_igual`, `pct_bajo` | % de jornadas con la interbancaria por encima, igual o por debajo de la referencia |
| `pct_banda10`, `pct_sobre25` | Solo en la comparación: % de jornadas con \|desvío\| ≤ 0.10 pp y con \|desvío\| > 0.25 pp |

`tabla_top10_desvios` tiene `fecha`, `ib` (interbancaria), `ref_escalon` (referencia en escalones) y `desvio` de las 10 jornadas publicadas con mayor desvío absoluto.

## 5. Archivos crudos (`datos_crudos/`)

| Variable | Descripción |
|---|---|
| `fecha_bcrp` | Fecha tal como la entrega la API, en texto (ej. `05.Ene.15`; setiembre aparece como `Set`) |
| Demás columnas | Mismos nombres que la sección 1, con los valores en texto tal como salen de la API. `n.d.` = dato no disponible según el BCRP |
