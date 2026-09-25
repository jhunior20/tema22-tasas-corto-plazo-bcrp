# NOMBRES Y APELLIDOS COMPLETOS: Isai Jhunior Laymito Tacza
# CODIGO DE MATRICULA: 2024200505K
# TEMA: N.o 22 - Tasas de corto plazo en el Peru: interbancaria, certificados
#       del BCRP y tasa de referencia
# FECHA DE EXTRACCION: 24/09/2026
"""
03_limpieza_datos.py

Depuracion, tipificacion, tratamiento de faltantes y outliers, union de
fuentes por la llave comun (fecha) y generacion de datos_procesados,
tal como exige el numeral 2.4.2 de la consigna.

Input : /datos_crudos/datos_crudos_api_<codigo>.csv   (de 01_extraccion_api.py)
        /datos_crudos/datos_crudos_scraping_<codigo>.csv (de 02, SI existe)
Output: /datos_procesados/datos_procesados_<codigo>.csv

Modelo del tema 22:
    ENDOGENA : tasa_interbancaria_on_end
    EXOGENAS : tasa_referencia_exo, tasa_cdbcrp_saldo_exo,
               depositos_sector_publico_saldo_exo,
               cuentas_corrientes_bancos_bcrp_saldo_exo

La exogena 4 (cuentas corrientes de bancos en el BCRP) se usa REZAGADA
un periodo, para mitigar simultaneidad. Ese rezago se aplica AQUI (no
en 01), generando una columna nueva "..._L1" y conservando la version
sin rezagar para que quede trazable de donde sale cada una.

Tratamiento de faltantes autorizado por el docente (metodos
estadisticos, no solo dejar NaN): cada variable usa el metodo que mejor
refleja su naturaleza economica -- ver la funcion tratar_faltantes()
mas abajo.
"""

import os
import sys
import hashlib
import logging

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 1) RUTAS Y PARAMETROS
# ---------------------------------------------------------------------------
CODIGO_MATRICULA = "2024200505K"

try:
    _DIRECTORIO_SCRIPT = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _DIRECTORIO_SCRIPT = os.getcwd()

CARPETA_CRUDOS = os.path.join(_DIRECTORIO_SCRIPT, "..", "datos_crudos")
CARPETA_PROCESADOS = os.path.join(_DIRECTORIO_SCRIPT, "..", "datos_procesados")
ARCHIVO_LOG = os.path.join(_DIRECTORIO_SCRIPT, "..", "log_ejecucion.txt")

RUTA_CRUDO_API = os.path.join(CARPETA_CRUDOS, f"datos_crudos_api_{CODIGO_MATRICULA}.csv")
RUTA_CRUDO_SCRAPING = os.path.join(CARPETA_CRUDOS, f"datos_crudos_scraping_{CODIGO_MATRICULA}.csv")
RUTA_PROCESADO = os.path.join(CARPETA_PROCESADOS, f"datos_procesados_{CODIGO_MATRICULA}.csv")

# Columna a la que se le aplica el rezago (exogena 4 del modelo: cuentas
# corrientes de bancos en el BCRP, saldo, millones S/)
COLUMNA_EXOGENA_REZAGO = "cuentas_corrientes_bancos_bcrp_saldo_exo"

# Listas EXPLICITAS de columnas por tipo de tratamiento. Se usan listas
# explicitas y NO se detecta el tipo buscando palabras como "saldo" en
# el nombre de la columna, porque "tasa_cdbcrp_saldo_exo" es una TASA
# (%) aunque su nombre contenga la palabra "saldo" -- detectar por
# palabra clave habria clasificado mal esta columna.
COLUMNAS_TASA_INTERPOLACION = [
    "tasa_interbancaria_on_end",
    "tasa_referencia_exo",
    "tasa_cdbcrp_saldo_exo",
]
COLUMNAS_SALDO_FORWARDFILL = [
    "depositos_sector_publico_saldo_exo",
    "cuentas_corrientes_bancos_bcrp_saldo_exo",
]
COLUMNAS_VARIABLES = COLUMNAS_TASA_INTERPOLACION + COLUMNAS_SALDO_FORWARDFILL

# Mapeo explicito de mes en texto (español, como lo entrega la API con
# IDIOMA="esp") a numero. Se usa un mapeo manual, en vez de %b de
# strptime, porque %b depende del idioma configurado en el sistema
# operativo, y ademas el BCRP usa "Set" (no "Sep") para setiembre,
# siguiendo la convencion peruana, que no siempre coincide con la
# abreviatura que usaria Python por defecto.
MESES_ABREVIADOS_A_NUMERO = {
    "Ene": "01", "Feb": "02", "Mar": "03", "Abr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Ago": "08",
    "Set": "09", "Sep": "09",  # el BCRP usa "Set"; se acepta "Sep" tambien por si acaso
    "Oct": "10", "Nov": "11", "Dic": "12",
}


