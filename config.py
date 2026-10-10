"""Configuración central del pipeline: rutas, reglas de negocio y parámetros."""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")

# --- Rutas -------------------------------------------------------------------
DIR_DATA = RAIZ / "data"
ARCHIVO_FUENTE = DIR_DATA / "source" / "Postes_Trafos_anon.xlsx"  # exportación SAP anonimizada
DIR_RAW = DIR_DATA / "raw"
DIR_PROCESSED = DIR_DATA / "processed"
BD_SQLITE = DIR_PROCESSED / "costos_mantenimiento.db"
DIR_DOCS = RAIZ / "docs"

# Hojas de la exportación SAP -> nombre del archivo raw
HOJAS_SAP = {"ME2N": "me2n", "ME5K": "me5k", "MSRV5": "msrv5", "MB51": "mb51"}

# --- Reglas de negocio --------------------------------------------------------
PREFIJO_OM_VALIDA = "400"   # T1: OM válidas en ME5K
IVA = 1.19                  # T4: valor neto ME5K x IVA
MOV_SALIDA, MOV_RETORNO = 261, 262

# T2: código de servicio -> categoría (19 códigos filtro de MSRV5)
MAPA_SERVICIOS = {
    90000445: "Poste", 90000446: "Poste", 90000507: "Poste", 90000553: "Poste",
    90000591: "Poste", 90004718: "Poste", 90004723: "Poste", 90005705: "Poste",
    90005669: "Poste", 90005670: "Poste", 90005703: "Poste", 90005704: "Poste",
    90000469: "Trafo", 90005624: "Trafo", 90005625: "Trafo", 90005723: "Trafo",
    90005724: "Trafo", 90005725: "Trafo", 90005726: "Trafo",
}

# --- Ventana temporal y madurez (T7) -----------------------------------------
ANIO = 2026
FECHA_CORTE = "2026-08-31"                         # último pedido extraído
VENTANA_REF_REZAGO = ("2026-01-01", "2026-03-31")  # solped con rezago observable
UMBRAL_COMPLETITUD = 0.90

# --- Parámetros del modelo ------------------------------------------------------
IPC_CIERRE = float(os.getenv("IPC_CIERRE", "0.07"))  # estimado de cierre del IPC (7 %)
