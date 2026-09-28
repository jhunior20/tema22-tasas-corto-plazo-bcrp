# NOMBRES Y APELLIDOS COMPLETOS: Isai Jhunior Laymito Tacza
# CODIGO DE MATRICULA: 2024200505K
# TEMA: N.o 22 - Tasas de corto plazo en el Peru: interbancaria, certificados
#       del BCRP y tasa de referencia
# FECHA DE EXTRACCION: 24/09/2026
"""
04_analisis.py
Estimaciones, tablas y figuras del articulo, generadas desde el archivo
procesado que produce 03_limpieza_datos.py y guardadas en /salidas.

TEMA N.22: Tasas de corto plazo en el Peru: interbancaria, certificados
del BCRP y tasa de referencia.

OBJETIVO DE INVESTIGACION: Analizar la formacion de las tasas de muy
corto plazo y su desvio respecto de la tasa de politica.

Autor: Isai Jhunior Laymito Tacza  -  Codigo: 2024200505K

Entrada : datos_procesados/datos_procesados_2024200505K.csv (salida de 03)
Salidas : salidas/  (tablas .csv, figuras .png, base final y hash)
Log     : log_ejecucion.txt (todo lo que se muestra en pantalla)

Que hace, en orden:
  (1) Lee el procesado y usa las columnas *_metodo_imputacion para separar
      valores publicados de valores imputados.
  (2) Reconstruye la tasa de referencia como variable de escalones: la ultima
      tasa publicada sigue vigente hasta la siguiente decision del Directorio.
      Interpolarla seria un error, porque cambia por decisiones discretas.
  (3) Elimina la primera fila, cuya cuenta corriente rezagada no existe: no se
      rellena con el dato contemporaneo.
  (4) Calcula el desvio sobre la muestra publicada (principal) y sobre la
      completa (robustez), por anio y por etapa de politica.
  (5) Contrasta raiz unitaria (ADF, KPSS) y cointegracion (Engle-Granger).
  (6) Estima el vector de largo plazo por MCO-HAC y por DOLS.
  (7) Estima la regresion ampliada en niveles y el modelo de correccion de
      errores, con los diagnosticos del propio modelo dinamico.
  (8) Obtiene la vida media simulando la dinamica completa, no con la formula
      simplificada, porque el modelo incluye la variacion rezagada.
  (9) Genera las figuras desde esta misma base.
  (10) Guarda la base final y calcula su hash SHA-256.
"""
import os
import sys
import hashlib
import logging
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, kpss, coint
from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan
from statsmodels.stats.stattools import jarque_bera, durbin_watson
from statsmodels.graphics.tsaplots import plot_acf
from scipy import stats

COD = "2024200505K"

# Rutas relativas a la carpeta del script (no a la carpeta desde donde se
# ejecuta), igual que en 01 y 03. __file__ no existe al correr por celdas
# en Spyder: en ese caso se usa el directorio de trabajo actual.
try:
    _DIRECTORIO_SCRIPT = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _DIRECTORIO_SCRIPT = os.getcwd()
PROC = os.path.join(_DIRECTORIO_SCRIPT, "..", "datos_procesados", "datos_procesados_%s.csv" % COD)
SAL = os.path.join(_DIRECTORIO_SCRIPT, "..", "salidas") + os.sep
ARCHIVO_LOG = os.path.join(_DIRECTORIO_SCRIPT, "..", "log_ejecucion.txt")
os.makedirs(SAL, exist_ok=True)

# Todo lo que el script muestra queda tambien en log_ejecucion.txt
# (numeral 2.4.2), igual que en 01 y 03. Las advertencias de statsmodels
# (ej. KPSS fuera de la tabla de valores criticos) tambien van al log.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(ARCHIVO_LOG, mode="a", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
logging.captureWarnings(True)


def log(texto):
    logging.info(texto)


