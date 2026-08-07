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