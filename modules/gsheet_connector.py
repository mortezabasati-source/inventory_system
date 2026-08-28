import pandas as pd  # type: ignore[import]
import gspread  # type: ignore[import]
import os
import json
try:
    from google.oauth2.service_account import Credentials  # type: ignore[import]
except Exception as e:  # pragma: no cover - provides clearer error when dependency missing
    raise ImportError(
        "google.oauth2.service_account could not be imported.\n"
        "Please install the required package: pip install google-auth\n"
        "Original error: {}".format(e)
    )
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Help static type checkers / language servers resolve streamlit during analysis
    import streamlit as st  # type: ignore
else:
    try:
        import streamlit as st
    except Exception:  # pragma: no cover - provide lightweight fallback for environments without streamlit
        # Minimal fallback so module can be imported (e.g., in linters or tests without streamlit installed).
        class _StubSecrets(dict):
            pass

        class _StubDecorators:
            @staticmethod
            def cache_resource(func=None):
                if func is None:
                    def _decorator(f):
                        return f
                    return _decorator
                return func

            @staticmethod
            def cache_data(ttl=None):
                def _decorator(f):
                    return f
                return _decorator

        class _StubStreamlit:
            cache_resource = _StubDecorators.cache_resource
            cache_data = _StubDecorators.cache_data
            secrets = _StubSecrets()

        st = _StubStreamlit()

# Set necessary Google API scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def get_gsheet_client():
    """Establishes a cached connection to Google Sheets using Cloud Run env vars or Streamlit secrets."""
    creds_str = os.getenv("gcp_service_account")
    
    if creds_str:
        # If running in Cloud Run where env var is set
        try:
            creds_dict = json.loads(creds_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Environment variable 'gcp_service_account' is not valid JSON: {e}")
    else:
        # Fallback for Streamlit Cloud / Local dev
        try:
            # We explicitly convert to dict to avoid StreamlitSecretNotFoundError if .toml is missing 
            # and it's accessed like a dict. But st.secrets itself might throw an error if no toml exists.
            # To be 100% safe, we only try st.secrets if we didn't find the env var.
            if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
                creds_dict = dict(st.secrets["gcp_service_account"])
            else:
                raise KeyError("gcp_service_account not found in st.secrets")
        except Exception as e:
            raise RuntimeError("Could not find 'gcp_service_account' in environment variables or st.secrets.") from e

    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client

@st.cache_data(ttl=600) # Cache data for 10 minutes
def load_sheet_data(spreadsheet_name: str, worksheet_name: str) -> pd.DataFrame:
    """Reads data from a specific worksheet, caches it, and returns it as a pandas DataFrame."""
    client = get_gsheet_client()
    sheet = client.open(spreadsheet_name).worksheet(worksheet_name)
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def append_row_to_sheet(spreadsheet_name: str, worksheet_name: str, row_data: list):
    """Appends a new row to the specified worksheet."""
    client = get_gsheet_client() # Uses the cached client
    sheet = client.open(spreadsheet_name).worksheet(worksheet_name)
    sheet.append_row(row_data)

def append_rows_to_sheet(spreadsheet_name: str, worksheet_name: str, rows_data: list[list]):
    """Appends multiple rows to the specified worksheet in a single API call."""
    client = get_gsheet_client()
    sheet = client.open(spreadsheet_name).worksheet(worksheet_name)
    sheet.append_rows(rows_data, value_input_option='USER_ENTERED') # 'USER_ENTERED' allows formulas in sheets