def registrar_error(tipo, valor, traza):
    """Deja constancia del error en log_ejecucion.txt antes de detenerse."""
    logging.error("La ejecucion termino con error", exc_info=(tipo, valor, traza))


sys.excepthook = registrar_error

log("=== Inicio de analisis (Tema 22) ===")

pd.set_option("display.width", 200)
plt.rcParams.update({"font.size": 11, "axes.grid": True, "grid.alpha": .25,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 160, "savefig.bbox": "tight"})
AZUL, NARANJA, GRIS, ROJO = "#2166AC", "#D95F02", "#8C8C8C", "#B2182B"

# ---------------------------------------------------------------------------
# (1) Lectura y separacion entre publicados e imputados
# ---------------------------------------------------------------------------
d = pd.read_csv(PROC, parse_dates=["fecha"]).sort_values("fecha").reset_index(drop=True)
VARS = ["tasa_interbancaria_on_end", "tasa_referencia_exo", "tasa_cdbcrp_saldo_exo",
        "depositos_sector_publico_saldo_exo", "cuentas_corrientes_bancos_bcrp_saldo_exo"]
pub = {v: d[v + "_metodo_imputacion"].isna() for v in VARS}

cob = pd.DataFrame([dict(variable=v, publicados=int(pub[v].sum()),
                         imputados=int((~pub[v]).sum()),
                         pct_imputado=round(100 * (~pub[v]).mean(), 2)) for v in VARS])
cob.to_csv(SAL + "tabla_cobertura_datos_%s.csv" % COD, index=False)
log("=== (1) COBERTURA (n = %d fechas del calendario) ===" % len(d))
log("\n" + cob.to_string(index=False))

# ---------------------------------------------------------------------------
# (2) Tasa de referencia como variable de escalones
# ---------------------------------------------------------------------------
ref_pub = d["tasa_referencia_exo"].where(pub["tasa_referencia_exo"])
d["ref_escalon"] = ref_pub.ffill()
d["ref_escalon_alt"] = ref_pub.bfill()          # convencion contraria, para sensibilidad
amb = (~pub["tasa_referencia_exo"]) & (d.ref_escalon != d.ref_escalon_alt) & d.ref_escalon.notna()
log("Fechas sin publicar con cambio de tasa dentro del tramo: %d" % amb.sum())
log("\n" + d.loc[amb, ["fecha", "ref_escalon", "ref_escalon_alt"]].to_string(index=False))

# ---------------------------------------------------------------------------
# (3) Base de estimacion: se elimina la fila de borde del rezago
# ---------------------------------------------------------------------------
borde = d["cuentas_corrientes_bancos_bcrp_saldo_exo_L1_metodo_imputacion"].notna()
log("Filas eliminadas por rezago de borde: %d" % borde.sum())
d["ib"] = d["tasa_interbancaria_on_end"]
d["cd"] = d["tasa_cdbcrp_saldo_exo"]
d["ln_dep"] = np.log(d["depositos_sector_publico_saldo_exo"])
d["ln_cc_L1"] = np.log(d["cuentas_corrientes_bancos_bcrp_saldo_exo_L1"])
d["desvio"] = d.ib - d.ref_escalon
d["obs_par"] = pub["tasa_interbancaria_on_end"] & pub["tasa_referencia_exo"]
log("Jornadas con interbancaria y referencia publicadas: %d" % d.obs_par.sum())

est = d[~borde].reset_index(drop=True)
log("Observaciones para los modelos: %d" % len(est))

# ---------------------------------------------------------------------------
# (4) Desvio: muestra publicada (principal) y completa (robustez)
# ---------------------------------------------------------------------------
def resumen(x, etiqueta):
    x = x.dropna()
    return dict(muestra=etiqueta, n=len(x), medio=x.mean(), abs_medio=x.abs().mean(),
                de=x.std(ddof=1), min=x.min(), max=x.max(),
                pct_sobre=100 * (x > 1e-9).mean(), pct_igual=100 * (x.abs() < 1e-9).mean(),
                pct_bajo=100 * (x < -1e-9).mean(),
                pct_banda10=100 * (x.abs() <= 0.10 + 1e-9).mean(),
                pct_sobre25=100 * (x.abs() > 0.25 + 1e-9).mean())


