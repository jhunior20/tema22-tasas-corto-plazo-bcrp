# NOMBRES Y APELLIDOS COMPLETOS: Isai Jhunior Laymito Tacza
# CODIGO DE MATRICULA: 2024200505K
# TEMA: N.o 22 - Tasas de corto plazo en el Peru: interbancaria, certificados
#       del BCRP y tasa de referencia
# FECHA DE EXTRACCION: 24/09/2026
"""
01_extraccion_api.py

Via 1 (obligatoria) del numeral 2.4 de la consigna: consumo de la API
BCRPData del Banco Central de Reserva del Peru (BCRP) para descargar,
en frecuencia diaria, las series del modelo del tema 22: una variable
ENDOGENA (la tasa que se quiere explicar) y cuatro EXOGENAS (los
factores que explican su formacion y su desvio respecto de la tasa
de politica):

    ENDOGENA
    - PD04692MD : Tasa de interes interbancaria overnight, en soles (%)
                  -> la tasa de muy corto plazo que se quiere explicar.

    EXOGENAS
    - PD12301MD : Tasa de Referencia de la Politica Monetaria (%)
                  -> la señal de politica del BCRP (el ancla).
    - PD04679MD : Tasa de interes del saldo de Certificados de Deposito
                  del BCRP (CD BCRP) (%)
                  -> rendimiento del instrumento de esterilizacion.
    - PD04668MD : Depositos del sector publico en el BCRP (saldo,
                  millones S/)
                  -> factor autonomo de liquidez: flujos fiscales que
                  drenan o inyectan soles al sistema.
    - PD04665MD : Cuentas corrientes de bancos en el BCRP (saldo,
                  millones S/)
                  -> liquidez disponible de la banca (encaje en exceso
                  en soles). Esta variable se
                  usa REZAGADA (un periodo atras) para mitigar
                  simultaneidad; el rezago se aplica en
                  03_limpieza_datos.py, NO aqui (aqui se guarda la
                  serie cruda, sin desplazar, tal como sale de la
                  fuente).

La API de BCRPData es publica y no requiere token ni registro previo,
por eso este script no usa clave alguna en el .env (no hay clave que
declarar; el archivo .env.example queda vacio a proposito).

Documentacion oficial de la API:
https://estadisticas.bcrp.gob.pe/estadisticas/series/ayuda/api
"""

import os
import sys
import json
import time
import logging
from datetime import datetime

import requests
import pandas as pd

# ---------------------------------------------------------------------------
# 1) PARAMETROS CONGELADOS DE LA CONSULTA (numeral 2.4.5 de la consigna)
#    Se declaran como constantes fijas, NUNCA como fechas dinamicas tipo
#    "hoy", para que la extraccion sea reproducible y verificable.
# ---------------------------------------------------------------------------
FECHA_INICIO = "2015-01-01"   # inicio de la ventana exigida (>= 2500 obs diarias)
FECHA_CORTE = "2025-12-31"    # fin de la ventana; ajustar solo una vez y declararlo

CODIGO_MATRICULA = "2024200505K"  # se usa para nombrar los archivos de salida

# Series BCRPData que se consultan en esta via (mismo codigo -> misma frecuencia)
SERIES = {
    "PD04692MD": "tasa_interbancaria_on_end",
    "PD12301MD": "tasa_referencia_exo",
    "PD04679MD": "tasa_cdbcrp_saldo_exo",
    "PD04668MD": "depositos_sector_publico_saldo_exo",
    "PD04665MD": "cuentas_corrientes_bancos_bcrp_saldo_exo",
}

# Orden final exigido de columnas en el archivo crudo: fecha, endogena,
# exo1, exo2, exo3, exo4 (en ese orden, siempre, sin importar el orden
# en que el servidor de BCRPData devuelva las series en su respuesta).
ORDEN_COLUMNAS_SALIDA = ["fecha_bcrp"] + list(SERIES.values())

BASE_URL = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
IDIOMA = "esp"          # todo en español: nombres de series Y fechas (ej. 01.Ene.15)
FORMATO_SALIDA = "json"

# NOTA: __file__ no existe cuando el script se corre por celdas en la
# consola interactiva de Spyder (solo existe al correr el archivo
# completo). Por eso se resuelve con un try/except: si no existe, se usa
# el directorio de trabajo actual (el que Spyder tenga configurado).
try:
    _DIRECTORIO_SCRIPT = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _DIRECTORIO_SCRIPT = os.getcwd()

