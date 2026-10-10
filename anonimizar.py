"""Genera la versión publicable de la exportación SAP.

Se ejecuta SOLO en el equipo del autor, con el Excel real, antes de subir datos al repositorio:
  - multiplica todas las columnas monetarias por FACTOR_ANON (definido en .env)
  - reemplaza el nombre del contratista y su código de proveedor
  - reemplaza los usuarios SAP por códigos (USR001, USR002, ...)

Uso:  python anonimizar.py
Requiere en .env:  FACTOR_ANON y RUTA_EXCEL_ORIGINAL
"""
import os
import re
import sys

import pandas as pd

import config as C

COLUMNAS_MONETARIAS = {
    "ME2N": ["Precio neto", "Valor neto de pedido", "Valor pendiente", "Valor pendiente total"],
    "ME5K": ["Valor neto de pedido"],
    "MSRV5": ["Valor neto", "Precio bruto"],
    "MB51": ["Importe ML"],
}
COLUMNAS_USUARIO = {"ME2N": ["Creado por"], "ME5K": ["Solicitante"]}
COLUMNAS_TEXTO = {
    "ME2N": ["Nombre de proveedor", "Texto breve"],
    "ME5K": ["Nombre de proveedor", "Texto breve"],
    "MB51": ["Texto cab.documento", "Referencia"],
}
PATRON_CONTRATISTAS = re.compile(r"(?:\d+\s+)?(?:HESEGO(?: INGENIERIA SAS)?|PROING)", re.IGNORECASE)
CODIGO_PROVEEDOR_ANON = 999999


def anonimizar(hojas, factor):
    usuarios = sorted({u for h, cols in COLUMNAS_USUARIO.items() for c in cols
                       for u in hojas[h][c].dropna().astype(str).str.upper()})
    mapa_usuarios = {u: f"USR{i:03d}" for i, u in enumerate(usuarios, 1)}

    salida = {}
    for hoja, df in hojas.items():
        df = df.copy()
        for c in COLUMNAS_MONETARIAS.get(hoja, []):
            df[c] = (pd.to_numeric(df[c], errors="coerce") * factor).round(0)
        for c in COLUMNAS_USUARIO.get(hoja, []):
            df[c] = df[c].astype(str).str.upper().map(mapa_usuarios)
        for c in COLUMNAS_TEXTO.get(hoja, []):
            df[c] = df[c].astype("string").str.replace(PATRON_CONTRATISTAS, "CONTRATISTA", regex=True)
        for c in ("Proveedor fijo", "Proveedor"):
            if c in df.columns:
                codigos = {v: CODIGO_PROVEEDOR_ANON - i for i, v in enumerate(sorted(df[c].dropna().astype(str).unique()))}
                df[c] = df[c].astype(str).map(codigos)
        salida[hoja] = df
    return salida


def main():
    factor = os.getenv("FACTOR_ANON")
    ruta = os.getenv("RUTA_EXCEL_ORIGINAL")
    if not factor or not ruta:
        sys.exit("Defina FACTOR_ANON y RUTA_EXCEL_ORIGINAL en el archivo .env")

    ruta = C.RAIZ / ruta if not os.path.isabs(ruta) else ruta
    hojas = pd.read_excel(ruta, sheet_name=list(C.HOJAS_SAP))
    anon = anonimizar(hojas, float(factor))

    # Control: no debe quedar ningún rastro del contratista
    for hoja, df in anon.items():
        texto = df.astype(str).apply(lambda s: s.str.contains(PATRON_CONTRATISTAS)).any().any()
        assert not texto, f"Quedó el nombre del contratista en la hoja {hoja}"

    C.ARCHIVO_FUENTE.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(C.ARCHIVO_FUENTE) as w:
        for hoja, df in anon.items():
            df.to_excel(w, sheet_name=hoja, index=False)
    print(f"Archivo anonimizado: {C.ARCHIVO_FUENTE}")
    for hoja, df in anon.items():
        print(f"  {hoja:6s} {len(df):>6,} filas")


if __name__ == "__main__":
    main()
