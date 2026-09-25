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
        /salidas/fig_interbancaria_vs_referencia_<codigo>.png
        /salidas/fig_variables_liquidez_<codigo>.png
        /salidas/fig_correlacion_<codigo>.png
        /salidas/fig_desvio_interbancaria_<codigo>.png

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
# 3 exogenas en nivel + exogena 4 (original y rezagada). El resto de
# columnas del datos_procesados (metodo_imputacion, outlier) quedan
# fuera de este script: son para trazabilidad, no para el modelo.
COL_FECHA = "fecha"
COL_ENDOGENA = "tasa_interbancaria_on_end"
COL_EXO1_REFERENCIA = "tasa_referencia_exo"
COL_EXO2_CDBCRP = "tasa_cdbcrp_saldo_exo"
COL_EXO3_DEPOSITOS = "depositos_sector_publico_saldo_exo"
COL_EXO4_CTACTE_L1 = "cuentas_corrientes_bancos_bcrp_saldo_exo_L1"

# Desvio de la interbancaria respecto de la tasa de politica (se calcula
# en memoria en este script; no esta en datos_procesados)
COL_DESVIO = "desvio_interbancaria_referencia_pp"

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
# 3) CARGA (solo las 7 columnas necesarias)
# ---------------------------------------------------------------------------
def cargar_datos_procesados():
    """Lee datos_procesados y se queda SOLO con fecha + las 5 variables
    + la version rezagada de la exogena 4 -- las columnas auxiliares
    (metodo_imputacion, outlier) no se usan aqui, son para trazabilidad
    en la Carpeta N.3, no para el analisis."""
    df = pd.read_csv(RUTA_PROCESADO, usecols=COLUMNAS_ANALISIS)
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

    total = tabla_desvio.iloc[-1]
    logging.info("Desvio interbancaria - referencia (%s): medio = %.4f pp | absoluto "
                 "medio = %.4f pp | dias sobre / igual / bajo la referencia = "
                 "%.1f%% / %.1f%% / %.1f%%", total["periodo"], total["desvio_medio_pp"],
                 total["desvio_absoluto_medio_pp"], total["pct_dias_sobre_referencia"],
                 total["pct_dias_igual_referencia"], total["pct_dias_bajo_referencia"])

    ruta_fig_desvio = os.path.join(CARPETA_SALIDAS, f"fig_desvio_interbancaria_{CODIGO_MATRICULA}.png")
    figura_desvio(df, ruta_fig_desvio)
    logging.info("Figura del desvio guardada en: %s", ruta_fig_desvio)

    # --- Regresion ---
    modelo, maxlags = correr_regresion(df_modelo)

    tabla_reg = tabla_resultados_regresion(modelo)
    ruta_reg = os.path.join(CARPETA_SALIDAS, f"tabla_regresion_{CODIGO_MATRICULA}.csv")
    tabla_reg.to_csv(ruta_reg, index=False, encoding="utf-8")
    logging.info("Tabla de resultados de la regresion guardada en: %s", ruta_reg)

    logging.info("R2 = %.4f | R2 ajustado = %.4f | N = %s | maxlags HAC = %s",
                 modelo.rsquared, modelo.rsquared_adj, int(modelo.nobs), maxlags)

    # --- Prueba de traspaso completo (H0: b1 = 1) ---
    tabla_traspaso = prueba_traspaso_completo(modelo)
    ruta_traspaso = os.path.join(CARPETA_SALIDAS, f"tabla_prueba_traspaso_{CODIGO_MATRICULA}.csv")
    tabla_traspaso.to_csv(ruta_traspaso, index=False, encoding="utf-8")
    fila = tabla_traspaso.iloc[0]
    logging.info("Prueba de traspaso completo H0: b1 = 1 -> b1 = %.4f | z = %.3f | "
                 "p-valor = %.4f | rechaza H0 al 5%%: %s", fila["b1_estimado"],
                 fila["z_stat"], fila["p_valor"], "si" if fila["rechaza_h0_al_5pct"] else "no")
    logging.info("Tabla de la prueba de traspaso guardada en: %s", ruta_traspaso)
    logging.info("=== Fin de analisis (Tema 22) ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Deja constancia del error en log_ejecucion.txt antes de detenerse
        logging.exception("La ejecucion termino con error")
        raise
