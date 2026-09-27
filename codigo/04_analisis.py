# NOMBRES Y APELLIDOS COMPLETOS: Isai Jhunior Laymito Tacza
# CODIGO DE MATRICULA: 2024200505K
# TEMA: N.o 22 - Tasas de corto plazo en el Peru: interbancaria, certificados
#       del BCRP y tasa de referencia
# FECHA DE EXTRACCION: 24/09/2026
"""
04_analisis.py

TEMA N.22: Tasas de corto plazo en el Peru: interbancaria, certificados
del BCRP y tasa de referencia.

OBJETIVO DE INVESTIGACION: Analizar la formacion de las tasas de muy
corto plazo y su desvio respecto de la tasa de politica.

Como responde este script al objetivo:

1) FORMACION de la tasa de muy corto plazo: regresion de la tasa
   interbancaria overnight sobre la tasa de politica, la tasa de los
   CD BCRP y los dos factores de liquidez (ver el modelo mas abajo).

2) DESVIO respecto de la tasa de politica: se calcula, dia por dia,
       desvio = interbancaria - referencia   (en puntos porcentuales)
   y se resume por anio (tabla y figura). Como el desvio es la
   endogena menos la tasa de referencia, el mismo modelo lo explica:
       desvio = b0 + (b1 - 1)*referencia + b2*cdbcrp
                   + b3*ln(depositos) + b4*ln(ctacte_L1) + error
   Por eso b2, b3 y b4 miden tambien el efecto de cada variable sobre
   el desvio, y la prueba H0: b1 = 1 (traspaso completo de la tasa de
   politica) indica si el desvio cambia con el nivel de esa tasa.

Estimaciones, tablas y figuras del articulo, generadas desde el archivo
procesado y guardadas en /salidas, tal como exige el numeral 2.4.2 de
la consigna.

Input : /datos_procesados/datos_procesados_<codigo>.csv (de 03_limpieza_datos.py)
Output: /salidas/datos_analisis_<codigo>.csv
        /salidas/tabla_descriptivos_<codigo>.csv
        /salidas/tabla_correlacion_<codigo>.csv
        /salidas/tabla_regresion_<codigo>.csv
        /salidas/tabla_prueba_traspaso_<codigo>.csv
        /salidas/tabla_desvio_por_anio_<codigo>.csv
        /salidas/tabla_desvio_por_etapa_<codigo>.csv
        /salidas/tabla_top10_desvios_<codigo>.csv
        /salidas/tabla_diagnosticos_regresion_<codigo>.csv
        /salidas/fig_interbancaria_vs_referencia_<codigo>.png
        /salidas/fig_variables_liquidez_<codigo>.png
        /salidas/fig_correlacion_<codigo>.png
        /salidas/fig_desvio_interbancaria_<codigo>.png
        Figuras complementarias (tasas, liquidez y desvio):
        /salidas/fig_cdbcrp_vs_referencia_<codigo>.png
        /salidas/fig_histograma_desvio_<codigo>.png
        /salidas/fig_boxplot_desvio_anual_<codigo>.png
        /salidas/fig_estado_diario_por_anio_<codigo>.png
        /salidas/fig_scatter_interbancaria_referencia_<codigo>.png
        /salidas/fig_distribucion_tasas_<codigo>.png
        /salidas/fig_depositos_publicos_<codigo>.png
        /salidas/fig_cuenta_corriente_detalle2023_<codigo>.png
        /salidas/fig_volatilidad_movil_<codigo>.png
        /salidas/fig_desvio_absoluto_por_anio_<codigo>.png
        /salidas/fig_heatmap_desvio_mensual_<codigo>.png
        /salidas/fig_ctacte_zoom_trimestre_<codigo>.png
        /salidas/fig_depositos_vs_ctacte_scatter_<codigo>.png
        /salidas/fig_correlacion_movil_90d_<codigo>.png
        /salidas/fig_variacion_diaria_interbancaria_<codigo>.png
        /salidas/fig_histograma_variacion_diaria_<codigo>.png
        /salidas/fig_promedio_movil_ctacte_30d_<codigo>.png
        /salidas/fig_promedio_movil_depositos_90d_<codigo>.png
        /salidas/fig_boxplot_desvio_por_etapa_<codigo>.png
        /salidas/fig_dispersion_volatilidad_desvio_<codigo>.png
        /salidas/fig_ecdf_desvio_<codigo>.png
        /salidas/fig_evolucion_cdbcrp_suavizada_<codigo>.png
        /salidas/fig_top10_desvios_<codigo>.png
        Diagnostico del modelo de regresion:
        /salidas/fig_residuos_vs_ajustados_<codigo>.png
        /salidas/fig_residuos_tiempo_<codigo>.png
        /salidas/fig_qq_residuos_<codigo>.png
        /salidas/fig_histograma_residuos_<codigo>.png
        /salidas/fig_autocorrelacion_residuos_<codigo>.png

Modelo estimado (variable endogena ~ 4 exogenas), en niveles para las
tasas y en logaritmo natural para las 2 variables de liquidez (estan en
millones de soles, escala muy distinta a las tasas en %):

    interbancaria = b0 + b1*referencia + b2*cdbcrp
                       + b3*ln(depositos_sector_publico)
                       + b4*ln(cuentas_corrientes_bancos_L1) + error

La exogena 4 entra REZAGADA un periodo (columna "..._L1" ya generada en
03_limpieza_datos.py), para mitigar el problema de simultaneidad entre
las decisiones de liquidez del BCRP y la tasa interbancaria del mismo
dia.

Los datos son SERIES DE TIEMPO (una sola unidad -- el mercado
interbancario peruano -- observada en el tiempo), no panel data (que
requeriria varias unidades, ej. varios paises). Por eso el modelo es
una regresion de series de tiempo con errores estandar robustos a
autocorrelacion (Newey-West / HAC), no un modelo de panel.

Los outliers marcados por 03_limpieza_datos.py NO se eliminan de la
regresion: son datos reales o imputados ya validados, solo senalados
como atipicos. Eliminarlos violaria la politica de no alterar/borrar
datos (numeral 2.4.6).
"""

import os
import sys
import logging

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # no necesita pantalla, solo guardar archivos .png
import matplotlib.pyplot as plt
import statsmodels.api as sm
from statsmodels.stats.stattools import durbin_watson, jarque_bera

# ---------------------------------------------------------------------------
# 1) RUTAS Y PARAMETROS
# ---------------------------------------------------------------------------
CODIGO_MATRICULA = "2024200505K"

try:
    _DIRECTORIO_SCRIPT = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _DIRECTORIO_SCRIPT = os.getcwd()

CARPETA_PROCESADOS = os.path.join(_DIRECTORIO_SCRIPT, "..", "datos_procesados")
CARPETA_SALIDAS = os.path.join(_DIRECTORIO_SCRIPT, "..", "salidas")
ARCHIVO_LOG = os.path.join(_DIRECTORIO_SCRIPT, "..", "log_ejecucion.txt")

RUTA_PROCESADO = os.path.join(CARPETA_PROCESADOS, f"datos_procesados_{CODIGO_MATRICULA}.csv")

