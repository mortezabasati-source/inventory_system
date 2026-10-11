"""Independent Sheets reader. Never imports the operational write connector."""
import json
import os
from datetime import datetime, timezone

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

READ_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
SHEETS = ("Insatsvara", "BOM", "Inbound_Log", "Production_Log", "Products", "Stickprov_Log")


def setting(name, default=None):
    value = os.getenv(name)
    if value:
        return value
    try:
        return st.secrets.get(name, default)
    except (FileNotFoundError, KeyError):
        return default


def configuration():
    """Return server-only configuration; do not display or send it to the model."""
    key = setting("GEMINI_API_KEY")
    sheet_id = setting("ANALYTICS_SPREADSHEET_ID")
    credentials = setting("analytics_gcp_service_account")
    if not key or not sheet_id or not credentials:
        raise ValueError("Konfigurera GEMINI_API_KEY, ANALYTICS_SPREADSHEET_ID och analytics_gcp_service_account (se README).")
    try:
        credentials = json.loads(credentials) if isinstance(credentials, str) else dict(credentials)
    except (ValueError, TypeError):
        raise ValueError("Ogiltig konfiguration för analyskontot. Se README.") from None
    return key, setting("GEMINI_MODEL", "gemini-3.8-flash"), sheet_id, credentials


@st.cache_data(ttl=60, max_entries=4, show_spinner=False)
def load_snapshot(sheet_id, credentials_json):
    """Cache includes credential identity; no fallback to the read/write account."""
    credentials = Credentials.from_service_account_info(json.loads(credentials_json), scopes=[READ_SCOPE])
    book = gspread.authorize(credentials).open_by_key(sheet_id)
    frames = {name: pd.DataFrame(book.worksheet(name).get_all_records()) for name in SHEETS}
    return {"frames": frames, "fetched_at": datetime.now(timezone.utc).isoformat()}
