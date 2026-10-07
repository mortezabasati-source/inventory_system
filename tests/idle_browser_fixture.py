"""Run the real app with fabricated data and no Google Sheets reads or writes."""

import runpy
import sys
import os
from pathlib import Path

import pandas as pd
from streamlit.runtime import Runtime

# Observe disconnect on the server; browser tooling may omit close events when
# the original document is destroyed during navigation.
if not getattr(Runtime, "_idle_test_hook", False):
    _disconnect = Runtime.disconnect_session

    def observed_disconnect(self, *args, **kwargs):
        marker = os.getenv("IDLE_TEST_DISCONNECT_MARKER")
        if marker:
            with open(marker, "a") as output:
                output.write("disconnected\n")
        return _disconnect(self, *args, **kwargs)

    Runtime.disconnect_session = observed_disconnect
    Runtime._idle_test_hook = True

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules import gsheet_connector as connector

FIXTURE = {
    "Insatsvara": pd.DataFrame([{
        "Sl": "501", "Insatsvara": "Flour", "Typ": "g", "Vikt/Pcs": 1000,
        "Antal": 10, "Pris (Kr)": 50, "Leverantör": "S1",
    }]),
    "BOM": pd.DataFrame([{
        "Produkt_id": "P1", "SI": "501", "Insatsvara": "Flour",
        "Enhet": "g", "Förbrukning": 200,
    }]),
    "Products": pd.DataFrame([{
        "Produkt_id": "P1", "Produkt_namn": "Bread", "Utpris": 30,
    }]),
    "Inbound_Log": pd.DataFrame(columns=[
        "Datum", "SI_Code", "Artikel", "Package_Qty", "Total_Base_Qty", "Leverantör",
    ]),
    "Production_Log": pd.DataFrame(columns=[
        "Datum", "Product_ID", "Product_Name", "Quantity_Produced",
    ]),
    "Stickprov_Log": pd.DataFrame(columns=[
        "Datum", "SI_Code", "Artikel", "System_Stock", "Actual_Stock", "Deviation", "Note",
    ]),
}
connector.load_sheet_data = lambda name, sheet: FIXTURE[sheet].copy()
connector.append_rows_to_sheet = lambda *args: None
runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
