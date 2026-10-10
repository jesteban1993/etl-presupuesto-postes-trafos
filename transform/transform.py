"""TRANSFORM: limpieza, integración y variables derivadas (reglas T1–T7 de la Entrega 2).

Resultado principal: tabla de costos con UNA fila por solped.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as C  # noqa: E402

COLS_MSRV5 = ["Número de documento", "Centro", "Fecha documento", "Valor neto", "Posición",
              "Número de servicio", "Cantidad", "Unidad medida base", "Precio bruto", "Texto breve"]


def om_texto(serie):
    """Normaliza la OM a texto sin decimales ('' si está vacía)."""
    return pd.to_numeric(serie, errors="coerce").astype("Int64").astype(str).replace("<NA>", "")


# T1 -----------------------------------------------------------------------------
def solped_validas(me5k):
    """Una fila por solped con OM válida (inicia por '400')."""
    k = me5k.assign(OM=om_texto(me5k["Orden"]))
    k = k[k["OM"].str.startswith(C.PREFIJO_OM_VALIDA)]
    return (k.groupby("Solicitud de pedido")
              .agg(OM=("OM", "first"), Pedido=("Pedido", "first"), n_pedidos=("Pedido", "nunique"),
                   Contrato_marco=("Contrato marco", "first"), Fecha_pedido=("Fecha de pedido", "min"),
                   Valor_neto_solped=("Valor neto de pedido", "sum"))
              .reset_index().rename(columns={"Solicitud de pedido": "Solped"}))


# T0 -----------------------------------------------------------------------------
LLAVE_LINEA = ["Número de documento", "Posición", "Número de servicio"]


def deduplicar_msrv5(msrv5):
    """Una línea por (solped, posición, servicio). Si la línea viene repetida en la exportación,
    se conserva la de mayor valor neto (las repetidas son copias o registros con valor residual)."""
    return (msrv5.sort_values("Valor neto", ascending=False)
                 .drop_duplicates(LLAVE_LINEA, keep="first")
                 .sort_index())


# T2 -----------------------------------------------------------------------------
def detalle_servicios(msrv5):
    """Una fila por línea de servicio, con su categoría Poste/Trafo."""
    d = msrv5[COLS_MSRV5].rename(columns={
        "Número de documento": "Solped", "Fecha documento": "Fecha_solped", "Valor neto": "Valor_neto_linea",
        "Número de servicio": "Codigo_servicio", "Texto breve": "Descripcion_servicio",
        "Unidad medida base": "Unidad", "Precio bruto": "Precio_bruto"})
    d["Categoria"] = d["Codigo_servicio"].map(C.MAPA_SERVICIOS)
    return d


# T5 -----------------------------------------------------------------------------
def material_por_om(mb51):
    """Material imputado a la OM = -(261 + 262), sin filtro de fecha."""
    m = mb51[pd.to_numeric(mb51["Clase de movimiento"], errors="coerce").isin([C.MOV_SALIDA, C.MOV_RETORNO])]
    return (-m.groupby(om_texto(m["Orden"]))["Importe ML"].sum()).rename("Material_OM_total")


# T7 -----------------------------------------------------------------------------
def completitud_mensual(t):
    """% esperado de solped de cada mes ya facturadas al corte, según el rezago observado."""
    corte = pd.Timestamp(C.FECHA_CORTE)
    ref = t[t["Fecha_solped"].between(*C.VENTANA_REF_REZAGO)]["Rezago_dias"]
    filas = []
    for mes in range(1, corte.month + 1):
        inicio = pd.Timestamp(f"{C.ANIO}-{mes:02d}-01")
        dias = pd.date_range(inicio, periods=inicio.days_in_month)
        comp = float(np.mean([(ref <= (corte - d).days).mean() for d in dias]))
        filas.append({"Anio": C.ANIO, "Mes": mes, "Completitud": comp, "Mes_maduro": comp >= C.UMBRAL_COMPLETITUD})
    return pd.DataFrame(filas)


def transformar(raw):
    """Aplica T1–T7. Devuelve dict con las tablas procesadas."""
    me5k, msrv5_crudo, mb51 = raw["me5k"], raw["msrv5"], raw["mb51"]
    msrv5 = deduplicar_msrv5(msrv5_crudo)                           # T0
    sp = solped_validas(me5k)                                       # T1
    det = detalle_servicios(msrv5)                                  # T2
    solped_sin_om = sorted(set(det["Solped"]) - set(sp["Solped"]))
    det = det[det["Solped"].isin(sp["Solped"])]

    t = (det.groupby("Solped")                                      # T3: una fila por solped
            .agg(Centro=("Centro", "first"), Fecha_solped=("Fecha_solped", "min"),
                 n_servicios=("Categoria", "size"),
                 n_poste=("Categoria", lambda x: int((x == "Poste").sum())),
                 n_trafo=("Categoria", lambda x: int((x == "Trafo").sum())),
                 Cantidad_servicios=("Cantidad", "sum"))
            .reset_index().merge(sp, on="Solped", how="left"))
    t["TIPO"] = np.where(t["n_trafo"] > 0, "TD", "Poste")
    t["Valor_Servicio"] = t["Valor_neto_solped"] * C.IVA            # T4

    t = t.merge(material_por_om(mb51), left_on="OM", right_index=True, how="left")   # T5
    sin_material = t[t["Material_OM_total"].isna()]
    t = t[t["Material_OM_total"].notna()].copy()                    # T5b: material pagado con otras OM

    t["n_solped_OM"] = t.groupby("OM")["Solped"].transform("size")  # T6: reparto en OM compartidas
    t["Valor_Material"] = t["Material_OM_total"] * t["Valor_Servicio"] / t.groupby("OM")["Valor_Servicio"].transform("sum")
    t["Valor_Total"] = t["Valor_Servicio"] + t["Valor_Material"]
    t["Costo_unitario"] = t["Valor_Total"] / t["Cantidad_servicios"]

    t["Anio"], t["Mes"] = t["Fecha_solped"].dt.year, t["Fecha_solped"].dt.month   # T7
    t["Rezago_dias"] = (t["Fecha_pedido"] - t["Fecha_solped"]).dt.days
    t = t[t["Anio"] == C.ANIO].copy()
    comp = completitud_mensual(t)
    t = t.merge(comp[["Mes", "Completitud", "Mes_maduro"]], on="Mes", how="left")

    det = det[det["Solped"].isin(t["Solped"])]
    sin_material = sin_material[sin_material["Fecha_solped"].dt.year == C.ANIO]

    validaciones = pd.DataFrame([
        ("Líneas de servicio MSRV5 (crudo)", len(msrv5_crudo), len(det), "Líneas que quedan en el detalle 2026"),
        ("Líneas MSRV5 repetidas (T0)", int(msrv5_crudo.duplicated(LLAVE_LINEA).sum()), 0, "Se conserva una por solped-posición-servicio"),
        ("Solped MSRV5 (crudo)", msrv5_crudo["Número de documento"].nunique(), len(t), "Una fila por solped en la tabla final"),
        ("Solped duplicadas en la tabla final", None, int(t["Solped"].duplicated().sum()), "Debe ser 0"),
        ("Solped sin OM válida (T1)", len(solped_sin_om), 0, "Excluidas"),
        ("Solped sin material en MB51 (T5b)", len(sin_material), 0, "Excluidas: material pagado con otras OM"),
        ("OM compartidas por varias solped (T6)", int(t.loc[t["n_solped_OM"] > 1, "OM"].nunique()), None, "Material repartido"),
        ("Solped con más de un pedido", int((sp["n_pedidos"] > 1).sum()), int((t["n_pedidos"] > 1).sum()), "Control"),
        ("Servicios fuera de los 19 códigos", int(det["Categoria"].isna().sum()), 0, "Control"),
        ("Nulos en columnas clave (Solped, OM, TIPO, Valor_Total)", None,
         int(t[["Solped", "OM", "TIPO", "Valor_Total"]].isna().sum().sum()), "Debe ser 0"),
        ("Solped en meses maduros (base del modelo)", None, int(t["Mes_maduro"].sum()), f"Completitud >= {C.UMBRAL_COMPLETITUD:.0%}"),
    ], columns=["Verificacion", "Antes", "Despues", "Nota"]).astype({"Antes": "Int64", "Despues": "Int64"})

    columnas = ["Solped", "OM", "Pedido", "Contrato_marco", "Centro", "TIPO", "Fecha_solped", "Fecha_pedido",
                "Anio", "Mes", "Rezago_dias", "n_servicios", "n_poste", "n_trafo", "Cantidad_servicios",
                "Valor_neto_solped", "Valor_Servicio", "Material_OM_total", "n_solped_OM", "Valor_Material",
                "Valor_Total", "Costo_unitario", "Completitud", "Mes_maduro"]
    return {"costos_solped": t[columnas], "detalle_servicios": det, "completitud_mes": comp,
            "validaciones": validaciones}


def guardar(tablas):
    C.DIR_PROCESSED.mkdir(parents=True, exist_ok=True)
    for nombre, df in tablas.items():
        df.to_csv(C.DIR_PROCESSED / f"{nombre}.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    from extract.extract import leer_raw
    tablas = transformar(leer_raw())
    guardar(tablas)
    print(tablas["validaciones"].to_string(index=False))