# Las 7 columnas que realmente entran al analisis: fecha + endogena +
# 3 exogenas en nivel + exogena 4 (original y rezagada). Las columnas de
# trazabilidad (metodo_imputacion, outlier) no entran al modelo.
COL_FECHA = "fecha"
COL_ENDOGENA = "tasa_interbancaria_on_end"
COL_EXO1_REFERENCIA = "tasa_referencia_exo"
COL_EXO2_CDBCRP = "tasa_cdbcrp_saldo_exo"
COL_EXO3_DEPOSITOS = "depositos_sector_publico_saldo_exo"
COL_EXO4_CTACTE_L1 = "cuentas_corrientes_bancos_bcrp_saldo_exo_L1"

# Desvio de la interbancaria respecto de la tasa de politica (se calcula
# en memoria en este script; no esta en datos_procesados)
COL_DESVIO = "desvio_interbancaria_referencia_pp"

COLUMNAS_TASAS = [COL_ENDOGENA, COL_EXO1_REFERENCIA, COL_EXO2_CDBCRP]

# Etapas de la politica monetaria en 2015-2025, delimitadas por los
# cambios de la tasa de referencia observados en los datos del BCRP:
# (nombre, fecha de inicio, fecha de fin). Se usan para agrupar el desvio.
ETAPAS_POLITICA = [
    ("1. Alzas y estabilidad\n(3.25 a 4.25%)", "2015-01-01", "2017-05-11"),
    ("2. Relajamiento gradual\n(4.25 a 2.25%)", "2017-05-12", "2020-03-19"),
    ("3. Estimulo COVID-19\n(minimo 0.25%)", "2020-03-20", "2021-08-12"),
    ("4. Alzas por inflacion\n(0.25 a 7.75%)", "2021-08-13", "2023-09-14"),
    ("5. Recortes\n(7.75 a 4.25%)", "2023-09-15", "2025-12-31"),
]

# Columnas de trazabilidad que se leen solo para marcar, en las figuras,
# los dias cuyo valor fue imputado en 03_limpieza_datos.py
COLUMNAS_IMPUTACION_DESVIO = [
    "tasa_interbancaria_on_end_metodo_imputacion",
    "tasa_referencia_exo_metodo_imputacion",
]

COLUMNAS_ANALISIS = [
    COL_FECHA, COL_ENDOGENA, COL_EXO1_REFERENCIA, COL_EXO2_CDBCRP,
    COL_EXO3_DEPOSITOS, "cuentas_corrientes_bancos_bcrp_saldo_exo", COL_EXO4_CTACTE_L1,
]


