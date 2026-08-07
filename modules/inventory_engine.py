import pandas as pd  # type: ignore[import]

def calculate_current_stock(df_insats: pd.DataFrame, df_bom: pd.DataFrame, 
                            df_inbound: pd.DataFrame, df_production: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates the current stock level for each item.

    The calculation is:
    Current Stock = Initial Stock + Total Inbound - Total Consumed

    """
    # 1. Prepare base items dataframe
    if df_insats.empty:
        return pd.DataFrame(columns=['Sl', 'Insatsvara', 'Typ', 'Initial_Base_Stock', 'Total_Inbound', 'Total_Consumed', 'Current_Stock'])
        
    stock_df = df_insats[['Sl', 'Insatsvara', 'Typ', 'Vikt/Pcs', 'Leverantör', 'Antal']].copy()
    stock_df['Sl'] = stock_df['Sl'].astype(str)
    
    # Calculate Initial Base Stock (Opening Balance)
    # Antal = initial quantity of packages/units, Vikt/Pcs = base unit weight per package
    stock_df['Antal'] = pd.to_numeric(stock_df['Antal'], errors='coerce').fillna(0)
    stock_df['Vikt/Pcs'] = pd.to_numeric(stock_df['Vikt/Pcs'], errors='coerce').fillna(1)
    stock_df['Initial_Base_Stock'] = stock_df['Antal'] * stock_df['Vikt/Pcs']

    # 2. Calculate Total Inbound Stock
    if not df_inbound.empty and 'SI_Code' in df_inbound.columns and 'Total_Base_Qty' in df_inbound.columns:
        df_inbound['SI_Code'] = df_inbound['SI_Code'].astype(str)
        # Ensure we operate on a Series (avoid static-analysis issue where to_numeric may return a scalar)
        df_inbound['Total_Base_Qty'] = pd.to_numeric(df_inbound['Total_Base_Qty'], errors='coerce')
        df_inbound['Total_Base_Qty'] = df_inbound['Total_Base_Qty'].fillna(0)
        inbound_sum = df_inbound.groupby('SI_Code')['Total_Base_Qty'].sum().reset_index()
        inbound_sum.columns = ['Sl', 'Total_Inbound']
    else:
        inbound_sum = pd.DataFrame(columns=['Sl', 'Total_Inbound'])
        
    stock_df = pd.merge(stock_df, inbound_sum, on='Sl', how='left')
    stock_df['Total_Inbound'] = stock_df['Total_Inbound'].fillna(0)
    
    # 3. Calculate Total Consumed Stock (from production logs and BOM)
    if not df_production.empty and not df_bom.empty and 'Product_ID' in df_production.columns and 'Quantity_Produced' in df_production.columns:
        df_production['Product_ID'] = df_production['Product_ID'].astype(str)
        df_production['Quantity_Produced'] = pd.Series(
            pd.to_numeric(df_production['Quantity_Produced'], errors='coerce'),
            index=df_production.index,
        ).fillna(0)
        
        df_bom['Produkt_id'] = df_bom['Produkt_id'].astype(str)
        df_bom['SI'] = df_bom['SI'].astype(str)
        df_bom['Förbrukning'] = pd.to_numeric(df_bom['Förbrukning'], errors='coerce')
        df_bom['Förbrukning'] = df_bom['Förbrukning'].fillna(0)
        
        # Merge production logs with BOM recipe
        merged_prod = pd.merge(df_production, df_bom, left_on='Product_ID', right_on='Produkt_id')
        if not merged_prod.empty:
            merged_prod['Consumed_Qty'] = merged_prod['Quantity_Produced'] * merged_prod['Förbrukning']
            consumed_sum = merged_prod.groupby('SI')['Consumed_Qty'].sum().reset_index()
            consumed_sum.columns = ['Sl', 'Total_Consumed']
        else:
            consumed_sum = pd.DataFrame(columns=['Sl', 'Total_Consumed'])
    else:
        consumed_sum = pd.DataFrame(columns=['Sl', 'Total_Consumed'])
        
    stock_df = pd.merge(stock_df, consumed_sum, on='Sl', how='left')
    stock_df['Total_Consumed'] = stock_df['Total_Consumed'].fillna(0)
    
    # 4. Compute Net Stock Level
    stock_df['Current_Stock'] = stock_df['Initial_Base_Stock'] + stock_df['Total_Inbound'] - stock_df['Total_Consumed']
    
    return stock_df