"""MODELO: proyección del presupuesto del año siguiente por simulación (bootstrap de meses).

Cada año simulado toma 12 meses al azar (con reemplazo) entre los meses maduros observados,
suma su costo y aplica el IPC. Con 10.000 años simulados se obtienen P10, P50 y P90.
Se compara con la proyección lineal (costo mensual promedio x 12 x (1 + IPC)).

Supuesto: el segundo semestre repite el ciclo del primero (una temporada de lluvias con pico de
daños en cada semestre, confirmado por el área de Mantenimiento). La prueba ene-abr -> may-jun
muestra que los meses dentro de un semestre NO son intercambiables, por lo que el rango P10-P90
subestima la incertidumbre real. Con históricos de años completos se podrá modelar la estacionalidad.
"""
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

N_SIMULACIONES = 10_000
SEMILLA = 42


def simular(mensual, n_meses, rng):
    """mensual: DataFrame (mes x segmento). Devuelve DataFrame (simulación x segmento) con el costo sumado."""
    idx = rng.integers(0, len(mensual), size=(N_SIMULACIONES, n_meses))
    return pd.DataFrame(mensual.values[idx].sum(axis=1), columns=mensual.columns)


def proyectar(con):
    base = pd.read_sql("SELECT Mes, TIPO, Centro, Valor_Total FROM v_base_modelo", con)
    base["Segmento"] = base["TIPO"] + " - " + base["Centro"].astype(str)
    mensual = base.pivot_table(index="Mes", columns="Segmento", values="Valor_Total", aggfunc="sum", fill_value=0)
    for tipo in ["Poste", "TD"]:
        mensual[tipo] = mensual[[c for c in mensual.columns if c.startswith(tipo + " -")]].sum(axis=1)
    mensual["Total"] = mensual[["Poste", "TD"]].sum(axis=1)

    rng = np.random.default_rng(SEMILLA)
    sim = simular(mensual, 12, rng) * (1 + C.IPC_CIERRE)
    lineal = mensual.sum() / len(mensual) * 12 * (1 + C.IPC_CIERRE)
    p = sim.quantile([.10, .50, .90]).T
    resultado = pd.DataFrame({"Segmento": mensual.columns, "Proyeccion_lineal": lineal.values,
                              "P10": p[0.10].values, "P50": p[0.50].values, "P90": p[0.90].values})
    resultado["P90_vs_lineal"] = resultado["P90"] / resultado["Proyeccion_lineal"] - 1

    # Validación: con ene-abr se proyectan may-jun y se verifica si el valor real cae en [P10, P90]
    entrena, prueba = mensual.loc[mensual.index <= 4], mensual.loc[mensual.index > 4]
    sim_val = simular(entrena, len(prueba), np.random.default_rng(SEMILLA))
    validacion = pd.DataFrame({"Segmento": mensual.columns, "Real": prueba.sum().values,
                               "P10": sim_val.quantile(.10).values, "P50": sim_val.quantile(.50).values,
                               "P90": sim_val.quantile(.90).values})
    validacion["Dentro_P10_P90"] = validacion["Real"].between(validacion["P10"], validacion["P90"])
    return resultado, validacion, sim["Total"]


def graficar(total, resultado, ruta):
    fila = resultado.set_index("Segmento").loc["Total"]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(total / 1e6, bins=60, color="#2E86AB", alpha=.8)
    for etiqueta, valor, estilo in [("P10", fila.P10, ":"), ("P50", fila.P50, "-"), ("P90", fila.P90, "--"),
                                    ("Proyección lineal", fila.Proyeccion_lineal, "-.")]:
        ax.axvline(valor / 1e6, color="k" if etiqueta != "Proyección lineal" else "#C0392B", ls=estilo,
                   label=f"{etiqueta}: {valor/1e6:,.0f} M")
    ax.set_xlabel("Presupuesto anual simulado (M COP, valores anonimizados)")
    ax.set_ylabel("Años simulados")
    ax.set_title(f"Proyección del presupuesto ({N_SIMULACIONES:,} simulaciones, IPC {C.IPC_CIERRE:.0%})")
    ax.legend()
    fig.tight_layout()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=150)
    plt.close(fig)


def ejecutar(bd=C.BD_SQLITE):
    with sqlite3.connect(bd) as con:
        resultado, validacion, total = proyectar(con)
        resultado.to_sql("proyeccion", con, if_exists="replace", index=False)
        validacion.to_sql("validacion_modelo", con, if_exists="replace", index=False)
    resultado.to_csv(C.DIR_PROCESSED / "proyeccion.csv", index=False, encoding="utf-8-sig")
    graficar(total, resultado, C.DIR_DOCS / "proyeccion_presupuesto.png")
    return resultado, validacion


if __name__ == "__main__":
    r, v = ejecutar()
    pd.set_option("display.float_format", lambda x: f"{x:,.2f}")
    print((r.set_index("Segmento")[["Proyeccion_lineal", "P10", "P50", "P90"]] / 1e6).round(1))
    print(v[["Segmento", "Dentro_P10_P90"]].to_string(index=False))