# ---------------------------------------------------------------------------
# 2) LOG
# ---------------------------------------------------------------------------
def configurar_logging():
    os.makedirs(CARPETA_PROCESADOS, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(ARCHIVO_LOG, mode="a", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ---------------------------------------------------------------------------
# 3) CARGA Y TIPIFICACION
# ---------------------------------------------------------------------------
def parsear_fecha_bcrp(serie_fechas):
    """Convierte la columna 'fecha_bcrp' (texto tal como la entrega la
    API, formato real confirmado: 'DD.Mes.YY', ej. '05.Ene.15') a
    datetime real, usando el mapeo explicito de mes (no %b) para que
    no dependa del idioma del sistema operativo."""

    def convertir_una_fecha(texto_fecha):
        partes = str(texto_fecha).split(".")
        if len(partes) != 3:
            return None
        dia, mes_abrev, anio_corto = partes
        mes_numero = MESES_ABREVIADOS_A_NUMERO.get(mes_abrev)
        if mes_numero is None:
            return None
        anio_completo = f"20{anio_corto}"  # BCRPData: para 2015-2025 basta con "20"
        return f"{anio_completo}-{mes_numero}-{dia.zfill(2)}"

    fechas_iso = serie_fechas.apply(convertir_una_fecha)
    fechas = pd.to_datetime(fechas_iso, format="%Y-%m-%d", errors="coerce")

    if fechas.isna().any():
        no_parseadas = serie_fechas[fechas.isna()].unique()[:5]
        logging.warning(
            "Algunas fechas no se pudieron convertir. Ejemplos: %s. "
            "Revisa si el formato real cambio.", list(no_parseadas)
        )

    return fechas


def cargar_crudo_api():
    """Lee el CSV crudo de la API tal cual, sin editarlo, y solo aqui
    (en memoria, para procesar) convierte tipos: fecha a datetime y las
    series a numerico, marcando 'n.d.' como NaN explicito."""
    df = pd.read_csv(RUTA_CRUDO_API, dtype=str)

    df["fecha"] = parsear_fecha_bcrp(df["fecha_bcrp"])
    df = df.drop(columns=["fecha_bcrp"])

    for col in COLUMNAS_VARIABLES:
        # "n.d." (no disponible) -> NaN explicito, tal como lo marca el
        # propio BCRP. No se inventa ningun valor todavia.
        df[col] = df[col].replace("n.d.", np.nan)
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Orden exigido: fecha, endogena, exogenas
    df = df[["fecha"] + COLUMNAS_VARIABLES]
    df = df.sort_values("fecha").reset_index(drop=True)
    return df


def cargar_crudo_scraping_si_existe():
    """Si 02_scraping_web.py logro extraer datos, los integra. Si el
    archivo no existe, sigue solo con la API sin fallar: en Unidad I la
    segunda via es opcional (en este tema, se decidio no hacer la
    Via 2, asi que este archivo normalmente no existira)."""
    if not os.path.exists(RUTA_CRUDO_SCRAPING):
        logging.info(
            "No se encontro %s. Se continua solo con la Via 1 (API); "
            "esto es valido para Unidad I.", RUTA_CRUDO_SCRAPING
        )
        return None

    df_scraping = pd.read_csv(RUTA_CRUDO_SCRAPING)
    logging.info("Datos de scraping encontrados: %s filas.", len(df_scraping))
    return df_scraping


# ---------------------------------------------------------------------------
# 4) TRATAMIENTO DE FALTANTES (autorizado por el docente) Y OUTLIERS
# ---------------------------------------------------------------------------
def tratar_faltantes(df):
    """Rellena los faltantes con el metodo estadistico que corresponde
    a la naturaleza de cada variable (autorizado por el docente):

    - Tasas (interbancaria, referencia, CD BCRP): INTERPOLACION LINEAL.
      En la interbancaria y la de CD BCRP, el valor intermedio entre
      el dato anterior y el siguiente es una buena aproximacion
      estadistica del dia faltante. La tasa de referencia, en cambio,
      cambia en saltos: si un cambio de tasa coincide con un dia sin
      dato, la interpolacion da un valor intermedio que el BCRP nunca
      fijo (limitacion documentada en incidencias_fuente.md). Se usa el
      mismo metodo en las tres tasas para mantener un criterio unico.
      Excepcion de borde: si el hueco esta al INICIO de toda la serie
      (no hay dato anterior con el cual interpolar), se usa
      backward-fill (copia el primer valor real hacia atras). Si el
      hueco esta al FINAL de toda la serie (no hay dato siguiente), se
      usa forward-fill como ultimo recurso simetrico.

    - Saldos (depositos sector publico, cuentas corrientes de bancos):
      FORWARD-FILL con limite de 5 dias. Son variables de STOCK: si el
      BCRP no reporta un dia, el saldo del dia anterior es la mejor
      aproximacion (el saldo no cambia sin una transaccion nueva).

    Cada columna genera una columna auxiliar "<col>_metodo_imputacion"
    (texto) que indica, celda por celda, que metodo se aplico -- o
    cadena vacia si el dato ya era real y no se toco. Esto deja 100%
    trazable que se hizo, para que se pueda distinguir un dato real de
    uno imputado en cualquier auditoria (numeral 2.4.6).
    """
    conteo_nan_antes = df[COLUMNAS_VARIABLES].isna().sum()
    logging.info("Conteo de NaN por variable (antes de tratar):\n%s", conteo_nan_antes.to_string())

    # --- Tasas: interpolacion lineal + bfill/ffill solo en los bordes ---
    for col in COLUMNAS_TASA_INTERPOLACION:
        col_metodo = f"{col}_metodo_imputacion"
        df[col_metodo] = ""

        faltaba_antes = df[col].isna()
        # limit_area="inside": solo huecos con dato real a ambos lados;
        # los bordes se tratan abajo con bfill/ffill y quedan marcados asi.
        df[col] = df[col].interpolate(method="linear", limit_area="inside")
        se_interpolo = faltaba_antes & df[col].notna()
        df.loc[se_interpolo, col_metodo] = "interpolacion_lineal"

        # Bordes: lo que siga en NaN esta al inicio o al final de toda
        # la serie (no se pudo interpolar por falta de un punto de
        # apoyo a ambos lados).
        faltaba_aun = df[col].isna()
        df[col] = df[col].bfill()
        se_relleno_bfill = faltaba_aun & df[col].notna()
        df.loc[se_relleno_bfill, col_metodo] = "bfill_borde_inicial"

        faltaba_aun2 = df[col].isna()
        df[col] = df[col].ffill()
        se_relleno_ffill = faltaba_aun2 & df[col].notna()
        df.loc[se_relleno_ffill, col_metodo] = "ffill_borde_final"

        n_interp = (df[col_metodo] == "interpolacion_lineal").sum()
        n_bfill = (df[col_metodo] == "bfill_borde_inicial").sum()
        n_ffill = (df[col_metodo] == "ffill_borde_final").sum()
        logging.info(
            "%s: %s interpolados, %s con bfill de borde inicial, %s con "
            "ffill de borde final.", col, n_interp, n_bfill, n_ffill
        )

    # --- Saldos: forward-fill con limite de 5 dias ---
    for col in COLUMNAS_SALDO_FORWARDFILL:
        col_metodo = f"{col}_metodo_imputacion"
        df[col_metodo] = ""

        faltaba_antes = df[col].isna()
        df[col] = df[col].ffill(limit=5)
        se_relleno = faltaba_antes & df[col].notna()
        df.loc[se_relleno, col_metodo] = "forward_fill_max5"

        # Borde inicial: antes del primer dato real no hay saldo previo
        # que arrastrar, asi que se copia el primer valor real hacia atras.
        faltaba_aun = df[col].isna()
        es_borde_inicial = faltaba_aun & (df.index < df[col].first_valid_index())
        df.loc[es_borde_inicial, col] = df[col].bfill()[es_borde_inicial]
        df.loc[es_borde_inicial, col_metodo] = "bfill_borde_inicial"

        n_relleno = se_relleno.sum()
        n_bfill = es_borde_inicial.sum()
        n_aun_faltante = df[col].isna().sum()
        logging.info(
            "%s: %s rellenados con forward-fill (max. 5 dias), %s con bfill "
            "de borde inicial; %s siguen en NaN (huecos de mas de 5 dias, "
            "dejados sin inventar).",
            col, n_relleno, n_bfill, n_aun_faltante,
        )

    return df


def marcar_outliers(df, n_desv_estandar=4):
    """Marca (no elimina ni corrige) valores atipicos por columna, sobre
    los datos YA rellenados, usando +/- N desviaciones estandar. Se deja
    como columna booleana "_outlier" para que la deteccion sea
    transparente y reproducible, sin alterar ningun valor real."""
    for col in COLUMNAS_VARIABLES:
        media = df[col].mean()
        desv = df[col].std()
        limite_inf = media - n_desv_estandar * desv
        limite_sup = media + n_desv_estandar * desv
        df[f"{col}_outlier"] = (df[col] < limite_inf) | (df[col] > limite_sup)

        n_outliers = df[f"{col}_outlier"].sum()
        if n_outliers > 0:
            logging.info(
                "%s: %s valores marcados como outlier (fuera de +/- %s "
                "desv. estandar). NO se eliminan, solo se marcan.",
                col, n_outliers, n_desv_estandar,
            )
    return df


# ---------------------------------------------------------------------------
# 5) REZAGO DE LA EXOGENA 4 (mitigar simultaneidad)
# ---------------------------------------------------------------------------
def aplicar_rezago(df, columna, periodos=1):
    """Crea una version rezagada de 'columna' (el valor de 'periodos'
    dias atras se asigna a la fecha actual, via .shift()). Esta es la
    variable que efectivamente entra al modelo como exogena 4, para no
    explicar la interbancaria de HOY con una decision de liquidez de
    HOY, que se toma casi simultaneamente."""
    nombre_col_rezago = f"{columna}_L{periodos}"
    col_metodo = f"{nombre_col_rezago}_metodo_imputacion"
    df[nombre_col_rezago] = df[columna].shift(periodos)

    # Las primeras 'periodos' filas quedan vacias por el propio shift (no
    # hay dia anterior al inicio de la muestra): bfill de borde inicial.
    df[col_metodo] = ""
    faltaba = df[nombre_col_rezago].isna()
    df[nombre_col_rezago] = df[nombre_col_rezago].bfill()
    df.loc[faltaba & df[nombre_col_rezago].notna(), col_metodo] = "bfill_borde_inicial"

    logging.info("Rezago aplicado: %s -> %s (shift de %s dia(s)); %s fila(s) "
                 "iniciales con bfill.", columna, nombre_col_rezago, periodos,
                 (df[col_metodo] == "bfill_borde_inicial").sum())
    return df, nombre_col_rezago


# ---------------------------------------------------------------------------
# 6) HASH DE VERIFICACION (numeral 2.4.2 y 2.4.5)
# ---------------------------------------------------------------------------
def calcular_sha256(ruta_archivo):
    sha256 = hashlib.sha256()
    with open(ruta_archivo, "rb") as f:
        for bloque in iter(lambda: f.read(8192), b""):
            sha256.update(bloque)
    return sha256.hexdigest()


# ---------------------------------------------------------------------------
# 7) PROGRAMA PRINCIPAL
# ---------------------------------------------------------------------------
def main():
    configurar_logging()
    logging.info("=== Inicio de limpieza de datos (Tema 22) ===")

    df = cargar_crudo_api()
    logging.info("Filas leidas del crudo API: %s", len(df))

    # Union con la Via 2 (scraping), solo si existe.
    df_scraping = cargar_crudo_scraping_si_existe()
    if df_scraping is not None and "fecha" in df_scraping.columns:
        df_scraping["fecha"] = pd.to_datetime(df_scraping["fecha"])
        df = df.merge(df_scraping, on="fecha", how="left")
        logging.info("Datos de scraping unidos por la llave comun 'fecha'.")

    df = tratar_faltantes(df)
    df = marcar_outliers(df)
    df, columna_rezagada = aplicar_rezago(df, COLUMNA_EXOGENA_REZAGO, periodos=1)

    # Orden final: fecha, endogena, exogenas (con la _L1 junto a la exo 4),
    # y despues las columnas auxiliares de imputacion y outliers.
    columnas_modelo = ["fecha"] + COLUMNAS_VARIABLES + [columna_rezagada]
    columnas_aux = (
        [f"{c}_metodo_imputacion" for c in COLUMNAS_VARIABLES]
        + [f"{c}_outlier" for c in COLUMNAS_VARIABLES]
    )
    columnas_extra = [c for c in df.columns if c not in columnas_modelo + columnas_aux]
    df = df[columnas_modelo + columnas_extra + columnas_aux]

    os.makedirs(CARPETA_PROCESADOS, exist_ok=True)
    df.to_csv(RUTA_PROCESADO, index=False, encoding="utf-8")

    hash_procesado = calcular_sha256(RUTA_PROCESADO)

    logging.info("Filas finales en datos_procesados: %s", len(df))
    logging.info("Columnas finales: %s", list(df.columns))
    logging.info("Variable exogena 4 para el modelo (rezagada): %s", columna_rezagada)
    logging.info("Archivo procesado guardado en: %s", RUTA_PROCESADO)
    logging.info("HASH SHA-256 del archivo procesado: %s", hash_procesado)
    logging.info("(Este hash va en el README.md, en la seccion de verificacion)")
    logging.info("=== Fin de limpieza de datos (Tema 22) ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Deja constancia del error en log_ejecucion.txt antes de detenerse
        logging.exception("La ejecucion termino con error")
        raise
