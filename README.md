# 📦 SmartLager - Inventory & Production Management System

SmartLager is a web-based inventory and production management system built with Python, Streamlit, and Google Sheets. It provides a user-friendly interface for small to medium-sized businesses to track raw material stock, register inbound deliveries, and log daily production, with automatic stock deduction based on a Bill of Materials (BOM).

## Read-only AI analysis (desktop)

The **AI-analys** page answers inventory, inbound delivery, production, consumption,
stock deviation and calculated margin questions using Gemini. It is available to
everyone who can open the app, including access to prices and margins. Mobile
continues to show the inbound registration page only.

### Server setup

1. Enable the **Google Sheets API** in your Google Cloud project. Create a **new,
   dedicated service account** for analytics and obtain its JSON key. Do not reuse
   the application's operational account or give this account write permissions.
2. Share the existing `Inventory_System_DB` spreadsheet with the new account's
   `client_email`, selecting **Viewer**. Check that it does not inherit Editor
   access through a group, shared drive or another sharing rule. Google Cloud IAM
   roles alone do not give Viewer access to this spreadsheet.
3. Copy the spreadsheet ID from the part between `/d/` and `/edit` in its URL.
4. Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/).
   Install `requirements.txt`. Configure these values on the **server** in your
   ignored `.streamlit/secrets.toml` file:

```toml
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
GEMINI_MODEL = "gemini-3.8-flash"
ANALYTICS_SPREADSHEET_ID = "YOUR_SPREADSHEET_ID"

[analytics_gcp_service_account]
type = "service_account"
project_id = "YOUR_PROJECT_ID"
private_key_id = "YOUR_KEY_ID"
private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n"
client_email = "analytics-reader@YOUR_PROJECT_ID.iam.gserviceaccount.com"
client_id = "YOUR_CLIENT_ID"
token_uri = "https://oauth2.googleapis.com/token"
```

Use the actual fields from the downloaded service account JSON. Retain the
existing operational account settings for the app's registration forms. Never
commit either key file. On Cloud Run, supply `GEMINI_API_KEY`, `GEMINI_MODEL`,
`ANALYTICS_SPREADSHEET_ID` and `analytics_gcp_service_account` as environment
variables backed by Secret Manager; the last variable must contain the service
account JSON object. Environment values take precedence over Streamlit secrets.

The independent reader opens only the configured spreadsheet ID and the six
existing worksheets (`Insatsvara`, `BOM`, `Inbound_Log`, `Production_Log`,
`Products`, `Stickprov_Log`). It uses `spreadsheets.readonly`, with no Drive scope,
and never falls back to operational credentials. Missing configuration disables
chat. The Viewer role must be configured externally; the app cannot verify
inherited sharing permissions. Registration forms retain their existing writer.

### Analysis behavior and limits

