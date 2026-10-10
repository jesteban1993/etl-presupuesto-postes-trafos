"""EXTRACT: lee las 4 exportaciones SAP (ME2N, ME5K, MSRV5, MB51) y las deja sin modificar en data/raw."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402


def extraer(archivo=C.ARCHIVO_FUENTE):
    """Lee cada hoja de la exportación y la guarda como CSV en data/raw. Devuelve un dict de DataFrames."""
    C.DIR_RAW.mkdir(parents=True, exist_ok=True)
    hojas = pd.read_excel(archivo, sheet_name=list(C.HOJAS_SAP))
    for hoja, nombre in C.HOJAS_SAP.items():
        hojas[hoja].to_csv(C.DIR_RAW / f"{nombre}.csv", index=False, encoding="utf-8-sig")
    return {C.HOJAS_SAP[h]: df for h, df in hojas.items()}


def leer_raw():
    """Lee los CSV de data/raw con los tipos correctos (para ejecutar transform por separado)."""
    fechas = {"me2n": ["Fecha documento"], "me5k": ["Fecha de pedido"],
              "msrv5": ["Fecha documento"], "mb51": ["Fe.contabilización"]}
    return {n: pd.read_csv(C.DIR_RAW / f"{n}.csv", parse_dates=fechas[n], low_memory=False)
            for n in C.HOJAS_SAP.values()}


if __name__ == "__main__":
    for nombre, df in extraer().items():
        print(f"{nombre:6s} {df.shape[0]:>6,} filas x {df.shape[1]} columnas -> data/raw/{nombre}.csv")
