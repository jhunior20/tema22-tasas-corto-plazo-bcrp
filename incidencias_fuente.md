# Incidencias de la fuente

Tema 22 – Isai Jhunior Laymito Tacza (2024200505K)

Fuente: API BCRPData del BCRP. Periodo consultado: 01/01/2015 – 31/12/2025. Fecha de extracción: 24/09/2026.

Este archivo registra los problemas encontrados **en los datos o en el comportamiento de la fuente**, y cómo se trató cada uno. Los archivos de `datos_crudos/` se conservan sin editar; todo tratamiento se hace en `03_limpieza_datos.py`.

## 1. Valor malformado en la tasa de referencia (14/09/2017)

| Campo | Detalle |
|---|---|
| Serie | PD12301MD – Tasa de Referencia de la Política Monetaria |
| Fecha | 14.Set.17 |
| Valor entregado por la API | `"3.7512301,2011-04-07,3.75"` |
| Valores vecinos | 13.Set.17 = 3.75 · 15.Set.17 = 3.5 |
| Verificación | Se volvió a consultar la API solo para esas fechas y devolvió el mismo valor. Es un error de la fuente, no del script de extracción. |
| Tratamiento | `03_limpieza_datos.py` no puede convertirlo a número y lo marca como faltante (NaN). Luego se rellena por interpolación lineal (3.625) y queda marcado como `interpolacion_lineal` en `tasa_referencia_exo_metodo_imputacion`. |

## 2. Días con dato no disponible (`n.d.`)

La API devuelve el texto `n.d.` en los días sin dato. Conteo en el crudo:

| Serie | Días con `n.d.` |
|---|---|
| PD04692MD – Interbancaria | 131 |
| PD12301MD – Tasa de referencia | 106 |
| PD04679MD – CD BCRP | 128 |
| PD04668MD – Depósitos sector público | 128 |
| PD04665MD – Cuentas corrientes de bancos | 128 |

- En 106 fechas las 5 series vienen en `n.d.` a la vez. Coinciden con feriados en el Perú (ej. 01.Nov, 08.Dic, Semana Santa, 29.Jun, 28–29.Jul, 30.Ago), además de los feriados de la cumbre APEC (17–18.Nov.16).
- La interbancaria tiene 25 días adicionales con `n.d.` en los que la tasa de referencia sí tiene dato.
- CD BCRP, depósitos y cuentas corrientes empiezan en `n.d.` el 01 y 02.Ene.15, por lo que no hay un dato anterior para rellenar.

**Tratamiento:** `n.d.` se convierte en NaN y se rellena según el tipo de variable: interpolación lineal en las tasas, y forward-fill de máximo 5 días en los saldos. Los huecos al inicio de la serie se rellenan con bfill. Cada celda rellenada queda identificada en su columna `_metodo_imputacion`.

### Limitación del tratamiento en la tasa de referencia

Se usó interpolación lineal en las tres tasas para mantener un mismo criterio. La tasa de referencia, sin embargo, cambia en saltos. Por eso, cuando un cambio de tasa coincide con un día sin dato, la interpolación produce valores intermedios que el BCRP nunca fijó. Ocurre en 5 de los 107 días interpolados:

| Fecha | Valor interpolado | Contexto |
|---|---|---|
| 14/09/2017 | 3.625 | Valor malformado de la API (incidencia 1); la tasa pasó de 3.75 a 3.50 |
| 09/04/2020 | 0.917 | Semana Santa; la tasa bajó de 1.25 a 0.25 |
| 10/04/2020 | 0.583 | Semana Santa; la tasa bajó de 1.25 a 0.25 |
| 08/12/2022 | 7.333 | Feriado; la tasa subió de 7.25 a 7.50 |
| 09/12/2022 | 7.417 | Feriado; la tasa subió de 7.25 a 7.50 |

Estos 5 días representan el 0.17 % de la muestra (5 de 2870) y quedan identificados en la columna `tasa_referencia_exo_metodo_imputacion`. En los otros 102 días interpolados, la tasa era igual antes y después del hueco, así que el valor rellenado coincide con la tasa vigente.

**Corrección en el análisis:** `04_analisis.py` no usa la tasa de referencia interpolada. La reconstruye como variable de escalones (`tasa_referencia_escalon`): toma solo los valores publicados y arrastra la última tasa vigente hasta la siguiente decisión del Directorio. Así ningún día tiene un valor intermedio que el BCRP no fijó. `datos_procesados` se conserva sin cambios, con su columna de imputación, para mantener la trazabilidad. Además, el desvío se calcula principalmente sobre las jornadas con ambas tasas publicadas, y la muestra completa se reporta como robustez (`tabla_comparacion_desvio`).

## 3. Orden de las series en consultas múltiples

Cuando se piden varias series en una sola consulta, la API las devuelve ordenadas por código (no en el orden pedido). Además, el campo `config.series[].name` trae la descripción de la serie y no su código. Por eso no se puede saber con seguridad a qué serie corresponde cada valor.

**Tratamiento:** `01_extraccion_api.py` consulta cada serie por separado y luego las une por fecha.

## 4. Formato de fecha

La API entrega las fechas como texto `DD.Mes.AA` en español (ej. `05.Ene.15`), y setiembre aparece como `Set`, no `Sep`.

**Tratamiento:** `03_limpieza_datos.py` convierte las fechas con un mapeo explícito de meses (acepta `Set` y `Sep`). No se usa `%b`, porque depende del idioma del sistema operativo.