# ---------------------------------------------------------------------------
# 2) LOG
# ---------------------------------------------------------------------------
def configurar_logging():
    os.makedirs(CARPETA_SALIDAS, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(ARCHIVO_LOG, mode="a", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ---------------------------------------------------------------------------
# 3) CARGA (solo las columnas necesarias)
# ---------------------------------------------------------------------------
def cargar_datos_procesados():
    """Lee datos_procesados y se queda con fecha + las 5 variables + la
    version rezagada de la exogena 4. De las columnas auxiliares solo se
    leen las de imputacion de la interbancaria y de la referencia, para
    marcar en la figura de los 10 mayores desvios los dias imputados;
    no entran al modelo ni a datos_analisis."""
    df = pd.read_csv(RUTA_PROCESADO, usecols=COLUMNAS_ANALISIS + COLUMNAS_IMPUTACION_DESVIO,
                     dtype={c: str for c in COLUMNAS_IMPUTACION_DESVIO})
    df[COL_FECHA] = pd.to_datetime(df[COL_FECHA])
    df = df.sort_values(COL_FECHA).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# 4) ESTADISTICA DESCRIPTIVA Y CORRELACION (tablas)
# ---------------------------------------------------------------------------
def tabla_descriptivos(df):
    columnas_describir = [
        COL_ENDOGENA, COL_EXO1_REFERENCIA, COL_EXO2_CDBCRP,
        COL_EXO3_DEPOSITOS, "cuentas_corrientes_bancos_bcrp_saldo_exo",
    ]
    tabla = df[columnas_describir].describe().T
    tabla.insert(0, "variable", tabla.index)
    return tabla.reset_index(drop=True)


def tabla_correlacion(df, columnas_modelo):
    return df[columnas_modelo].corr()


def figura_correlacion(matriz_corr, ruta_salida):
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(matriz_corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(matriz_corr.columns)))
    ax.set_yticks(range(len(matriz_corr.columns)))
    ax.set_xticklabels(matriz_corr.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(matriz_corr.columns, fontsize=8)
    for i in range(len(matriz_corr.columns)):
        for j in range(len(matriz_corr.columns)):
            ax.text(j, i, f"{matriz_corr.values[i, j]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax, label="Correlacion")
    ax.set_title("Matriz de correlacion - Tema 22")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 5) FIGURAS DE SERIES DE TIEMPO
# ---------------------------------------------------------------------------
def figura_interbancaria_vs_referencia(df, ruta_salida):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(df[COL_FECHA], df[COL_ENDOGENA], label="Interbancaria overnight", linewidth=0.9)
    ax.plot(df[COL_FECHA], df[COL_EXO1_REFERENCIA], label="Tasa de referencia", linewidth=0.9)
    ax.set_ylabel("%")
    ax.set_title("Interbancaria vs. tasa de referencia (2015-2025)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_variables_liquidez(df, ruta_salida):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(df[COL_FECHA], df[COL_EXO3_DEPOSITOS], label="Depositos sector publico", linewidth=0.8)
    ax.plot(df[COL_FECHA], df["cuentas_corrientes_bancos_bcrp_saldo_exo"],
            label="Cuentas corrientes de bancos", linewidth=0.8)
    ax.set_ylabel("Millones S/")
    ax.set_title("Variables de liquidez (2015-2025)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


# Colores fijos por variable (los de matplotlib por defecto, los mismos de
# la figura interbancaria vs. referencia), para que cada tasa tenga
# siempre el mismo color en todas las figuras.
COLOR_INTERBANCARIA = "C0"
COLOR_REFERENCIA = "C1"
COLOR_CDBCRP = "C2"

# Ventana de la volatilidad movil, en dias habiles (filas de la base)
VENTANA_VOLATILIDAD = 30

# Anio que se muestra en el detalle de las cuentas corrientes
ANIO_DETALLE_CTACTE = 2023

# Trimestre del zoom a las cuentas corrientes (inicio, fin, etiqueta)
TRIMESTRE_ZOOM_CTACTE = ("2023-01-01", "2023-03-31", "I trimestre 2023")

# Ventanas moviles, en dias habiles (filas de la base)
VENTANA_CORRELACION = 90
VENTANA_PROMEDIO_CTACTE = 30
VENTANA_PROMEDIO_DEPOSITOS = 90
VENTANA_PROMEDIO_CDBCRP = 90


def figura_cdbcrp_vs_referencia(df, ruta_salida):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(df[COL_FECHA], df[COL_EXO2_CDBCRP], label="Tasa del saldo de CD BCRP",
            color=COLOR_CDBCRP, linewidth=0.9)
    ax.plot(df[COL_FECHA], df[COL_EXO1_REFERENCIA], label="Tasa de referencia",
            color=COLOR_REFERENCIA, linewidth=0.9)
    ax.set_ylabel("%")
    ax.set_title("Tasa de CD BCRP vs. tasa de referencia (2015-2025)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_depositos_publicos(df, ruta_salida):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(df[COL_FECHA], df[COL_EXO3_DEPOSITOS], color="C0", linewidth=0.8)
    ax.set_ylabel("Millones S/")
    ax.set_title("Depositos del sector publico en el BCRP (2015-2025)")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_cuenta_corriente_detalle(df, ruta_salida):
    """Un solo anio de las cuentas corrientes (sin rezago), para que se
    vea el patron de 'diente de sierra': los bancos acumulan saldo y lo
    reducen dentro de cada periodo de encaje (mensual)."""
    anio = df[df[COL_FECHA].dt.year == ANIO_DETALLE_CTACTE]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(anio[COL_FECHA], anio["cuentas_corrientes_bancos_bcrp_saldo_exo"],
            color="C1", linewidth=0.9, marker="o", markersize=2)
    ax.set_ylabel("Millones S/")
    ax.set_title(f"Cuentas corrientes de bancos en el BCRP, detalle {ANIO_DETALLE_CTACTE}")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_distribucion_tasas(df, ruta_salida):
    """Histogramas de las tres tasas con los mismos intervalos de 0.25
    pp, dibujados como contorno (y con distinto tipo de linea) para que
    se puedan comparar sin taparse."""
    intervalos = np.arange(0, np.ceil(df[COLUMNAS_TASAS].max().max()) + 0.25, 0.25)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for col, etiqueta, color, estilo in [
        (COL_ENDOGENA, "Interbancaria overnight", COLOR_INTERBANCARIA, "-"),
        (COL_EXO1_REFERENCIA, "Tasa de referencia", COLOR_REFERENCIA, "--"),
        (COL_EXO2_CDBCRP, "Tasa del saldo de CD BCRP", COLOR_CDBCRP, ":"),
    ]:
        ax.hist(df[col], bins=intervalos, histtype="step", linewidth=1.5,
                color=color, linestyle=estilo, label=etiqueta)
    ax.set_xlabel("%")
    ax.set_ylabel("Numero de dias")
    ax.set_title("Distribucion de las tres tasas (2015-2025)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_scatter_interbancaria_referencia(df, ruta_salida):
    """Cada punto es un dia. Si la interbancaria siguiera 1 a 1 a la
    tasa de politica, todos los puntos caerian sobre la linea de 45
    grados; la distancia vertical a esa linea es el desvio."""
    fig, ax = plt.subplots(figsize=(6.5, 6))
    ax.scatter(df[COL_EXO1_REFERENCIA], df[COL_ENDOGENA], s=10, alpha=0.35,
               color=COLOR_INTERBANCARIA, label=f"Dias (n = {len(df)})")
    limites = [0, np.ceil(df[[COL_ENDOGENA, COL_EXO1_REFERENCIA]].max().max())]
    ax.plot(limites, limites, color="black", linewidth=1, linestyle="--",
            label="Traspaso unitario (45 grados)")
    ax.set_xlim(limites)
    ax.set_ylim(limites)
    ax.set_aspect("equal")
    ax.set_xlabel("Tasa de referencia (%)")
    ax.set_ylabel("Interbancaria overnight (%)")
    ax.set_title("Interbancaria vs. tasa de referencia, dia a dia")
    ax.legend()
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_volatilidad_movil(df, ruta_salida):
    """Desviacion estandar movil de la interbancaria y de su desvio. La
    del nivel sube tambien cuando el BCRP mueve la tasa de politica (ej.
    2022); la del desvio solo mide la inestabilidad alrededor de ella."""
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(df[COL_FECHA], df[COL_ENDOGENA].rolling(VENTANA_VOLATILIDAD).std(),
            color=COLOR_INTERBANCARIA, linewidth=0.9, label="Interbancaria (nivel)")
    ax.plot(df[COL_FECHA], df[COL_DESVIO].rolling(VENTANA_VOLATILIDAD).std(),
            color="C3", linewidth=0.9, linestyle="--",
            label="Desvio respecto de la referencia")
    ax.set_ylabel("Desviacion estandar (pp)")
    ax.set_title(f"Volatilidad movil de {VENTANA_VOLATILIDAD} dias habiles (2015-2025)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_serie_con_promedio_movil(df, columna, ventana, color, etiqueta, unidad,
                                    titulo, ruta_salida):
    """Serie diaria (tenue, de fondo) y su promedio movil (linea
    principal), para ver la tendencia sin el ruido de cada dia."""
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(df[COL_FECHA], df[columna], color="0.75", linewidth=0.6,
            label=f"{etiqueta} (diario)")
    ax.plot(df[COL_FECHA], df[columna].rolling(ventana).mean(), color=color,
            linewidth=1.6, label=f"Promedio movil de {ventana} dias habiles")
    ax.set_ylabel(unidad)
    ax.set_title(titulo)
    ax.legend()
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_promedio_movil_ctacte(df, ruta_salida):
    figura_serie_con_promedio_movil(
        df, "cuentas_corrientes_bancos_bcrp_saldo_exo", VENTANA_PROMEDIO_CTACTE, "C1",
        "Cuentas corrientes de bancos", "Millones S/",
        "Cuentas corrientes de bancos en el BCRP: tendencia suavizada (2015-2025)",
        ruta_salida)


def figura_promedio_movil_depositos(df, ruta_salida):
    figura_serie_con_promedio_movil(
        df, COL_EXO3_DEPOSITOS, VENTANA_PROMEDIO_DEPOSITOS, "C0",
        "Depositos del sector publico", "Millones S/",
        "Depositos del sector publico en el BCRP: tendencia suavizada (2015-2025)",
        ruta_salida)


def figura_cdbcrp_suavizada(df, ruta_salida):
    figura_serie_con_promedio_movil(
        df, COL_EXO2_CDBCRP, VENTANA_PROMEDIO_CDBCRP, COLOR_CDBCRP,
        "Tasa del saldo de CD BCRP", "%",
        "Tasa de CD BCRP y su tendencia (2015-2025)", ruta_salida)


def figura_ctacte_zoom_trimestre(df, ruta_salida):
    """Zoom de un trimestre a las cuentas corrientes: con pocos dias en
    pantalla se ve cada 'diente' del encaje (el saldo sube al inicio del
    periodo de encaje y baja hasta el final)."""
    inicio, fin, etiqueta = TRIMESTRE_ZOOM_CTACTE
    tramo = df[(df[COL_FECHA] >= inicio) & (df[COL_FECHA] <= fin)]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(tramo[COL_FECHA], tramo["cuentas_corrientes_bancos_bcrp_saldo_exo"],
            color="C1", linewidth=1.2, marker="o", markersize=4)
    ax.set_ylabel("Millones S/")
    ax.set_title(f"Cuentas corrientes de bancos en el BCRP, {etiqueta}")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_depositos_vs_ctacte(df, ruta_salida):
    """Relacion entre los dos factores de liquidez, dia a dia. El color
    indica el anio, para ver si la relacion cambia en el tiempo."""
    fig, ax = plt.subplots(figsize=(8, 5.5))
    puntos = ax.scatter(df[COL_EXO3_DEPOSITOS], df["cuentas_corrientes_bancos_bcrp_saldo_exo"],
                        c=df[COL_FECHA].dt.year, cmap="viridis", s=8, alpha=0.6)
    fig.colorbar(puntos, ax=ax, label="Anio")
    ax.set_xlabel("Depositos del sector publico (millones S/)")
    ax.set_ylabel("Cuentas corrientes de bancos (millones S/)")
    ax.set_title("Depositos publicos vs. cuentas corrientes de bancos en el BCRP")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_correlacion_movil(df, ruta_salida):
    """Correlacion movil entre la interbancaria y la referencia. Queda
    en blanco en los tramos en que alguna de las dos tasas no cambia en
    toda la ventana (ej. 2020-2021 en 0.25%): con una variable constante
    la correlacion no esta definida."""
    correlacion = df[COL_ENDOGENA].rolling(VENTANA_CORRELACION).corr(df[COL_EXO1_REFERENCIA])
    # Donde alguna de las dos tasas es constante en la ventana (maximo =
    # minimo) la correlacion no existe; se fuerza NaN para no mostrar el
    # 0 que devuelve pandas en esos casos.
    for col in (COL_ENDOGENA, COL_EXO1_REFERENCIA):
        ventana = df[col].rolling(VENTANA_CORRELACION)
        correlacion = correlacion.mask(ventana.max() - ventana.min() < 1e-9)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(df[COL_FECHA], correlacion, color=COLOR_INTERBANCARIA, linewidth=0.9)
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_ylim(-1.05, 1.05)
    ax.set_ylabel("Correlacion")
    ax.set_title(f"Correlacion movil de {VENTANA_CORRELACION} dias habiles: "
                 "interbancaria vs. referencia")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def histograma_centrado_en_cero(ax, valores, ancho, color):
    """Histograma con intervalos de 'ancho' centrados en cero y eje
    vertical logaritmico (la mayoria de valores es cero)."""
    tope = np.ceil(valores.abs().max() / ancho) * ancho
    intervalos = np.arange(-tope - ancho / 2, tope + ancho, ancho)
    ax.hist(valores, bins=intervalos, color=color, edgecolor="white", linewidth=0.5)
    ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_yscale("log")
    ax.set_ylabel("Numero de dias (escala log)")
    ax.text(0.02, 0.95, f"{(valores == 0).mean() * 100:.1f}% de los dias en cero",
            transform=ax.transAxes, va="top")


def variacion_diaria_interbancaria(df):
    """Primera diferencia de la interbancaria (hoy - dia habil anterior),
    en pp, redondeada a 6 decimales para quitar el ruido de coma flotante."""
    return df[COL_ENDOGENA].diff().round(6)


def figura_variacion_diaria_interbancaria(df, ruta_salida):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(df[COL_FECHA], variacion_diaria_interbancaria(df),
            color=COLOR_INTERBANCARIA, linewidth=0.7)
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_ylabel("Variacion diaria (pp)")
    ax.set_title("Variacion diaria de la interbancaria overnight (2015-2025)")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_histograma_variacion_diaria(df, ruta_salida):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    histograma_centrado_en_cero(ax, variacion_diaria_interbancaria(df).dropna(), 0.05,
                                COLOR_INTERBANCARIA)
    ax.set_xlabel("Variacion diaria de la interbancaria (pp)")
    ax.set_title("Distribucion de la variacion diaria de la interbancaria (2015-2025)")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 6) DESVIO DE LA INTERBANCARIA RESPECTO DE LA TASA DE POLITICA
# ---------------------------------------------------------------------------
def calcular_desvio(df):
    """Desvio diario de la interbancaria respecto de la tasa de
    referencia, en puntos porcentuales (pp). Positivo = la interbancaria
    esta por encima de la tasa de politica. Se redondea a 6 decimales
    solo para quitar el ruido de la resta en coma flotante (ej. 3.55 -
    3.5 = 0.0499999...), sin cambiar ningun valor real."""
    df = df.copy()
    df[COL_DESVIO] = (df[COL_ENDOGENA] - df[COL_EXO1_REFERENCIA]).round(6)
    return df


def resumir_desvio(desvio):
    return {
        "n_dias": len(desvio),
        "desvio_medio_pp": desvio.mean(),
        "desvio_absoluto_medio_pp": desvio.abs().mean(),
        "desv_estandar_pp": desvio.std(),
        "desvio_min_pp": desvio.min(),
        "desvio_max_pp": desvio.max(),
        "pct_dias_sobre_referencia": (desvio > 0).mean() * 100,
        "pct_dias_igual_referencia": (desvio == 0).mean() * 100,
        "pct_dias_bajo_referencia": (desvio < 0).mean() * 100,
    }


def tabla_desvio_por_anio(df):
    """Resumen del desvio por anio y para toda la muestra (ultima fila):
    cuanto se aleja en promedio la interbancaria de la tasa de politica,
    que tan volatil es ese desvio y en que proporcion de dias queda por
    encima, igual o por debajo de la referencia."""
    anios = df[COL_FECHA].dt.year
    filas = [
        {"periodo": str(anio), **resumir_desvio(desvio)}
        for anio, desvio in df[COL_DESVIO].groupby(anios)
    ]
    filas.append({"periodo": f"{anios.min()}-{anios.max()}", **resumir_desvio(df[COL_DESVIO])})
    return pd.DataFrame(filas)


def figura_desvio(df, ruta_salida):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(df[COL_FECHA], df[COL_DESVIO], label="Interbancaria - referencia", linewidth=0.8)
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", label="Sin desvio")
    ax.set_ylabel("Puntos porcentuales")
    ax.set_title("Desvio de la interbancaria respecto de la tasa de referencia (2015-2025)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_histograma_desvio(df, ruta_salida):
    """Distribucion del desvio diario, en intervalos de 0.05 pp centrados
    en cero. El eje vertical va en escala logaritmica porque la mayoria
    de dias tiene desvio cero y, en escala normal, las colas (los dias
    con desvios grandes) no se verian."""
    fig, ax = plt.subplots(figsize=(10, 4.5))
    histograma_centrado_en_cero(ax, df[COL_DESVIO], 0.05, "C0")
    ax.set_xlabel("Desvio interbancaria - referencia (pp)")
    ax.set_title("Distribucion del desvio diario (2015-2025)")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_boxplot_desvio_anual(df, ruta_salida):
    """Caja y bigotes del desvio por anio. En los anios en que casi
    todos los dias tienen desvio cero, la caja se reduce a una linea en
    cero y solo se ven los dias atipicos como puntos."""
    grupos = df[COL_DESVIO].groupby(df[COL_FECHA].dt.year)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.boxplot([g.values for _, g in grupos], tick_labels=[str(a) for a, _ in grupos],
               flierprops={"marker": "o", "markersize": 3, "alpha": 0.5})
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_ylabel("Desvio (pp)")
    ax.set_title("Desvio de la interbancaria respecto de la referencia, por anio")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_estado_diario_por_anio(tabla_desvio, ruta_salida):
    """Barras apiladas al 100%: en que % de dias de cada anio la
    interbancaria quedo por debajo, igual o por encima de la tasa de
    politica (la 'meta' operativa del BCRP). Usa la tabla por anio, sin
    la fila del total."""
    por_anio = tabla_desvio.iloc[:-1]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    base = np.zeros(len(por_anio))
    for col, etiqueta, color in [
        ("pct_dias_bajo_referencia", "Debajo de la referencia", "C0"),
        ("pct_dias_igual_referencia", "Igual a la referencia", "0.75"),
        ("pct_dias_sobre_referencia", "Encima de la referencia", "C1"),
    ]:
        ax.bar(por_anio["periodo"], por_anio[col], bottom=base, width=0.7,
               color=color, edgecolor="white", linewidth=1, label=etiqueta)
        base += por_anio[col].to_numpy()
    ax.set_ylim(0, 100)
    ax.set_ylabel("% de dias del anio")
    ax.set_title("Posicion diaria de la interbancaria frente a la tasa de referencia, por anio")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3, frameon=False)
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_desvio_absoluto_por_anio(tabla_desvio, ruta_salida):
    """Cuanto se alejo en promedio la interbancaria de la tasa de
    politica cada anio, sin importar si fue por encima o por debajo."""
    por_anio = tabla_desvio.iloc[:-1]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(por_anio["periodo"], por_anio["desvio_absoluto_medio_pp"], width=0.7, color="C0")
    ax.set_ylabel("Desvio absoluto medio (pp)")
    ax.set_title("Desvio absoluto medio de la interbancaria respecto de la referencia, por anio")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


MESES_ABREVIADOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                    "Jul", "Ago", "Set", "Oct", "Nov", "Dic"]


def figura_heatmap_desvio_mensual(df, ruta_salida):
    """Desvio medio de cada mes (columnas) de cada anio (filas). Escala
    divergente centrada en cero: rojo = interbancaria por encima de la
    referencia, azul = por debajo, blanco = sin desvio."""
    tabla = df.pivot_table(index=df[COL_FECHA].dt.year, columns=df[COL_FECHA].dt.month,
                           values=COL_DESVIO, aggfunc="mean")
    limite = np.nanmax(np.abs(tabla.values))
    fig, ax = plt.subplots(figsize=(10, 5.5))
    im = ax.imshow(tabla.values, cmap="RdBu_r", vmin=-limite, vmax=limite, aspect="auto")
    ax.set_xticks(range(len(tabla.columns)))
    ax.set_xticklabels([MESES_ABREVIADOS[m - 1] for m in tabla.columns])
    ax.set_yticks(range(len(tabla.index)))
    ax.set_yticklabels(tabla.index)
    fig.colorbar(im, ax=ax, label="Desvio medio (pp)")
    ax.set_title("Desvio medio mensual de la interbancaria respecto de la referencia")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def asignar_etapa(fechas):
    """Nombre de la etapa de politica monetaria (ETAPAS_POLITICA) a la
    que pertenece cada fecha."""
    etapa = pd.Series(pd.NA, index=fechas.index, dtype="object")
    for nombre, inicio, fin in ETAPAS_POLITICA:
        etapa[(fechas >= inicio) & (fechas <= fin)] = nombre
    return etapa


def figura_boxplot_desvio_por_etapa(df, ruta_salida):
    etapas = asignar_etapa(df[COL_FECHA])
    nombres = [nombre for nombre, _, _ in ETAPAS_POLITICA]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.boxplot([df.loc[etapas == n, COL_DESVIO].values for n in nombres], tick_labels=nombres,
               flierprops={"marker": "o", "markersize": 3, "alpha": 0.5})
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.tick_params(axis="x", labelsize=8)
    ax.set_ylabel("Desvio (pp)")
    ax.set_title("Desvio de la interbancaria por etapa de la politica monetaria")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_dispersion_volatilidad_desvio(df, ruta_salida):
    """Un punto por mes: volatilidad de la interbancaria (desviacion
    estandar de su variacion diaria en el mes) vs. desvio absoluto medio
    del mes. El color indica la etapa de politica monetaria."""
    mensual = pd.DataFrame({
        "mes": df[COL_FECHA].dt.to_period("M"),
        "etapa": asignar_etapa(df[COL_FECHA]),
        "variacion": variacion_diaria_interbancaria(df),
        "desvio_abs": df[COL_DESVIO].abs(),
    }).groupby("mes").agg(etapa=("etapa", "first"), volatilidad=("variacion", "std"),
                          desvio_abs=("desvio_abs", "mean"))

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for i, (nombre, _, _) in enumerate(ETAPAS_POLITICA):
        grupo = mensual[mensual["etapa"] == nombre]
        ax.scatter(grupo["volatilidad"], grupo["desvio_abs"], s=22, alpha=0.8,
                   color=f"C{i}", label=nombre.replace("\n", " "))
    ax.set_xlabel("Volatilidad mensual: desv. estandar de la variacion diaria (pp)")
    ax.set_ylabel("Desvio absoluto medio del mes (pp)")
    ax.set_title("Volatilidad de la interbancaria vs. desvio respecto de la referencia (por mes)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_ecdf_desvio(df, ruta_salida):
    """Distribucion acumulada: para cada valor x, el % de dias con
    desvio menor o igual a x. El salto vertical en cero son los dias
    sin desvio."""
    ordenado = np.sort(df[COL_DESVIO].to_numpy())
    acumulado = np.arange(1, len(ordenado) + 1) / len(ordenado) * 100
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.step(ordenado, acumulado, where="post", color="C0", linewidth=1.4)
    ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_ylim(0, 100)
    ax.set_xlabel("Desvio interbancaria - referencia (pp)")
    ax.set_ylabel("% acumulado de dias")
    ax.set_title("Distribucion acumulada del desvio diario (2015-2025)")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def tabla_desvio_por_etapa(df):
    """Los mismos estadisticos de tabla_desvio_por_anio, agrupados por
    las etapas de politica monetaria (ETAPAS_POLITICA)."""
    etapas = asignar_etapa(df[COL_FECHA])
    return pd.DataFrame([
        {"etapa": nombre.replace("\n", " "), "fecha_inicio": inicio, "fecha_fin": fin,
         **resumir_desvio(df.loc[etapas == nombre, COL_DESVIO])}
        for nombre, inicio, fin in ETAPAS_POLITICA
    ])


def seleccionar_top10_desvios(df):
    """Los 10 dias con mayor desvio en valor absoluto, del mayor al menor.
    'dato_imputado' = True si la interbancaria o la referencia de ese dia
    fue imputada en 03_limpieza_datos.py (no es un dato original del BCRP)."""
    top = df.loc[df[COL_DESVIO].abs().nlargest(10).index]
    return top.assign(dato_imputado=top[COLUMNAS_IMPUTACION_DESVIO].notna().any(axis=1))


def tabla_top10_desvios(df):
    top = seleccionar_top10_desvios(df)
    return pd.DataFrame({
        "puesto": range(1, len(top) + 1),
        "fecha": top[COL_FECHA].dt.strftime("%Y-%m-%d").to_numpy(),
        "tasa_interbancaria": top[COL_ENDOGENA].to_numpy(),
        "tasa_referencia": top[COL_EXO1_REFERENCIA].to_numpy(),
        "desvio_pp": top[COL_DESVIO].to_numpy(),
        "dato_imputado": top["dato_imputado"].to_numpy(),
        "metodo_imputacion_interbancaria": top[COLUMNAS_IMPUTACION_DESVIO[0]].fillna("").to_numpy(),
        "metodo_imputacion_referencia": top[COLUMNAS_IMPUTACION_DESVIO[1]].fillna("").to_numpy(),
    })


def figura_top10_desvios(df, ruta_salida):
    """Los 10 dias con mayor desvio en valor absoluto (el mayor arriba).
    Naranja = la interbancaria quedo por encima de la referencia, azul =
    por debajo. Se marca con * si el dia tiene un dato imputado."""
    top = seleccionar_top10_desvios(df).iloc[::-1]
    imputado = top["dato_imputado"]
    etiquetas = [f"{f:%d/%m/%Y}{' *' if imp else ''}"
                 for f, imp in zip(top[COL_FECHA], imputado)]
    colores = ["C1" if d > 0 else "C0" for d in top[COL_DESVIO]]

    fig, ax = plt.subplots(figsize=(9, 5))
    barras = ax.barh(etiquetas, top[COL_DESVIO], color=colores, height=0.7)
    ax.bar_label(barras, labels=[f"{d:+.2f}" for d in top[COL_DESVIO]], padding=3, fontsize=8)
    ax.axvline(0, color="black", linewidth=0.8)
    limite = top[COL_DESVIO].abs().max() * 1.2
    ax.set_xlim(-limite, limite)
    ax.set_xlabel("Desvio interbancaria - referencia (pp)")
    ax.set_title("Los 10 dias con mayor desvio respecto de la referencia")
    if imputado.any():
        ax.text(0.01, -0.13, "* dia con la interbancaria o la referencia imputada",
                transform=ax.transAxes, fontsize=8)
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 7) REGRESION (series de tiempo, errores Newey-West / HAC)
# ---------------------------------------------------------------------------
def preparar_variables_regresion(df):
    """Aplica logaritmo natural SOLO en memoria, solo para la
    estimacion -- no se guarda de vuelta en datos_procesados. Las 2
    variables en millones de soles cambian de escala (log); las tasas
    se quedan en nivel (%)."""
    df_modelo = df.copy()
    df_modelo["ln_depositos"] = np.log(df_modelo[COL_EXO3_DEPOSITOS])
    df_modelo["ln_ctacte_L1"] = np.log(df_modelo[COL_EXO4_CTACTE_L1])
    return df_modelo


def tabla_datos_analisis(df_modelo):
    """Base de datos EXACTA que entra a la regresion: fecha, endogena y
    las 4 exogenas tal como se estiman (tasas en nivel, liquidez en ln,
    cuentas corrientes rezagada). Se guarda antes del analisis para que
    cualquiera pueda reproducir la estimacion desde este archivo."""
    return df_modelo[[
        COL_FECHA, COL_ENDOGENA, COL_EXO1_REFERENCIA, COL_EXO2_CDBCRP,
        "ln_depositos", "ln_ctacte_L1",
    ]]


def calcular_maxlags_newey_west(n_obs):
    """Regla practica de Newey-West para elegir el numero de rezagos en
    los errores HAC: floor(4*(T/100)^(2/9)). Se calcula, no se fija a
    mano, para que quede reproducible si cambia el tamano de muestra."""
    return int(np.floor(4 * (n_obs / 100) ** (2 / 9)))


def correr_regresion(df_modelo):
    y = df_modelo[COL_ENDOGENA]
    X = df_modelo[[COL_EXO1_REFERENCIA, COL_EXO2_CDBCRP, "ln_depositos", "ln_ctacte_L1"]]
    X = sm.add_constant(X)

    maxlags = calcular_maxlags_newey_west(len(df_modelo))
    modelo = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})

    logging.info("Regresion OLS con errores Newey-West (HAC), maxlags=%s", maxlags)
    logging.info("\n%s", modelo.summary())

    return modelo, maxlags


def tabla_resultados_regresion(modelo):
    tabla = pd.DataFrame({
        "coeficiente": modelo.params,
        "error_estandar_HAC": modelo.bse,
        "t_stat": modelo.tvalues,
        "p_valor": modelo.pvalues,
    })
    tabla.insert(0, "variable", tabla.index)
    tabla = tabla.reset_index(drop=True)
    tabla["r2"] = modelo.rsquared
    tabla["r2_ajustado"] = modelo.rsquared_adj
    tabla["n_obs"] = int(modelo.nobs)
    return tabla


def tabla_diagnosticos_regresion(modelo, maxlags):
    """Indicadores de ajuste y de diagnostico de los residuos (los mismos
    que muestra modelo.summary()), en formato largo para citarlos en la
    seccion de limitaciones."""
    jb, jb_p_valor, asimetria, curtosis = jarque_bera(modelo.resid)
    filas = [
        ("r2", modelo.rsquared, "Proporcion de la varianza de la interbancaria explicada por el modelo"),
        ("r2_ajustado", modelo.rsquared_adj, "R2 corregido por el numero de regresores"),
        ("n_obs", int(modelo.nobs), "Dias usados en la estimacion"),
        ("durbin_watson", durbin_watson(modelo.resid),
         "Cercano a 2 = sin autocorrelacion; muy por debajo de 2 = autocorrelacion positiva de los residuos"),
        ("jarque_bera", jb, "Prueba de normalidad de los residuos (H0: residuos normales)"),
        ("jarque_bera_p_valor", jb_p_valor, "p-valor < 0.05 = se rechaza la normalidad"),
        ("asimetria", asimetria, "0 en una normal; > 0 = cola derecha mas larga"),
        ("curtosis", curtosis, "3 en una normal; > 3 = colas mas gruesas (mas dias extremos)"),
        ("numero_condicion", modelo.condition_number,
         "Multicolinealidad: valores altos (> 30) indican regresores muy relacionados o de escala distinta"),
        ("maxlags_hac", maxlags, "Rezagos de los errores Newey-West (HAC) usados en la inferencia"),
    ]
    return pd.DataFrame(filas, columns=["indicador", "valor", "interpretacion"])


def prueba_traspaso_completo(modelo):
    """Prueba H0: b1 = 1 (traspaso completo) con los mismos errores HAC
    del modelo. Si no se rechaza, la interbancaria sigue 1 a 1 a la tasa
    de politica y el desvio no depende del nivel de esa tasa; si se
    rechaza, el desvio cambia sistematicamente con el nivel de la tasa
    de politica (en b1 - 1 pp por cada punto de la referencia)."""
    prueba = modelo.t_test(f"{COL_EXO1_REFERENCIA} = 1")
    p_valor = np.asarray(prueba.pvalue).item()
    return pd.DataFrame([{
        "hipotesis_nula": f"b1 ({COL_EXO1_REFERENCIA}) = 1",
        "b1_estimado": modelo.params[COL_EXO1_REFERENCIA],
        "error_estandar_HAC": modelo.bse[COL_EXO1_REFERENCIA],
        "z_stat": np.asarray(prueba.tvalue).item(),
        "p_valor": p_valor,
        "rechaza_h0_al_5pct": p_valor < 0.05,
    }])


# --- Diagnostico de los residuos del modelo ---
def figura_residuos_vs_ajustados(modelo, df_modelo, ruta_salida):
    """Si el modelo esta bien especificado, los residuos se reparten
    alrededor de cero sin forma ni embudo a lo largo de los ajustados."""
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(modelo.fittedvalues, modelo.resid, s=8, alpha=0.35, color="C0")
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Valores ajustados de la interbancaria (%)")
    ax.set_ylabel("Residuo (pp)")
    ax.set_title("Residuos vs. valores ajustados")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_residuos_tiempo(modelo, df_modelo, ruta_salida):
    """Residuos en el orden del tiempo: rachas largas del mismo signo
    indican autocorrelacion (por eso se usan errores Newey-West / HAC)."""
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(df_modelo[COL_FECHA], modelo.resid, color="C0", linewidth=0.7)
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_ylabel("Residuo (pp)")
    ax.set_title("Residuos del modelo en el tiempo (2015-2025)")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_qq_residuos(modelo, df_modelo, ruta_salida):
    """Cuantiles de los residuos contra los de una normal: si fueran
    normales, los puntos seguirian la linea recta."""
    fig, ax = plt.subplots(figsize=(6.5, 6))
    sm.qqplot(modelo.resid, line="q", ax=ax, markersize=3, alpha=0.5)
    ax.set_xlabel("Cuantiles teoricos (normal)")
    ax.set_ylabel("Cuantiles de los residuos (pp)")
    ax.set_title("Grafico Q-Q de los residuos")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_histograma_residuos(modelo, df_modelo, ruta_salida):
    """Histograma de los residuos con la curva normal de la misma media
    y desviacion estandar: si el pico es mas alto y las colas mas largas
    que la curva, los residuos no son normales (curtosis alta)."""
    residuos = modelo.resid
    media, desv = residuos.mean(), residuos.std()
    x = np.linspace(residuos.min(), residuos.max(), 400)
    curva_normal = np.exp(-((x - media) ** 2) / (2 * desv ** 2)) / (desv * np.sqrt(2 * np.pi))

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.hist(residuos, bins=120, density=True, color="C0", edgecolor="white", linewidth=0.3,
            label="Residuos")
    ax.plot(x, curva_normal, color="black", linewidth=1.2, linestyle="--",
            label="Normal con la misma media y desv. estandar")
    ax.set_xlabel("Residuo (pp)")
    ax.set_ylabel("Densidad")
    ax.set_title("Distribucion de los residuos del modelo")
    ax.legend()
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def figura_autocorrelacion_residuos(modelo, df_modelo, ruta_salida):
    """Funcion de autocorrelacion (ACF) de los residuos hasta 40 rezagos.
    Barras fuera de la banda sombreada = autocorrelacion significativa,
    lo que justifica los errores Newey-West (HAC)."""
    fig, ax = plt.subplots(figsize=(10, 4.5))
    sm.graphics.tsa.plot_acf(modelo.resid, lags=40, ax=ax, title=None)
    ax.set_xlabel("Rezago (dias habiles)")
    ax.set_ylabel("Autocorrelacion")
    ax.set_title("Autocorrelacion de los residuos del modelo")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=150)
    plt.close(fig)


def generar_figura(funcion, nombre, descripcion, *datos):
    """Arma la ruta /salidas/<nombre>_<codigo>.png, dibuja la figura y
    deja constancia en el log."""
    ruta = os.path.join(CARPETA_SALIDAS, f"{nombre}_{CODIGO_MATRICULA}.png")
    funcion(*datos, ruta)
    logging.info("Figura %s guardada en: %s", descripcion, ruta)


# ---------------------------------------------------------------------------
# 8) PROGRAMA PRINCIPAL
# ---------------------------------------------------------------------------
def main():
    configurar_logging()
    logging.info("=== Inicio de analisis (Tema 22) ===")
    os.makedirs(CARPETA_SALIDAS, exist_ok=True)

    df = cargar_datos_procesados()
    logging.info("Filas cargadas desde datos_procesados: %s", len(df))

    # --- Datos de analisis (lo que entra al modelo), antes de todo ---
    df_modelo = preparar_variables_regresion(df)
    ruta_datos_analisis = os.path.join(CARPETA_SALIDAS, f"datos_analisis_{CODIGO_MATRICULA}.csv")
    tabla_datos_analisis(df_modelo).to_csv(ruta_datos_analisis, index=False, encoding="utf-8")
    logging.info("Datos de analisis guardados en: %s", ruta_datos_analisis)

    # --- Descriptivos ---
    tabla_desc = tabla_descriptivos(df)
    ruta_desc = os.path.join(CARPETA_SALIDAS, f"tabla_descriptivos_{CODIGO_MATRICULA}.csv")
    tabla_desc.to_csv(ruta_desc, index=False, encoding="utf-8")
    logging.info("Tabla de descriptivos guardada en: %s", ruta_desc)

    # --- Correlacion (sobre las variables tal como entran al modelo) ---
    columnas_modelo_nivel = [
        COL_ENDOGENA, COL_EXO1_REFERENCIA, COL_EXO2_CDBCRP,
        COL_EXO3_DEPOSITOS, COL_EXO4_CTACTE_L1,
    ]
    tabla_corr = tabla_correlacion(df, columnas_modelo_nivel)
    ruta_corr = os.path.join(CARPETA_SALIDAS, f"tabla_correlacion_{CODIGO_MATRICULA}.csv")
    tabla_corr.to_csv(ruta_corr, encoding="utf-8")
    logging.info("Tabla de correlacion guardada en: %s", ruta_corr)

    ruta_fig_corr = os.path.join(CARPETA_SALIDAS, f"fig_correlacion_{CODIGO_MATRICULA}.png")
    figura_correlacion(tabla_corr, ruta_fig_corr)
    logging.info("Figura de correlacion guardada en: %s", ruta_fig_corr)

    # --- Figuras de series de tiempo ---
    ruta_fig1 = os.path.join(CARPETA_SALIDAS, f"fig_interbancaria_vs_referencia_{CODIGO_MATRICULA}.png")
    figura_interbancaria_vs_referencia(df, ruta_fig1)
    logging.info("Figura interbancaria vs. referencia guardada en: %s", ruta_fig1)

    ruta_fig2 = os.path.join(CARPETA_SALIDAS, f"fig_variables_liquidez_{CODIGO_MATRICULA}.png")
    figura_variables_liquidez(df, ruta_fig2)
    logging.info("Figura de variables de liquidez guardada en: %s", ruta_fig2)

    # --- Desvio respecto de la tasa de politica ---
    df = calcular_desvio(df)
    tabla_desvio = tabla_desvio_por_anio(df)
    ruta_desvio = os.path.join(CARPETA_SALIDAS, f"tabla_desvio_por_anio_{CODIGO_MATRICULA}.csv")
    tabla_desvio.to_csv(ruta_desvio, index=False, encoding="utf-8")
    logging.info("Tabla de desvio por anio guardada en: %s", ruta_desvio)

    for tabla, nombre, descripcion in [
        (tabla_desvio_por_etapa(df), "tabla_desvio_por_etapa", "desvio por etapa"),
        (tabla_top10_desvios(df), "tabla_top10_desvios", "10 mayores desvios"),
    ]:
        ruta = os.path.join(CARPETA_SALIDAS, f"{nombre}_{CODIGO_MATRICULA}.csv")
        tabla.to_csv(ruta, index=False, encoding="utf-8")
        logging.info("Tabla de %s guardada en: %s", descripcion, ruta)

    total = tabla_desvio.iloc[-1]
    logging.info("Desvio interbancaria - referencia (%s): medio = %.4f pp | absoluto "
                 "medio = %.4f pp | dias sobre / igual / bajo la referencia = "
                 "%.1f%% / %.1f%% / %.1f%%", total["periodo"], total["desvio_medio_pp"],
                 total["desvio_absoluto_medio_pp"], total["pct_dias_sobre_referencia"],
                 total["pct_dias_igual_referencia"], total["pct_dias_bajo_referencia"])

    ruta_fig_desvio = os.path.join(CARPETA_SALIDAS, f"fig_desvio_interbancaria_{CODIGO_MATRICULA}.png")
    figura_desvio(df, ruta_fig_desvio)
    logging.info("Figura del desvio guardada en: %s", ruta_fig_desvio)

    # --- Figuras complementarias: tasas, liquidez y desvio ---
    for funcion, nombre, descripcion in [
        (figura_cdbcrp_vs_referencia, "fig_cdbcrp_vs_referencia", "CD BCRP vs. referencia"),
        (figura_histograma_desvio, "fig_histograma_desvio", "histograma del desvio"),
        (figura_boxplot_desvio_anual, "fig_boxplot_desvio_anual", "boxplot del desvio por anio"),
        (figura_scatter_interbancaria_referencia, "fig_scatter_interbancaria_referencia",
         "dispersion interbancaria vs. referencia"),
        (figura_distribucion_tasas, "fig_distribucion_tasas", "distribucion de las tasas"),
        (figura_depositos_publicos, "fig_depositos_publicos", "depositos publicos"),
        (figura_cuenta_corriente_detalle, f"fig_cuenta_corriente_detalle{ANIO_DETALLE_CTACTE}",
         f"cuenta corriente {ANIO_DETALLE_CTACTE}"),
        (figura_volatilidad_movil, "fig_volatilidad_movil", "volatilidad movil"),
        (figura_heatmap_desvio_mensual, "fig_heatmap_desvio_mensual",
         "mapa de calor del desvio mensual"),
        (figura_ctacte_zoom_trimestre, "fig_ctacte_zoom_trimestre", "zoom trimestral cta. cte."),
        (figura_depositos_vs_ctacte, "fig_depositos_vs_ctacte_scatter",
         "depositos vs. cuentas corrientes"),
        (figura_correlacion_movil, "fig_correlacion_movil_90d", "correlacion movil"),
        (figura_variacion_diaria_interbancaria, "fig_variacion_diaria_interbancaria",
         "variacion diaria de la interbancaria"),
        (figura_histograma_variacion_diaria, "fig_histograma_variacion_diaria",
         "histograma de la variacion diaria"),
        (figura_promedio_movil_ctacte, "fig_promedio_movil_ctacte_30d",
         "promedio movil cta. cte."),
        (figura_promedio_movil_depositos, "fig_promedio_movil_depositos_90d",
         "promedio movil depositos"),
        (figura_boxplot_desvio_por_etapa, "fig_boxplot_desvio_por_etapa",
         "boxplot del desvio por etapa"),
        (figura_dispersion_volatilidad_desvio, "fig_dispersion_volatilidad_desvio",
         "volatilidad vs. desvio absoluto"),
        (figura_ecdf_desvio, "fig_ecdf_desvio", "distribucion acumulada del desvio"),
        (figura_cdbcrp_suavizada, "fig_evolucion_cdbcrp_suavizada", "CD BCRP suavizada"),
        (figura_top10_desvios, "fig_top10_desvios", "10 mayores desvios"),
    ]:
        generar_figura(funcion, nombre, descripcion, df)
    for funcion, nombre, descripcion in [
        (figura_estado_diario_por_anio, "fig_estado_diario_por_anio", "estado diario por anio"),
        (figura_desvio_absoluto_por_anio, "fig_desvio_absoluto_por_anio",
         "desvio absoluto por anio"),
    ]:
        generar_figura(funcion, nombre, descripcion, tabla_desvio)

    # --- Regresion ---
    modelo, maxlags = correr_regresion(df_modelo)

    tabla_reg = tabla_resultados_regresion(modelo)
    ruta_reg = os.path.join(CARPETA_SALIDAS, f"tabla_regresion_{CODIGO_MATRICULA}.csv")
    tabla_reg.to_csv(ruta_reg, index=False, encoding="utf-8")
    logging.info("Tabla de resultados de la regresion guardada en: %s", ruta_reg)

    logging.info("R2 = %.4f | R2 ajustado = %.4f | N = %s | maxlags HAC = %s",
                 modelo.rsquared, modelo.rsquared_adj, int(modelo.nobs), maxlags)

    tabla_diag = tabla_diagnosticos_regresion(modelo, maxlags)
    ruta_diag = os.path.join(CARPETA_SALIDAS, f"tabla_diagnosticos_regresion_{CODIGO_MATRICULA}.csv")
    tabla_diag.to_csv(ruta_diag, index=False, encoding="utf-8")
    logging.info("Tabla de diagnosticos de la regresion guardada en: %s", ruta_diag)

    # --- Prueba de traspaso completo (H0: b1 = 1) ---
    tabla_traspaso = prueba_traspaso_completo(modelo)
    ruta_traspaso = os.path.join(CARPETA_SALIDAS, f"tabla_prueba_traspaso_{CODIGO_MATRICULA}.csv")
    tabla_traspaso.to_csv(ruta_traspaso, index=False, encoding="utf-8")
    fila = tabla_traspaso.iloc[0]
    logging.info("Prueba de traspaso completo H0: b1 = 1 -> b1 = %.4f | z = %.3f | "
                 "p-valor = %.4f | rechaza H0 al 5%%: %s", fila["b1_estimado"],
                 fila["z_stat"], fila["p_valor"], "si" if fila["rechaza_h0_al_5pct"] else "no")
    logging.info("Tabla de la prueba de traspaso guardada en: %s", ruta_traspaso)

    # --- Diagnostico de residuos ---
    for funcion, nombre, descripcion in [
        (figura_residuos_vs_ajustados, "fig_residuos_vs_ajustados", "residuos vs. ajustados"),
        (figura_residuos_tiempo, "fig_residuos_tiempo", "residuos en el tiempo"),
        (figura_qq_residuos, "fig_qq_residuos", "Q-Q de los residuos"),
        (figura_histograma_residuos, "fig_histograma_residuos", "histograma de los residuos"),
        (figura_autocorrelacion_residuos, "fig_autocorrelacion_residuos",
         "autocorrelacion de los residuos"),
    ]:
        generar_figura(funcion, nombre, descripcion, modelo, df_modelo)
    logging.info("=== Fin de analisis (Tema 22) ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Deja constancia del error en log_ejecucion.txt antes de detenerse
        logging.exception("La ejecucion termino con error")
        raise
