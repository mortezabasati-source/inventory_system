import sys
import os
from datetime import date
import pandas as pd  # type: ignore
import streamlit as st  # type: ignore
from builtins import Exception

# Ensure imports reference the local modules package to satisfy linters
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
from modules.inventory_engine import calculate_current_stock
from modules.gsheet_connector import load_sheet_data, append_rows_to_sheet

SPREADSHEET_NAME = "Inventory_System_DB"

# --- Page Configuration ---
st.set_page_config(
    page_title="SmartLager",
    page_icon="logo.png",
    layout="wide"
)

# --- Custom Meta Tags for PWA ---
st.markdown("""
<meta name="apple-mobile-web-app-title" content="SmartLager">
<meta name="application-name" content="SmartLager">
<link rel="apple-touch-icon" href="logo.png">
""", unsafe_allow_html=True)

st.title("📦 SmartLager")
st.caption("Intelligent lager- och produktionshantering")

# --- Global Custom CSS Injection (Eataway Theme & 3D Keyboard Tabs) ---
st.markdown("""
<style>
    /* Card Container Styling */
    .smartlager-card {
        background-color: #FFFFFF;
        border: 1px solid #E1E8E1;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    }

    /* Primary Action Buttons */
    .stButton > button[kind="primary"] {
        background-color: #1E5631 !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 700 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #2E7D32 !important;
        color: #FFFFFF !important;
    }
    
    /* Summary Metric Cards */
    [data-testid="stMetric"] {
        background-color: #F4F7F4;
        border: 1px solid #E1E8E1;
        border-radius: 12px;
        padding: 15px;
    }
    [data-testid="stMetricLabel"] {
        color: #1E5631;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

def load_all_data():
    """Loads all necessary data from Google Sheets, with individual error handling."""
    data_sheets = {
        "df_insats": "Insatsvara",
        "df_bom": "BOM",
        "df_inbound": "Inbound_Log",
        "df_production": "Production_Log",
        "df_products": "Products"
    }
    loaded_data = {}
    for df_name, sheet_name in data_sheets.items():
        try:
            loaded_data[df_name] = load_sheet_data(SPREADSHEET_NAME, sheet_name)
        except Exception as e:
            st.error(f"Kunde inte ladda '{sheet_name}' från Google Sheets: {e}")
            st.stop()
    return loaded_data

data = load_all_data()
# Initialize session state for batch processing baskets
if 'inbound_basket' not in st.session_state:
    st.session_state['inbound_basket'] = []
if 'production_basket' not in st.session_state:
    st.session_state['production_basket'] = []

# --- Main Navigation using Selectbox ---
nav_options = [
    "📥 Registrera Inleverans", 
    "🏭 Registrera Daglig Produktion", 
    "📊 Aktuellt Lagersaldo"
]

selected_page = st.selectbox("Välj en åtgärd:", nav_options)
st.markdown("---")

# ------------------- Page 1: Register Inbound -------------------
if selected_page == "📥 Registrera Inleverans":
    st.header("Registrera Inleverans av Varor")
    st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
    
    with st.form("inbound_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            entry_date = st.date_input("Inleveransdatum", date.today())
        
        def create_inbound_label(row):
            label = f"{row['Sl']} - {row['Insatsvara']} ({row['Typ']}"
            weight = row.get('Vikt/Pcs')
            if weight and pd.notna(weight) and str(weight).strip():
                label += f" - {weight}g"
            label += ")"
            return label

        with col2:
            item_options = {create_inbound_label(row): row for _, row in data['df_insats'].iterrows()}
            selected_item_str = st.selectbox("Välj artikel / SI-kod", options=list(item_options.keys()))
            selected_item = item_options[selected_item_str]
        
        with col3:
            pkg_qty = st.number_input("Antal förpackningar", min_value=1.0, step=1.0)
        
        st.markdown("---")
        col_submit1, col_submit2 = st.columns([3, 1])
        with col_submit1:
            try:
                # Safely get 'Vikt/Pcs', defaulting to 1.0 if missing, empty, or non-numeric
                vikt_pcs = float(selected_item.get('Vikt/Pcs') or 1.0)
            except (ValueError, TypeError):
                vikt_pcs = 1.0
            total_base = pkg_qty * vikt_pcs
            st.info(f"Total basmängd som läggs till: **{total_base:,.2f}g**")
        
        with col_submit2:
            if st.form_submit_button("➕ Lägg till i listan", use_container_width=True, type="primary"):
                new_row = [str(entry_date), str(selected_item['Sl']), selected_item['Insatsvara'], pkg_qty, total_base]
                st.session_state.inbound_basket.append(new_row)
                st.success(f"✔️ Lade till '{selected_item['Insatsvara']}' i listan.")
                st.rerun()
                
    st.markdown('</div>', unsafe_allow_html=True)

    # Display Basket Preview Table
    if st.session_state.inbound_basket:
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        st.subheader("Poster att spara")
        
        header_cols = st.columns([2, 2, 4, 1, 2, 1])
        header_cols[0].write("**Datum**")
        header_cols[1].write("**SI-kod**")
        header_cols[2].write("**Artikel**")
        header_cols[3].write("**Antal**")
        header_cols[4].write("**Totalmängd**")
        header_cols[5].write("**Åtgärd**")
        
        for i, row in enumerate(st.session_state.inbound_basket):
            row_cols = st.columns([2, 2, 4, 1, 2, 1])
            row_cols[0].write(row[0])
            row_cols[1].write(row[1])
            row_cols[2].write(row[2])
            row_cols[3].write(row[3])
            row_cols[4].write(f"{row[4]:,.2f}g")
            if row_cols[5].button("🗑️", key=f"del_inbound_{i}", help="Ta bort denna post"):
                st.session_state.inbound_basket.pop(i)
                st.rerun()

        st.markdown("---")
        action_cols = st.columns(2)
        if action_cols[0].button("💾 Spara alla poster till Google Sheets", type="primary", use_container_width=True):
            append_rows_to_sheet(SPREADSHEET_NAME, "Inbound_Log", st.session_state.inbound_basket)
            st.success("Alla inleveranser har registrerats!")
            st.session_state.inbound_basket = []
            st.cache_data.clear()
            st.rerun()
            
        if action_cols[1].button("🗑️ Töm hela listan", use_container_width=True):
            st.session_state.inbound_basket = []
            st.rerun()
            
        st.markdown('</div>', unsafe_allow_html=True)

# ------------------- Page 2: Register Production -------------------
elif selected_page == "🏭 Registrera Daglig Produktion":
    st.header("Registrera Produktproduktion")
    st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
    
    with st.form("production_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            prod_date = st.date_input("Produktionsdatum", date.today())
        
        unique_product_ids = data['df_bom']['Produkt_id'].unique() if not data['df_bom'].empty else []
        
        if not data['df_products'].empty and 'Produkt_id' in data['df_products'].columns:
            df_products_copy = data['df_products'].copy()
            df_products_copy['Produkt_id'] = df_products_copy['Produkt_id'].astype(str)
            product_name_map = df_products_copy.set_index('Produkt_id')['Produkt_namn'].to_dict()
        else:
            product_name_map = {}

        with col2:
            product_options = {
                f"{pid} - {product_name_map.get(str(pid), 'Okänt Produktnamn')}": pid 
                for pid in unique_product_ids
            }
            if product_options:
                selected_prod_label = st.selectbox("Välj produkt", options=list(product_options.keys()))
                selected_prod_id = product_options[selected_prod_label]
            else:
                st.warning("Inga produkter hittades i BOM.")
                selected_prod_id = None

        with col3:
            prod_qty = st.number_input("Antal producerade", min_value=1.0, step=1.0)
        
        if st.form_submit_button("➕ Lägg till i listan", use_container_width=True, type="primary"):
            if selected_prod_id is not None:
                product_name = product_name_map.get(str(selected_prod_id), 'Okänt Produktnamn')
                new_prod_row = [str(prod_date), str(selected_prod_id), product_name, prod_qty]
                st.session_state.production_basket.append(new_prod_row)
                st.success(f"✔️ Lade till produktion av '{product_name}' i listan.")
                st.rerun()
                
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.production_basket:
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        st.subheader("Produktioner att spara")
        
        header_cols = st.columns([2, 3, 4, 1, 1])
        header_cols[0].write("**Datum**")
        header_cols[1].write("**Produkt-ID**")
        header_cols[2].write("**Produktnamn**")
        header_cols[3].write("**Antal**")
        header_cols[4].write("**Åtgärd**")

        for i, row in enumerate(st.session_state.production_basket):
            row_cols = st.columns([2, 3, 4, 1, 1])
            row_cols[0].write(row[0])
            row_cols[1].write(row[1])
            row_cols[2].write(row[2])
            row_cols[3].write(row[3])
            if row_cols[4].button("🗑️", key=f"del_prod_{i}", help="Ta bort denna post"):
                st.session_state.production_basket.pop(i)
                st.rerun()

        st.markdown("---")
        action_cols = st.columns(2)
        if action_cols[0].button("💾 Spara all produktion till Google Sheets", type="primary", use_container_width=True):
            append_rows_to_sheet(SPREADSHEET_NAME, "Production_Log", st.session_state.production_basket)
            st.success("All produktion har registrerats!")
            st.session_state.production_basket = []
            st.cache_data.clear()
            st.rerun()
            
        if action_cols[1].button("🗑️ Töm hela listan", use_container_width=True):
            st.session_state.production_basket = []
            st.rerun()
            
        st.markdown('</div>', unsafe_allow_html=True)

# ------------------- Page 3: Current Stock -------------------
elif selected_page == "📊 Aktuellt Lagersaldo":
    st.header("Aktuellt Lagersaldo")
    stock_df = calculate_current_stock(
        data['df_insats'], 
        data['df_bom'], 
        data['df_inbound'], 
        data['df_production']
    )

    total_items = len(stock_df)
    items_in_stock = len(stock_df[stock_df['Current_Stock'] > 0]) if not stock_df.empty else 0
    items_out_of_stock = total_items - items_in_stock

    metric_cols = st.columns(3)
    metric_cols[0].metric(label="Totalt antal artiklar", value=total_items)
    metric_cols[1].metric(label="Artiklar i lager", value=items_in_stock)
    metric_cols[2].metric(label="Behov av påfyllning", value=items_out_of_stock)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
    
    search_term = st.text_input("🔍 Sök efter artikelnamn eller SI-kod:")
    
    # Start with the full dataframe
    filtered_df = stock_df
    if search_term and not stock_df.empty:
        # Apply filter if a search term is provided
        # Ensure the series are string-typed for .str.contains to avoid type-checker errors
        mask1 = stock_df['Insatsvara'].astype('string').str.contains(search_term, case=False, na=False)
        mask2 = stock_df['Sl'].astype('string').str.contains(search_term, case=False, na=False)
        filtered_df = stock_df[mask1 | mask2]
    
    # Define the columns to display and their new names for the UI
    COLUMN_MAPPING = {
        'Sl': 'SI-kod',
        'Insatsvara': 'Artikel',
        'Typ': 'Enhet',
        'Initial_Base_Stock': 'Startsaldo',
        'Total_Inbound': 'Inlevererat',
        'Total_Consumed': 'Förbrukat',
        'Current_Stock': 'Aktuellt Saldo'
    }
    
    # Robustly select only the columns that exist in the dataframe to prevent KeyErrors
    # This also satisfies linters that warn about potential errors.
    columns_to_show = [col for col in COLUMN_MAPPING.keys() if col in filtered_df.columns]
    
    # Select the existing columns for display
    # Ensure filtered_df is a DataFrame before using .loc and .copy to satisfy type-checkers
    import pandas as pd  # type: ignore[import]

    # Ensure we always produce a DataFrame to satisfy type-checkers and avoid
    # attribute errors where the variable might be inferred as a dict.
    if isinstance(filtered_df, pd.DataFrame):
        # Avoid using a variable name in the type annotation to prevent linter/type errors
        display_df = filtered_df[columns_to_show].copy()
    else:
        # Fallback: create an empty DataFrame with the expected columns
        display_df = pd.DataFrame(columns=columns_to_show).astype(object)
    # Safely rename columns only if display_df is a DataFrame (not a Series)
    if isinstance(display_df, pd.DataFrame):
        display_df.columns = [COLUMN_MAPPING.get(col, col) for col in display_df.columns]

    def style_low_stock(row):
        """Applies a highlight style to rows with zero or negative stock."""
        if row['Aktuellt Saldo'] <= 0:
            return ['background-color: #FFD2D2'] * len(row)
        return [''] * len(row)

    # Apply styling to highlight low-stock items
    styled_df = display_df.style.apply(style_low_stock, axis=1)

    # Prepare options for the SelectboxColumn safely, preventing errors on an empty dataframe
    enhet_options = []
    if not display_df.empty and 'Enhet' in display_df.columns:
        enhet_options = display_df['Enhet'].unique().tolist()

    st.dataframe(
        styled_df,
        # The order is now implicitly handled by the COLUMN_MAPPING dictionary keys
        column_config={
            # We configure the original column names before they are displayed with new names
            "Startsaldo": st.column_config.NumberColumn(format="%,.2f g"),
            "Inlevererat": st.column_config.NumberColumn(format="%,.2f g"),
            "Förbrukat": st.column_config.NumberColumn(format="%,.2f g"),
            "Aktuellt Saldo": st.column_config.NumberColumn(format="%,.2f g"),
            "Enhet": st.column_config.SelectboxColumn(options=enhet_options)
        },
        use_container_width=True,
        hide_index=True
    )
    st.markdown('</div>', unsafe_allow_html=True)