cmp_d = pd.DataFrame([resumen(d.loc[d.obs_par, "desvio"], "Publicada (ambas tasas)"),
                      resumen(d["desvio"], "Completa (con imputacion)")])
cmp_d.to_csv(SAL + "tabla_comparacion_desvio_%s.csv" % COD, index=False)
log("=== (4) DESVIO: PUBLICADA VS COMPLETA ===")
log("\n" + cmp_d.round(4).to_string(index=False))
sub = d.loc[d.obs_par, "desvio"].dropna()
m0 = sm.OLS(sub.values, np.ones(len(sub))).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
log("Media del desvio (publicada): %.4f pp, EE HAC %.4f, p = %.4g"
    % (m0.params[0], m0.bse[0], m0.pvalues[0]))

ETAPAS = [("2015-01-01", "2017-05-11", "1. Alzas y estabilidad (3.25 a 4.25 %)"),
          ("2017-05-12", "2020-03-19", "2. Relajamiento gradual (4.25 a 2.25 %)"),
          ("2020-03-20", "2021-08-12", "3. Estimulo COVID-19 (minimo 0.25 %)"),
          ("2021-08-13", "2023-09-14", "4. Alzas por inflacion (0.25 a 7.75 %)"),
          ("2023-09-15", "2025-12-31", "5. Recortes (7.75 a 4.25 %)")]
fil = []
for a, b, nom in ETAPAS:
    r = resumen(d[(d.fecha >= a) & (d.fecha <= b) & d.obs_par]["desvio"], nom)
    r["etapa"] = r.pop("muestra")
    fil.append(r)
tab_etapa = pd.DataFrame(fil)[["etapa", "n", "medio", "abs_medio", "de", "min", "max",
                               "pct_sobre", "pct_igual", "pct_bajo"]]
tab_etapa.to_csv(SAL + "tabla_desvio_por_etapa_%s.csv" % COD, index=False)
log("=== (4) DESVIO POR ETAPA (muestra publicada) ===")
log("\n" + tab_etapa.round(4).to_string(index=False))

P = d[d.obs_par]
g = P.groupby(P.fecha.dt.year)["desvio"]
tab_anio = pd.DataFrame({"n": g.size(), "medio": g.mean(),
                         "abs_medio": g.agg(lambda x: x.abs().mean()),
                         "de": g.agg(lambda x: x.std(ddof=1)), "min": g.min(), "max": g.max(),
                         "pct_sobre": 100 * g.agg(lambda x: (x > 1e-9).mean()),
                         "pct_igual": 100 * g.agg(lambda x: (x.abs() < 1e-9).mean()),
                         "pct_bajo": 100 * g.agg(lambda x: (x < -1e-9).mean())}).reset_index()
tab_anio.to_csv(SAL + "tabla_desvio_por_anio_%s.csv" % COD, index=False)
(P.reindex(P.desvio.abs().sort_values(ascending=False).index)
 .head(10)[["fecha", "ib", "ref_escalon", "desvio"]]
 .to_csv(SAL + "tabla_top10_desvios_%s.csv" % COD, index=False))

desc = pd.DataFrame([dict(variable=n, n=len(est), M=est[c].mean(), DE=est[c].std(ddof=1),
                          min=est[c].min(), p25=est[c].quantile(.25), mediana=est[c].median(),
                          p75=est[c].quantile(.75), max=est[c].max())
                     for n, c in [("Tasa interbancaria (%)", "ib"),
                                  ("Tasa de referencia (%)", "ref_escalon"),
                                  ("Tasa CD BCRP (%)", "cd"),
                                  ("Depositos del sector publico (mill. S/)",
                                   "depositos_sector_publico_saldo_exo"),
                                  ("Cuenta corriente de bancos (mill. S/)",
                                   "cuentas_corrientes_bancos_bcrp_saldo_exo_L1")]])