- Gemini receives the question, the latest ten conversation turns and necessary
  tool results, rather than the entire workbook. Questions and analysis results
  leave the application and are processed by Google. Review the current
  [Gemini terms](https://ai.google.dev/gemini-api/terms) for your account and region.
- The default model is configurable. Free-tier availability and quotas depend on
  Google's current offerings and account configuration. This app cannot enforce
  free billing; it neither activates billing nor automatically changes models.
  See [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).
- Only six deterministic tools are available. Arguments are validated by the
  server. There is no arbitrary Python/SQL execution, browsing, file access or
  write tool. Cell contents are treated as data, not instructions.
- Each question uses one snapshot, independently cached for 60 seconds. **Hämta
  senaste data** invalidates that cached snapshot for the next question. Previous
  answers keep their original evidence and UTC fetch time.
- Each question allows at most five model requests, eight tool executions and
  4,000 input characters. The last model request is reserved for a summary with
  function calling disabled. Repeated identical tool requests reuse the result
  from the same snapshot and trigger summarization. If the model still requests
  tools during summarization, collected evidence is retained with a limitation
  notice. These application limits apply to both free and paid API accounts.
  Each tool returns at most 100 rows and reports
  truncation. Stock is sorted by increasing stock and margins by increasing
  margin before limiting; other results use ascending group keys. Questions
  needing omitted rows must be narrowed. Quantities remain separated by unit.
- Computations use current BOM and prices. Stock and consumption preserve the
  existing app's direct BOM calculation; margin costing supports nested BOM.
  There is no historical BOM/price versioning, historical stock reconstruction,
  actual sales profit or stock-out forecast. Empty results and invalid required
  data are reported explicitly. Monetary amounts are SEK.
- Empty `Antal` cells in `Insatsvara` mean zero opening balance, matching the
  existing stock page. Empty `Förbrukning` cells in BOM use zero consumption,
  also matching the existing calculation; these recipe parts have no quantity
  specified. Analysis explicitly reports each default and the affected count,
  and applies it only in memory. Nonempty invalid numbers remain errors; no
  source cells are modified.
- Margin validation allows unknown or empty material references only when their
  BOM consumption is exactly zero (including the documented empty-cell default).
  These rows have zero cost contribution and are explicitly reported. Unknown
  references with nonzero consumption still block costing; missing costs are
  never assumed to be zero for a consumed material. Identifier whitespace is
  trimmed on analysis copies only. Nonpositive package sizes block margin
  calculation only for materials referenced with nonzero BOM consumption;
  unused material records do not invalidate the calculation.
- History is limited to ten turns in the current Streamlit session and disappears
  on session expiry, including idle disconnection. **Rensa konversation** clears
  it immediately. It is not written to Sheets or another database.
- API requests have a 30-second timeout, with automatic retries disabled. Key,
  quota and network failures show sanitized messages without upstream details.

### Verification

Run offline regression tests with:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

The analytics tests mock Sheets and Gemini, exercise calculations and tool limits,
and verify the read-only scope, session isolation, cache refresh and desktop/mobile
navigation. Existing browser idle-disconnection checks remain available below.

After configuring the server, open **AI-analys** on desktop and ask for production
in a known period. Compare the evidence table with `Production_Log`, check its
source and timestamp, refresh data and try a request to edit stock: the assistant
must not perform any edit. Verify registration pages and mobile navigation. Do
not test writes against live data. Deploy only after the dedicated Viewer account
and secrets are configured.

---

## ✨ Features

- **Real-Time Stock Overview**: View current inventory levels for all raw materials and finished products.
- **Inbound Stock Registration**: Log incoming deliveries of raw materials.
- **Production Logging**: Register the quantity of finished goods produced each day.
- **Automatic Stock Deduction**: Inventory of raw materials is automatically consumed based on the Bill of Materials (BOM) when production is logged.
- **Batch Processing**: Use a session basket to add multiple inbound or production records before submitting them all in a single, efficient API call.
- **Data-Driven**: All data (items, products, BOM, logs) is stored and managed in a Google Sheet, making it easy to view and edit.

## 🏛️ Architecture & Data Flow

### Idle browser sessions on Cloud Run

After 30 minutes without mouse, touch, keyboard, or scroll activity, SmartLager
navigates to a local browser page and unloads the app, closing its WebSocket.
The **Anslut igen** link opens a fresh session and reloads data from Google Sheets.
The local pause page makes no requests to Cloud Run.

Automatic disconnection is paused while a basket, BOM draft, product information,
or an edited, unsubmitted form contains unsaved changes. Save or clear these
changes to allow disconnection. This intentionally keeps the connection active
when disconnecting could lose work. Inactivity detection runs entirely in the
browser, without server polling. Background browser throttling can delay the
disconnection; elapsed time is checked again when the tab becomes visible.

Set the Cloud Run environment variable `IDLE_TIMEOUT_MINUTES` to change the
timeout (default `30`, `0` disables it). Invalid values fall back to 30 minutes.
The guard uses Streamlit custom components v2 and requires Streamlit 1.51 or newer.
Include `modules/idle_session.js` when packaging the application.

For deployment verification, temporarily set the timeout to `1`, open a clean
session, and leave it untouched. Confirm navigation to the pause page and closure
of the WebSocket in browser developer tools. Check reconnection, preservation of
the `?mobile=true` query parameter, and that unsaved baskets/forms prevent timeout.
Compare Cloud Run billable CPU allocation time before and after deployment.

Regression checks: `python -m unittest discover -s tests -p 'test_idle_timeout.py'`.
For the browser checks, install Playwright as a development tool and follow the
instructions in `tests/test_idle_session_browser.py`. The fixture runs the actual
app with fabricated data and disables all Google Sheets reads and writes.

The system operates on a simple but powerful data flow:

1.  **Initial Stock**: The starting quantity for each item is defined in the `Insatsvara` sheet.
2.  **Inbound Log**: New deliveries are added to the `Inbound_Log` sheet, increasing the stock.
3.  **Production Log**: When finished goods are produced, an entry is made in the `Production_Log`.
4.  **BOM Consumption**: The system uses the `BOM` sheet to determine which raw materials and in what quantities are needed for the produced goods.
5.  **Stock Calculation**: The final stock is calculated as: `Initial Stock + Total Inbound - Total Consumed`.

## 📁 Directory Structure

```text
inventory_system/
│
├── .streamlit/
│   └── secrets.toml          # Secure credentials for Google Sheets API connection.
│
├── modules/
│   ├── __init__.py
│   ├── gsheet_connector.py   # Module for connecting to and interacting with Google Sheets.
│   └── inventory_engine.py   # Core logic for calculating stock levels.
│
├── app.py                    # Main application file containing the Streamlit UI.
├── requirements.txt          # List of Python dependencies.
└── README.md                 # This documentation file.
