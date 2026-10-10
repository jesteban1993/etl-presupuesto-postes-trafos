"""LOAD: carga las tablas procesadas en una base SQLite con esquema definido (modo reemplazo)."""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

ESQUEMA = """
DROP VIEW  IF EXISTS v_base_modelo;
DROP VIEW  IF EXISTS v_resumen_mensual;
DROP TABLE IF EXISTS costos_solped;
DROP TABLE IF EXISTS detalle_servicios;
DROP TABLE IF EXISTS completitud_mes;
DROP TABLE IF EXISTS validaciones;

CREATE TABLE costos_solped (
    Solped              INTEGER PRIMARY KEY,
    OM                  TEXT    NOT NULL,
    Pedido              INTEGER NOT NULL,
    Contrato_marco      INTEGER,
    Centro              INTEGER NOT NULL,
    TIPO                TEXT    NOT NULL CHECK (TIPO IN ('Poste', 'TD')),
    Fecha_solped        DATE    NOT NULL,
    Fecha_pedido        DATE,
    Anio                INTEGER NOT NULL,
    Mes                 INTEGER NOT NULL CHECK (Mes BETWEEN 1 AND 12),
    Rezago_dias         INTEGER,
    n_servicios         INTEGER,
    n_poste             INTEGER,
    n_trafo             INTEGER,
    Cantidad_servicios  REAL,
    Valor_neto_solped   REAL,
    Valor_Servicio      REAL    NOT NULL,
    Material_OM_total   REAL,
    n_solped_OM         INTEGER,
    Valor_Material      REAL    NOT NULL,
    Valor_Total         REAL    NOT NULL,
    Costo_unitario      REAL,
    Completitud         REAL,
    Mes_maduro          INTEGER NOT NULL
);

CREATE TABLE detalle_servicios (
    Solped               INTEGER NOT NULL REFERENCES costos_solped (Solped),
    Posicion             INTEGER NOT NULL,
    Centro               INTEGER,
    Fecha_solped         DATE,
    Codigo_servicio      INTEGER NOT NULL,
    Descripcion_servicio TEXT,
    Categoria            TEXT    NOT NULL,
    Cantidad             REAL,
    Unidad               TEXT,
    Precio_bruto         REAL,
    Valor_neto_linea     REAL,
    PRIMARY KEY (Solped, Posicion, Codigo_servicio)
);

CREATE TABLE completitud_mes (
    Anio        INTEGER NOT NULL,
    Mes         INTEGER NOT NULL,
    Completitud REAL    NOT NULL,
    Mes_maduro  INTEGER NOT NULL,
    PRIMARY KEY (Anio, Mes)
);

CREATE TABLE validaciones (
    Verificacion TEXT PRIMARY KEY,
    Antes        INTEGER,
    Despues      INTEGER,
    Nota         TEXT
);

CREATE VIEW v_base_modelo AS
    SELECT * FROM costos_solped WHERE Mes_maduro = 1;

CREATE VIEW v_resumen_mensual AS
    SELECT Anio, Mes, TIPO, Centro,
           COUNT(*)            AS Solped,
           SUM(Valor_Servicio) AS Valor_Servicio,
           SUM(Valor_Material) AS Valor_Material,
           SUM(Valor_Total)    AS Valor_Total,
           MAX(Mes_maduro)     AS Mes_maduro
    FROM costos_solped
    GROUP BY Anio, Mes, TIPO, Centro;
"""


def _fechas_a_texto(df):
    df = df.copy()
    for c in df.select_dtypes(include="datetime").columns:
        df[c] = df[c].dt.strftime("%Y-%m-%d")
    return df


def cargar(tablas, bd=C.BD_SQLITE):
    bd.parent.mkdir(parents=True, exist_ok=True)
    det = tablas["detalle_servicios"].rename(columns={"Posición": "Posicion"})
    det = det[["Solped", "Posicion", "Centro", "Fecha_solped", "Codigo_servicio", "Descripcion_servicio",
               "Categoria", "Cantidad", "Unidad", "Precio_bruto", "Valor_neto_linea"]]
    datos = {"costos_solped": tablas["costos_solped"], "detalle_servicios": det,
             "completitud_mes": tablas["completitud_mes"], "validaciones": tablas["validaciones"]}
    with sqlite3.connect(bd) as con:
        con.executescript(ESQUEMA)
        for nombre, df in datos.items():
            _fechas_a_texto(df).to_sql(nombre, con, if_exists="append", index=False)
        conteos = {n: con.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for n in datos}
    return conteos


if __name__ == "__main__":
    tablas = {n: pd.read_csv(C.DIR_PROCESSED / f"{n}.csv", parse_dates=["Fecha_solped", "Fecha_pedido"]
                             if n == "costos_solped" else (["Fecha_solped"] if n == "detalle_servicios" else None))
              for n in ["costos_solped", "detalle_servicios", "completitud_mes", "validaciones"]}
    print(cargar(tablas))