desc.to_csv(SAL + "tabla_descriptivos_%s.csv" % COD, index=False)
(est[["ib", "ref_escalon", "cd", "ln_dep", "ln_cc_L1"]].corr()
 .to_csv(SAL + "tabla_correlacion_%s.csv" % COD))

# ---------------------------------------------------------------------------
# (5) Raiz unitaria y cointegracion
# ---------------------------------------------------------------------------
fil = []
for nom, s in [("Tasa interbancaria", est.ib), ("Tasa de referencia", est.ref_escalon),
               ("Tasa CD BCRP", est.cd), ("Desvio", est.ib - est.ref_escalon)]:
    for dif, et in [(False, "nivel"), (True, "primera diferencia")]:
        x = s.diff().dropna() if dif else s.dropna()
        a = adfuller(x, autolag="AIC", regression="c", result_object=False)
        k = kpss(x, regression="c", nlags="auto", result_object=False)
        fil.append(dict(serie=nom, transformacion=et, adf=a[0], adf_p=a[1], adf_rezagos=a[2],
                        adf_vc5=a[4]["5%"], kpss=k[0], kpss_vc5=k[3]["5%"],
                        adf_rechaza_RU_5=a[1] < .05, kpss_rechaza_estac_5=k[0] > k[3]["5%"]))
tab_ur = pd.DataFrame(fil)
tab_ur.to_csv(SAL + "tabla_raiz_unitaria_%s.csv" % COD, index=False)
log("=== (5) RAIZ UNITARIA (ADF y KPSS, constante sin tendencia) ===")
log("\n" + tab_ur.round(4).to_string(index=False))

y, x = est.ib.values, est.ref_escalon.values
eg = coint(y, x, trend="c", autolag="AIC")
pd.DataFrame([dict(prueba="Engle-Granger (interbancaria ~ referencia)", estadistico=eg[0],
                   p=eg[1], vc_1=eg[2][0], vc_5=eg[2][1], n=len(y))]
             ).to_csv(SAL + "tabla_cointegracion_%s.csv" % COD, index=False)
log("Engle-Granger: %.4f (vc 1 %% = %.4f)" % (eg[0], eg[2][0]))

# ---------------------------------------------------------------------------
# (6) Vector de largo plazo: MCO-HAC, DOLS y submuestra publicada
# ---------------------------------------------------------------------------
mc = sm.OLS(y, sm.add_constant(x)).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
K = 4
dx = pd.Series(x).diff()
Z = sm.add_constant(pd.concat([pd.Series(x)] +
                              [dx.shift(-j).rename("l%+d" % j) for j in range(-K, K + 1)], axis=1))
ok = Z.notna().all(axis=1)
dols = sm.OLS(y[ok.values], Z[ok]).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
sp = est[est.obs_par]
mp = sm.OLS(sp.ib, sm.add_constant(sp.ref_escalon)).fit(cov_type="HAC", cov_kwds={"maxlags": 8})


def fila(nombre, n, th, se):
    z = (th - 1) / se
    return dict(metodo=nombre, n=n, theta1=th, ee=se, ic_inf=th - 1.96 * se,
                ic_sup=th + 1.96 * se, z=z, p=2 * (1 - stats.norm.cdf(abs(z))))


tab_lp = pd.DataFrame([fila("MCO estatico, EE HAC", len(y), mc.params[1], mc.bse[1]),
                       fila("DOLS (4 adelantos y 4 rezagos)", int(ok.sum()),
                            dols.params.iloc[1], dols.bse.iloc[1]),
                       fila("MCO, solo jornadas publicadas", len(sp),
                            mp.params.iloc[1], mp.bse.iloc[1])])