CARPETA_CRUDOS = os.path.join(_DIRECTORIO_SCRIPT, "..", "datos_crudos")
ARCHIVO_LOG = os.path.join(_DIRECTORIO_SCRIPT, "..", "log_ejecucion.txt")

# User-Agent identificable, tal como exige el numeral 2.4.8 de la consigna
HEADERS = {"User-Agent": "UNCP-FinanzasI-Tema22-Rey/1.0 (uso academico)"}


# ---------------------------------------------------------------------------
# 2) CONFIGURACION DEL LOG DE EJECUCION (numeral 2.4.2: log_ejecucion.txt)
# ---------------------------------------------------------------------------
def configurar_logging():
    """Registra en consola y en log_ejecucion.txt la fecha, hora, filas
    descargadas y codigo de respuesta HTTP de cada extraccion."""
    os.makedirs(CARPETA_CRUDOS, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(ARCHIVO_LOG, mode="a", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ---------------------------------------------------------------------------
# 3) CONSUMO DE LA API CON MANEJO DE ERRORES
# ---------------------------------------------------------------------------
def construir_url(codigos_series, fecha_ini, fecha_fin):
    """Arma la URL de consulta GET siguiendo la estructura oficial:
    .../api/[codigos]/[formato]/[periodo inicial]/[periodo final]/[idioma]
    Los codigos van separados por guion, como exige la API (max. 10 por
    consulta y todos de la misma frecuencia)."""
    codigos = "-".join(codigos_series)
    return f"{BASE_URL}/{codigos}/{FORMATO_SALIDA}/{fecha_ini}/{fecha_fin}/{IDIOMA}"


def descargar_series(codigos_series, fecha_ini, fecha_fin, reintentos=3, espera_seg=2):
    """Hace la solicitud GET a BCRPData con reintentos ante fallas
    temporales de red. Devuelve el JSON crudo tal como lo entrega el
    servidor (sin transformar), y el codigo de estado HTTP."""
    url = construir_url(codigos_series, fecha_ini, fecha_fin)
    ultimo_error = None

    for intento in range(1, reintentos + 1):
        try:
            respuesta = requests.get(url, headers=HEADERS, timeout=30)
            respuesta.raise_for_status()
            return respuesta.json(), respuesta.status_code, url
        except requests.exceptions.RequestException as err:
            ultimo_error = err
            logging.warning(
                "Intento %s/%s fallido para %s: %s", intento, reintentos, url, err
            )
            time.sleep(espera_seg * intento)  # backoff simple

    # Si tras todos los reintentos sigue fallando, se deja constancia en el
    # log y se detiene el script: esto es una falla tecnica (Bloque B),
    # no una falta de autenticidad de datos.
    logging.error("No se pudo descargar %s tras %s intentos: %s", url, reintentos, ultimo_error)
    raise RuntimeError(f"Fallo la extraccion de la API BCRPData: {ultimo_error}")


# ---------------------------------------------------------------------------
# 4) GUARDADO DEL CRUDO (tal como sale de la fuente, sin editar)
# ---------------------------------------------------------------------------
def guardar_json_crudo(json_crudo, codigo_matricula):
    """Guarda la respuesta cruda de la API en /datos_crudos, intacta
    (un diccionario {codigo_serie: respuesta JSON de esa serie}).
    Este archivo es la evidencia primaria y no se edita nunca."""
    os.makedirs(CARPETA_CRUDOS, exist_ok=True)
    ruta = os.path.join(CARPETA_CRUDOS, f"datos_crudos_api_{codigo_matricula}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(json_crudo, f, ensure_ascii=False, indent=2)
    return ruta


MESES_BCRP = {
    "Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Ago": 8, "Set": 9, "Sep": 9, "Oct": 10, "Nov": 11, "Dic": 12,
}


def fecha_bcrp_a_datetime(fecha_bcrp):
    """Convierte '05.Ene.15' a datetime. Solo se usa para ORDENAR las
    filas; la columna fecha_bcrp se guarda tal cual la entrega la API."""
    dia, mes, anio = fecha_bcrp.split(".")
    return datetime(2000 + int(anio), MESES_BCRP[mes], int(dia))


def serie_a_dataframe(json_serie, nombre_col):
    """Convierte la respuesta de UNA sola serie ({config, periods:[{name,
    values:[valor]}]}) a un DataFrame de dos columnas: fecha_bcrp y la
    serie. No limpia ni imputa nada ('n.d.' se deja tal cual): esa es
    tarea de 03_limpieza_datos.py."""
    filas = [
        {"fecha_bcrp": p.get("name"), nombre_col: (p.get("values") or [None])[0]}
        for p in json_serie.get("periods", [])
    ]
    return pd.DataFrame(filas, columns=["fecha_bcrp", nombre_col])


def json_a_dataframe(jsons_por_codigo, mapa_nombres, orden_columnas_salida):
    """Une las series descargadas POR SEPARADO en un DataFrame ancho: una
    fila por fecha, una columna por serie.

    IMPORTANTE: cuando se piden varias series en una sola consulta, el
    servidor de BCRPData las devuelve reordenadas (por codigo) y el
    'name' de config.series NO trae el codigo, asi que no hay forma
    segura de saber que posicion de 'values' corresponde a cada serie.
    Por eso cada serie se descarga en su propia consulta y aqui se unen
    por fecha (outer join, para no perder dias que falten en alguna
    serie). Al final se ordena cronologicamente y se fuerzan las
    columnas segun 'orden_columnas_salida'."""
    df = None
    for codigo, nombre_col in mapa_nombres.items():
        df_serie = serie_a_dataframe(jsons_por_codigo[codigo], nombre_col)
        df = df_serie if df is None else df.merge(df_serie, on="fecha_bcrp", how="outer")

    df["_orden"] = df["fecha_bcrp"].map(fecha_bcrp_a_datetime)
    df = df.sort_values("_orden").drop(columns="_orden").reset_index(drop=True)
    return df[orden_columnas_salida]


# ---------------------------------------------------------------------------
# 5) PROGRAMA PRINCIPAL
# ---------------------------------------------------------------------------
def main():
    configurar_logging()
    logging.info("=== Inicio de extraccion API BCRPData (Tema 22) ===")
    logging.info("Periodo solicitado: %s a %s", FECHA_INICIO, FECHA_CORTE)

    # Una consulta por serie: garantiza que cada columna corresponde a su
    # codigo (ver json_a_dataframe).
    json_crudo = {}
    for codigo in SERIES:
        json_serie, status_code, url_usada = descargar_series([codigo], FECHA_INICIO, FECHA_CORTE)
        json_crudo[codigo] = json_serie
        logging.info("Serie %s | HTTP %s | filas descargadas: %s | URL: %s",
                     codigo, status_code, len(json_serie.get("periods", [])), url_usada)

    ruta_crudo = guardar_json_crudo(json_crudo, CODIGO_MATRICULA)
    df = json_a_dataframe(json_crudo, SERIES, ORDEN_COLUMNAS_SALIDA)

    ruta_csv_crudo = os.path.join(
        CARPETA_CRUDOS, f"datos_crudos_api_{CODIGO_MATRICULA}.csv"
    )
    df.to_csv(ruta_csv_crudo, index=False, encoding="utf-8")

    # Ademas del CSV combinado, se guarda un crudo POR VARIABLE (fecha +
    # esa sola columna), para poder revisar cada serie de forma
    # independiente sin tener que filtrar la tabla grande.
    rutas_csv_por_variable = []
    for nombre_columna in SERIES.values():
        ruta_var = os.path.join(
            CARPETA_CRUDOS, f"datos_crudos_api_{CODIGO_MATRICULA}_{nombre_columna}.csv"
        )
        df[["fecha_bcrp", nombre_columna]].to_csv(ruta_var, index=False, encoding="utf-8")
        rutas_csv_por_variable.append(ruta_var)
        logging.info("CSV individual guardado: %s", ruta_var)

    logging.info("Filas descargadas: %s", len(df))
    logging.info("JSON crudo guardado en: %s", ruta_crudo)
    logging.info("CSV crudo combinado guardado en: %s", ruta_csv_crudo)
    logging.info("CSV individuales por variable guardados: %s", len(rutas_csv_por_variable))
    logging.info("=== Fin de extraccion API BCRPData (Tema 22) ===")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Deja constancia del error en log_ejecucion.txt antes de detenerse
        logging.exception("La ejecucion termino con error")
        raise
