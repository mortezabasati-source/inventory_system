# 📦 SmartLager - Inventory & Production Management System

SmartLager is a web-based inventory and production management system built with Python, Streamlit, and Google Sheets. It provides a user-friendly interface for small to medium-sized businesses to track raw material stock, register inbound deliveries, and log daily production, with automatic stock deduction based on a Bill of Materials (BOM).

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