tab_lp.to_csv(SAL + "tabla_largo_plazo_%s.csv" % COD, index=False)
log("=== (6) VECTOR DE LARGO PLAZO ===")
log("\n" + tab_lp.round(6).to_string(index=False))
log("Constante MCO: %.4f (EE %.4f, p = %.4g)" % (mc.params[0], mc.bse[0], mc.pvalues[0]))

# ---------------------------------------------------------------------------
# (7) Regresion ampliada en niveles y modelo de correccion de errores
# ---------------------------------------------------------------------------
Xn = sm.add_constant(est[["ref_escalon", "cd", "ln_dep", "ln_cc_L1"]])
mn = sm.OLS(est.ib, Xn).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
zn = (mn.params["ref_escalon"] - 1) / mn.bse["ref_escalon"]
(pd.DataFrame({"coef": mn.params, "EE_HAC": mn.bse, "z": mn.tvalues, "p": mn.pvalues})
 .to_csv(SAL + "tabla_regresion_%s.csv" % COD))
log("=== (7) MCO AMPLIADO (n = %d, R2 = %.4f) ===" % (int(mn.nobs), mn.rsquared))
log("\n" + pd.DataFrame({"coef": mn.params, "EE": mn.bse, "p": mn.pvalues}).round(6).to_string())
log("z de traspaso unitario: %.4f (p = %.4g)" % (zn, 2 * (1 - stats.norm.cdf(abs(zn)))))
for nom, s in [("ln_dep", est.ln_dep), ("ln_cc_L1", est.ln_cc_L1)]:
    a = adfuller(s.dropna(), autolag="AIC", regression="c", result_object=False)
    log("  ADF %s: %.3f (p = %.3f)" % (nom, a[0], a[1]))

est = est.copy()
est["ect_L1"] = pd.Series(mc.resid, index=est.index).shift(1)
for c in ["ib", "ref_escalon", "cd", "ln_dep", "ln_cc_L1"]:
    est["d_" + c] = est[c].diff()
est["d_ib_L1"] = est.d_ib.shift(1)
REG = ["d_ref_escalon", "d_cd", "d_ln_dep", "d_ln_cc_L1", "ect_L1", "d_ib_L1"]
e = est.dropna(subset=["d_ib"] + REG)
mce = sm.OLS(e.d_ib, sm.add_constant(e[REG])).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
(pd.DataFrame({"coef": mce.params, "EE_HAC": mce.bse, "z": mce.tvalues, "p": mce.pvalues})
 .to_csv(SAL + "tabla_mce_%s.csv" % COD))
log("=== (7) MCE (n = %d, R2 = %.4f) ===" % (int(mce.nobs), mce.rsquared))
log("\n" + pd.DataFrame({"coef": mce.params, "EE": mce.bse, "p": mce.pvalues}).round(6).to_string())
log("IC 95 %% de phi: [%.4f, %.4f]" % (mce.params["d_ref_escalon"] - 1.96 * mce.bse["d_ref_escalon"],
                                       mce.params["d_ref_escalon"] + 1.96 * mce.bse["d_ref_escalon"]))

lb = acorr_ljungbox(mce.resid, lags=[5, 10, 20], return_df=True)
bp = het_breuschpagan(mce.resid, sm.add_constant(e[REG]))
jb = jarque_bera(mce.resid)
diag = pd.DataFrame([dict(indicador="Durbin-Watson", valor=durbin_watson(mce.resid), p=np.nan)] +
                    [dict(indicador="Ljung-Box (%d rezagos)" % L, valor=lb.lb_stat.iloc[i],
                          p=lb.lb_pvalue.iloc[i]) for i, L in enumerate([5, 10, 20])] +
                    [dict(indicador="Breusch-Pagan", valor=bp[0], p=bp[1]),
                     dict(indicador="Jarque-Bera", valor=jb[0], p=jb[1])])
diag.to_csv(SAL + "tabla_diagnosticos_mce_%s.csv" % COD, index=False)
log("--- Diagnosticos de los residuos del MCE ---")
log("\n" + diag.round(4).to_string(index=False))

