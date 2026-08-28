import pandas as pd
import sys
import os

# Ensure modules are in path
sys.path.append(os.getcwd())
from modules.inventory_engine import calculate_current_stock

def test_inventory_logic():
    print("--- Testing Inventory Logic ---")
    
    # 1. Base Setup
    df_insats = pd.DataFrame([
        {'Sl': '501', 'Insatsvara': 'Flour', 'Typ': 'g', 'Vikt/Pcs': 1000, 'Antal': 10, 'Pris (Kr)': 50, 'Leverantör': 'S1'},
    ])
    
    # 2. Inbound Log
    df_inbound = pd.DataFrame([
        {'SI_Code': '501', 'Total_Base_Qty': 5000}
    ])
    
    # 3. BOM (Recipe)
    df_bom = pd.DataFrame([
        {'Produkt_id': 'P1', 'SI': '501', 'Förbrukning': 200}
    ])
    
    # 4. Production Log
    df_production = pd.DataFrame([
        {'Product_ID': 'P1', 'Quantity_Produced': 5}
    ])
    
    stock = calculate_current_stock(df_insats, df_bom, df_inbound, df_production)
    
    # Calculation: (10 * 1000) + 5000 - (5 * 200) = 10000 + 5000 - 1000 = 14000
    expected = 14000
    actual = stock.loc[stock['Sl'] == '501', 'Current_Stock'].values[0]
    
    if actual == expected:
        print(f"✅ Stock Calculation: SUCCESS (Actual: {actual})")
    else:
        print(f"❌ Stock Calculation: FAILED (Expected: {expected}, Actual: {actual})")

if __name__ == "__main__":
    test_inventory_logic()
