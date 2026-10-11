"""Shared product cost calculation; never modifies input frames."""
import pandas as pd

def calculate_product_cost_and_margin(df_products: pd.DataFrame, df_bom: pd.DataFrame, df_insats: pd.DataFrame) -> pd.DataFrame:
    """Calculates cost price and profit margin for each product recursively based on BOM."""
    df_products, df_bom, df_insats = (frame.copy(deep=True) for frame in (df_products, df_bom, df_insats))
    if df_products.empty or 'Produkt_id' not in df_products.columns:
        return pd.DataFrame()

    if 'Utpris' not in df_products.columns:
        df_products['Utpris'] = 0.0

    utpris_values = pd.to_numeric(df_products['Utpris'], errors='coerce')
    df_products['Utpris'] = pd.Series(utpris_values, index=df_products.index).fillna(0.0)

    df_bom['Produkt_id'] = df_bom['Produkt_id'].astype(str)
    df_bom['SI'] = df_bom['SI'].astype(str)

    df_insats_copy = df_insats.copy()
    vikt_per_pcs = pd.to_numeric(df_insats_copy['Vikt/Pcs'], errors='coerce')
    df_insats_copy['Vikt/Pcs'] = pd.Series(vikt_per_pcs, index=df_insats_copy.index).fillna(1.0)
    pris_kr = pd.to_numeric(df_insats_copy['Pris (Kr)'], errors='coerce')
    df_insats_copy['Pris (Kr)'] = pd.Series(pris_kr, index=df_insats_copy.index).fillna(0.0)

    raw_material_price_map = {}
    for _, row in df_insats_copy.iterrows():
        si_code = str(row['Sl'])
        consumption_type = str(row.get('Typ', '')).strip().lower()
        price = row['Pris (Kr)']
        price_unit = str(row.get('Pris_Enhet', 'pkg')).strip().lower()
        weight_per_pkg = row['Vikt/Pcs']
        
        if consumption_type == 'g':
            if price_unit == 'pkg':
                raw_material_price_map[si_code] = price / weight_per_pkg if weight_per_pkg > 0 else 0
            elif price_unit == 'kg':
                raw_material_price_map[si_code] = price / 1000.0
            elif price_unit == 'g':
                raw_material_price_map[si_code] = price
            else:
                raw_material_price_map[si_code] = price / weight_per_pkg if weight_per_pkg > 0 else 0
        else:
            pieces_per_pkg = weight_per_pkg
            raw_material_price_map[si_code] = price / pieces_per_pkg if pieces_per_pkg > 0 else price

    memo = {}
    visiting = set()
    all_product_ids_in_bom = set(df_bom['Produkt_id'].unique())

    def get_cost(item_id):
        item_id = str(item_id)
        if item_id in memo:
            return memo[item_id]
        
        if item_id in visiting:
            raise ValueError("Cykel i BOM: " + item_id)
        if item_id in all_product_ids_in_bom:
            visiting.add(item_id)
            bom_for_item = df_bom[df_bom['Produkt_id'] == item_id]
            total_cost = 0
            for _, row in bom_for_item.iterrows():
                consumption = pd.to_numeric(row.get('Förbrukning'), errors='coerce')
                consumption_value = consumption if pd.notna(consumption) else 0
                total_cost += get_cost(row['SI']) * consumption_value
            visiting.remove(item_id)
            memo[item_id] = total_cost
            return total_cost
        
        if item_id in raw_material_price_map:
            return raw_material_price_map[item_id]
        
        return 0

    product_costs = {}
    for product_id in df_products['Produkt_id']:
        product_costs[product_id] = get_cost(product_id)

    df_products['Kostpris'] = df_products['Produkt_id'].map(product_costs)
    df_products['Vinstmarginal (%)'] = df_products.apply(
        lambda row: ((row['Utpris'] - row['Kostpris']) / row['Utpris']) * 100 if row['Utpris'] > 0 else 0,
        axis=1
    )
    return df_products