# ---------------------------------------------------------------------------
# (8) Vida media con la dinamica completa
# ---------------------------------------------------------------------------
lam, rho = mce.params["ect_L1"], mce.params["d_ib_L1"]


def vida_media(lam, rho, H=400):
    """Respuesta del desvio a un choque unitario: Dib_t = lam*u_{t-1} + rho*Dib_{t-1}."""
    u, dib = 1.0, 0.0
    for h in range(1, H + 1):
        dib = lam * u + rho * dib
        u = u + dib
        if abs(u) <= 0.5:
            return h
    return np.nan


vm = vida_media(lam, rho)
V = mce.cov_params().loc[["ect_L1", "d_ib_L1"], ["ect_L1", "d_ib_L1"]].values
rng = np.random.default_rng(20242005)
vms = np.array([vida_media(a, b) for a, b in rng.multivariate_normal([lam, rho], V, 5000) if a < 0])
vms = vms[~np.isnan(vms)]
log("Vida media con la dinamica completa: %.0f dias  (banda %.0f a %.0f)"
    % (vm, np.percentile(vms, 2.5), np.percentile(vms, 97.5)))
log("Aproximacion ln(0.5)/ln(1+lambda), que ignora rho: %.1f dias"
    % (np.log(.5) / np.log(1 + lam)))

# robustez: sin diferencias que cruzan jornadas imputadas
flag = (~e.obs_par).values
e2 = e[~(flag | np.r_[False, flag[:-1]])]
mce2 = sm.OLS(e2.d_ib, sm.add_constant(e2[REG])).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
pd.DataFrame({"parametro": ["Traspaso contemporaneo", "Correccion de errores",
                            "Variacion rezagada", "n", "R2"],
              "MCE completo": [mce.params["d_ref_escalon"], mce.params["ect_L1"],
                               mce.params["d_ib_L1"], int(mce.nobs), mce.rsquared],
              "Sin tramos imputados": [mce2.params["d_ref_escalon"], mce2.params["ect_L1"],
                                       mce2.params["d_ib_L1"], int(mce2.nobs), mce2.rsquared]}
             ).to_csv(SAL + "tabla_robustez_mce_%s.csv" % COD, index=False)
log("Robustez: phi = %.4f, lambda = %.4f, vida media = %.0f dias (n = %d)"
    % (mce2.params["d_ref_escalon"], mce2.params["ect_L1"],
       vida_media(mce2.params["ect_L1"], mce2.params["d_ib_L1"]), int(mce2.nobs)))

# ---------------------------------------------------------------------------
# (8b) Cifras citadas en el texto del articulo que no estan en otra tabla
# ---------------------------------------------------------------------------
def cifras_desvio(x, periodo):
    return [("Desvio medio %s (pb, muestra publicada)" % periodo, 100 * x.mean()),
            ("Jornadas dentro de +/-10 pb %s (%%, muestra publicada)" % periodo,
             100 * (x.abs() <= 0.10 + 1e-9).mean())]


dep = d["depositos_sector_publico_saldo_exo"]
cifras = pd.DataFrame(
    cifras_desvio(P.loc[P.fecha.dt.year <= 2016, "desvio"], "2015-2016")
    + cifras_desvio(P.loc[P.fecha.dt.year >= 2017, "desvio"], "2017-2025")
    + [("Durbin-Watson de la regresion ampliada en niveles", durbin_watson(mn.resid)),
       ("Depositos del sector publico: minimo de 2017 (mill. S/)",
        dep[d.fecha.dt.year == 2017].min()),
       ("Depositos del sector publico: maximo de la muestra (mill. S/), el %s"
        % d.fecha[dep.idxmax()].strftime("%d/%m/%Y"), dep.max()),
       ("Depositos del sector publico: ultimo dato de 2025 (mill. S/)", dep.iloc[-1])],
    columns=["cifra", "valor"])
