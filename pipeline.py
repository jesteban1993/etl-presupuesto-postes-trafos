"""Orquesta la ejecución completa: extract -> transform -> load -> modelo de proyección."""
import time

import config as C
from extract.extract import extraer
from transform.transform import transformar, guardar
from load.load import cargar
from model.proyeccion import ejecutar as proyectar


def main():
    t0 = time.time()
    print("[1/4] Extract   ->", C.ARCHIVO_FUENTE.name)
    raw = extraer()
    for n, df in raw.items():
        print(f"      {n:6s} {len(df):>6,} filas -> data/raw/{n}.csv")

    print("[2/4] Transform -> reglas T0–T7")
    tablas = transformar(raw)
    guardar(tablas)
    print(tablas["validaciones"].to_string(index=False))

    print("[3/4] Load      ->", C.BD_SQLITE.relative_to(C.RAIZ))
    for tabla, n in cargar(tablas).items():
        print(f"      {tabla:18s} {n:>5,} filas")

    base = tablas["costos_solped"]
    base = base[base["Mes_maduro"]]
    print(f"      Base del modelo: {len(base)} solped | Valor total: {base['Valor_Total'].sum()/1e6:,.1f} M COP")

    print(f"[4/4] Modelo    -> proyección del presupuesto (IPC {C.IPC_CIERRE:.0%})")
    resultado, validacion = proyectar()
    tabla = resultado.set_index("Segmento")[["Proyeccion_lineal", "P10", "P50", "P90"]] / 1e6
    print(tabla.round(1).to_string())
    print(f"      Prueba del supuesto (ene-abr -> may-jun): {validacion['Dentro_P10_P90'].sum()} de "
          f"{len(validacion)} segmentos dentro de [P10, P90].")
    print("      Si es 0: los meses no son intercambiables (estacionalidad por temporada de lluvias);"
          " la proyección asume que el 2.º semestre repite el ciclo del 1.º. Ver README, sección 12.")
    print(f"Tiempo total: {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