cifras.to_csv(SAL + "tabla_cifras_texto_%s.csv" % COD, index=False)
log("=== (8b) CIFRAS CITADAS EN EL TEXTO ===")
log("\n" + cifras.round(4).to_string(index=False))

# ---------------------------------------------------------------------------
# (9) Figuras desde esta misma base
# ---------------------------------------------------------------------------
def anios(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def guardar(fig, n):
    fig.savefig(SAL + "fig_%s_%s.png" % (n, COD)); plt.close(fig); log("  fig_%s" % n)


log("=== (9) FIGURAS ===")
ib_pub = d.ib.where(pub["tasa_interbancaria_on_end"])
fig, ax = plt.subplots(figsize=(7.6, 3.5))
ax.plot(d.fecha, d.ref_escalon, color=NARANJA, lw=1.8, drawstyle="steps-post",
        label="Tasa de referencia (escalones)")
ax.plot(d.fecha, ib_pub, color=AZUL, lw=.8, label="Interbancaria overnight")
for a, b, _ in ETAPAS[1:]:
    ax.axvline(pd.Timestamp(a), color=GRIS, lw=.6, ls=":")
ax.set_ylabel("% anual"); ax.legend(frameon=False, loc="upper center", ncol=2, fontsize=9.5)
anios(ax); guardar(fig, "interbancaria_vs_referencia")

fig, ax = plt.subplots(figsize=(7.6, 3.5))
ax.plot(d.fecha, d.ref_escalon, color=NARANJA, lw=1.8, drawstyle="steps-post",
        label="Tasa de referencia")
ax.plot(d.fecha, d.cd.where(pub["tasa_cdbcrp_saldo_exo"]), color="#1B7837", lw=1.2,
        label="Tasa del saldo de CD BCRP")
ax.set_ylabel("% anual"); ax.legend(frameon=False, loc="upper center", ncol=2, fontsize=9.5)
anios(ax); guardar(fig, "cdbcrp_vs_referencia")

fig, ax = plt.subplots(figsize=(7.6, 3.5))
ax.axhline(0, color="black", lw=.8)
ax.axhspan(-.10, .10, color=GRIS, alpha=.18, label="Banda de ±10 puntos básicos")
ax.plot(P.fecha, P.desvio, color=AZUL, lw=.7)
ax.set_ylabel("Puntos porcentuales"); ax.legend(frameon=False, loc="upper right", fontsize=9.5)
anios(ax); guardar(fig, "desvio_interbancaria")

comp = pd.DataFrame({"Por encima": 100 * g.agg(lambda x: (x > 1e-9).mean()),
                     "Igual a la meta": 100 * g.agg(lambda x: (x.abs() < 1e-9).mean()),
                     "Por debajo": 100 * g.agg(lambda x: (x < -1e-9).mean())})
fig, ax = plt.subplots(figsize=(7.2, 3.4))
comp.plot(kind="bar", stacked=True, ax=ax, color=[NARANJA, GRIS, AZUL], width=.78,
          edgecolor="white", lw=.4)
ax.set_xlabel(""); ax.set_ylabel("% de jornadas publicadas"); ax.set_ylim(0, 100)
ax.legend(frameon=False, ncol=3, fontsize=9.5, loc="lower center", bbox_to_anchor=(.5, -.32))
plt.xticks(rotation=0); guardar(fig, "estado_diario_por_anio")

fig, ax = plt.subplots(figsize=(7.2, 3.4))
bp_ = ax.boxplot([P[(P.fecha >= a) & (P.fecha <= b)].desvio.values for a, b, _ in ETAPAS],
                 tick_labels=["1. Alzas y\nestabilidad", "2. Relajamiento\ngradual",
                              "3. Estímulo\nCOVID-19", "4. Alzas por\ninflación", "5. Recortes"],
                 flierprops=dict(marker=".", ms=2.5, mfc=GRIS, mec=GRIS, alpha=.5),
                 medianprops=dict(color=ROJO, lw=1.4), patch_artist=True)
for b_ in bp_["boxes"]:
    b_.set(facecolor="#D1E5F0", edgecolor=AZUL)
ax.axhline(0, color="black", lw=.7); ax.set_ylabel("Desvío (puntos porcentuales)")
ax.tick_params(axis="x", labelsize=9); guardar(fig, "boxplot_desvio_por_etapa")

piv = (P.assign(a=P.fecha.dt.year, m=P.fecha.dt.month)
       .pivot_table(index="m", columns="a", values="desvio", aggfunc="mean"))
fig, ax = plt.subplots(figsize=(7.2, 3.6))
v = np.nanmax(np.abs(piv.values))
im = ax.imshow(piv.values, cmap="RdBu_r", vmin=-v, vmax=v, aspect="auto")
ax.set_xticks(range(piv.shape[1])); ax.set_xticklabels(piv.columns, fontsize=9)
ax.set_yticks(range(12)); ax.set_yticklabels(
    ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"], fontsize=9)
ax.grid(False); fig.colorbar(im, ax=ax, shrink=.85, label="Desvío medio (pp)")
guardar(fig, "heatmap_desvio_mensual")

fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 4.2), sharex=True)
a1.plot(d.fecha, d.depositos_sector_publico_saldo_exo.where(
    pub["depositos_sector_publico_saldo_exo"]), color=AZUL, lw=.9)
a1.set_ylabel("Depósitos del\nsector público\n(millones de S/)", fontsize=9.5)
a2.plot(d.fecha, d.cuentas_corrientes_bancos_bcrp_saldo_exo.where(
    pub["cuentas_corrientes_bancos_bcrp_saldo_exo"]), color=NARANJA, lw=.7)
a2.set_ylabel("Cuenta corriente\nde los bancos\n(millones de S/)", fontsize=9.5)
anios(a2); guardar(fig, "variables_liquidez")

fig, ax = plt.subplots(figsize=(7.2, 3.2))
ax.plot(d.fecha, d.cd, color="#1B7837", lw=.8, alpha=.55, label="Tasa del saldo de CD BCRP")
ax.plot(d.fecha, d.cd.rolling(90, min_periods=30).mean(), color="#00441B", lw=1.8,
        label="Promedio móvil de 90 días")
ax.set_ylabel("% anual"); ax.legend(frameon=False, fontsize=9.5)
anios(ax); guardar(fig, "evolucion_cdbcrp_suavizada")

fig, ax = plt.subplots(figsize=(7.2, 3.2))
plot_acf(mce.resid, lags=40, ax=ax, color=AZUL, vlines_kwargs={"colors": AZUL})
ax.set_title(""); ax.set_xlabel("Rezago (días)"); ax.set_ylabel("Autocorrelación")
guardar(fig, "autocorrelacion_residuos_mce")

# ---------------------------------------------------------------------------
# (10) Base final y huella de verificacion
# ---------------------------------------------------------------------------
final = est[["fecha", "ib", "ref_escalon", "cd", "ln_dep", "ln_cc_L1"]].rename(columns={
    "ib": "tasa_interbancaria_on_end", "ref_escalon": "tasa_referencia_escalon",
    "cd": "tasa_cdbcrp_saldo_exo", "ln_dep": "ln_depositos", "ln_cc_L1": "ln_ctacte_L1"})
ruta = SAL + "datos_analisis_%s.csv" % COD
final.to_csv(ruta, index=False)
with open(ruta, "rb") as f:
    h = hashlib.sha256(f.read()).hexdigest()
with open(SAL + "hash_%s.txt" % COD, "w", encoding="utf-8") as f:
    f.write(h + "  " + os.path.basename(ruta) + "\n")
log("Base final: %s  (%d filas, %d columnas)" % (ruta, len(final), final.shape[1]))
log("SHA-256: %s" % h)
log("Listo. Tablas y figuras en %s" % SAL)
log("=== Fin de analisis (Tema 22) ===")
