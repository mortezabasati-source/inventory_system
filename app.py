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

# --- Database & Config Settings ---
SPREADSHEET_NAME = "Inventory_System_DB"

# Safe retrieval of APP_SECRET_KEY from Streamlit secrets
APP_SECRET_KEY = st.secrets.get("APP_SECRET_KEY", None)

# --- Page Configuration ---
st.set_page_config(
    page_title="SmartLager",
    page_icon="logo.png",
    layout="wide"
)

# --- Custom Meta Tags for Progressive Web App (PWA) ---
st.markdown("""
<meta name="apple-mobile-web-app-title" content="SmartLager">
<meta name="application-name" content="SmartLager">
<link rel="apple-touch-icon" href="logo.png">
""", unsafe_allow_html=True)

# --- Global Custom CSS Injection (Compact Eataway Theme) ---
st.markdown("""
<style>
    /* 1. Reduce Top Margin & Padding across main container */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }

    /* 2. Global App Background (Warm Ivory) */
    [data-testid="stAppViewContainer"] {
        background-color: #FAF8F0 !important;
    }
    
    [data-testid="stHeader"] {
        background-color: rgba(0, 0, 0, 0) !important;
    }

    /* 3. Compact Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #F3EFE0 !important;
        border-right: 1.5px solid #DDD7C0 !important;
    }
    
    [data-testid="stSidebar"] * {
        font-weight: 700 !important;
    }

    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div {
        color: #146331 !important;
        font-weight: 700 !important;
    }

    /* 4. Custom Compact Card Container Styling */
    .smartlager-card {
        background-color: #F3EFE0 !important;
        border: 1.5px solid #DDD7C0 !important;
        border-radius: 10px;
        padding: 12px 16px !important;
        margin-bottom: 10px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
    }

    /* Compact Headings */
    h1 {
        font-size: 1.8rem !important;
        margin-bottom: 0.2rem !important;
        padding-bottom: 0rem !important;
    }
    h2, h3, h4, h5, h6 {
        margin-top: 0.2rem !important;
        margin-bottom: 0.4rem !important;
    }

    /* 5. Primary Action Buttons */
    .stButton > button[kind="primary"] {
        background-color: #146331 !important;
        color: #FFFFFF !important;
        border-radius: 6px !important;
        border: none !important;
        font-weight: 700 !important;
        padding: 0.25rem 0.75rem !important;
        transition: all 0.2s ease-in-out !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #1B8242 !important;
        color: #FFFFFF !important;
        box-shadow: 0 2px 8px rgba(27, 130, 66, 0.25) !important;
    }

    /* 6. Summary Metric Cards */
    [data-testid="stMetric"] {
        background-color: #F3EFE0 !important;
        border: 1.5px solid #DDD7C0 !important;
        border-radius: 10px;
        padding: 6px 10px !important;
    }
    [data-testid="stMetricLabel"] {
        color: #146331 !important;
        font-weight: 700 !important;
        font-size: 0.8rem !important;
    }
    [data-testid="stMetricValue"] {
        color: #0E4722 !important;
        font-weight: 800 !important;
        font-size: 1.15rem !important;
    }

    /* 7. DataFrame Container Styling */
    [data-testid="stDataFrame"] {
        border: 1.5px solid #DDD7C0 !important;
        border-radius: 10px !important;
        background-color: #F3EFE0 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Header Section ---
st.title("📦 SmartLager")
st.caption("Intelligent lager- och produktionshantering")

# --- Help Text Dictionary (Swedish UI Tooltips) ---
HELP_TEXTS = {
    "inbound_date": "Välj det datum då varorna togs emot i lagret.",
    "inbound_item": "Välj den råvara (insatsvara) som har levererats.",
    "inbound_pkg_qty": "Ange antalet mottagna förpackningar.",
    "inbound_secret": "Ange den hemliga nyckeln för att spara alla poster.",
    "prod_date": "Välj det datum då produktionen ägde rum.",
    "prod_item": "Välj den färdiga produkt som har tillverkats.",
    "prod_qty": "Ange det totala antalet enheter som producerats.",
    "prod_secret": "Ange den hemliga nyckeln för att spara produktionsposter.",
    "new_insats_name": "Ange det fullständiga namnet på den nya råvaran.",
    "new_insats_type": "Välj en befintlig typ eller ange en ny.",
    "new_insats_new_type": "Skriv in den nya typen/enheten.",
    "new_insats_vikt_pcs": "Ange basvikten per enhet.",
    "new_insats_initial_stock": "Ange startsaldot.",
    "new_insats_price": "Ange inköpspriset per enhet.",
    "new_insats_supplier": "Välj eller ange en ny leverantör.",
    "new_insats_new_supplier": "Skriv in namnet på den nya leverantören.",
    "new_insats_secret": "Ange den hemliga nyckeln för att spara råvarorna.",
    "new_prod_id": "Ange ett unikt ID för den nya produkten.",
    "new_prod_name": "Ange det fullständiga namnet på den nya produkten.",
    "new_prod_utpris": "Ange försäljningspriset för produkten.",
    "new_prod_bom_item": "Välj en råvara som ingår i produkten.",
    "new_prod_bom_unit": "Ange enheten för förbrukningen.",
    "new_prod_bom_consumption": "Ange hur mycket av råvaran som går åt.",
    "new_prod_secret": "Ange den hemliga nyckeln för att spara produkten och BOM.",
    "search_stock": "Sök fritt på artikelnamn eller SI-kod."
}

# --- Data Loading Function ---
def load_all_data():
    """Loads all required worksheets from Google Sheets with individual error handling."""
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

INSATS_COLUMNS = ['Sl', 'Insatsvara', 'Typ', 'Vikt/Pcs', 'Antal', 'Pris (Kr)', 'Leverantör']

def get_next_sl(df_insats: pd.DataFrame) -> int:
    """Calculates the next available raw material ID code (Sl)."""
    sl_series = pd.Series(df_insats['Sl'])
    sl_numeric = pd.to_numeric(sl_series, errors='coerce')

    if not isinstance(sl_numeric, pd.Series):
        return 501

    non_null_values = sl_numeric.dropna()
    if not non_null_values.empty:
        max_sl = float(non_null_values.to_numpy(dtype=float).max())
        return int(max_sl) + 1
    return 501

# Fetch data at application start
data = load_all_data()

# Initialize session state lists for batch processing baskets
if 'inbound_basket' not in st.session_state:
    st.session_state['inbound_basket'] = []
if 'production_basket' not in st.session_state:
    st.session_state['production_basket'] = []
if 'insats_basket' not in st.session_state:
    st.session_state['insats_basket'] = []

# --- Calculation Functions ---
def calculate_product_cost_and_margin(df_products: pd.DataFrame, df_bom: pd.DataFrame, df_insats: pd.DataFrame) -> pd.DataFrame:
    """Calculates cost price and profit margin for each product recursively based on BOM."""
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
    all_product_ids_in_bom = set(df_bom['Produkt_id'].unique())

    def get_cost(item_id):
        item_id = str(item_id)
        if item_id in memo:
            return memo[item_id]
        
        if item_id in all_product_ids_in_bom:
            bom_for_item = df_bom[df_bom['Produkt_id'] == item_id]
            total_cost = 0
            for _, row in bom_for_item.iterrows():
                consumption = pd.to_numeric(row.get('Förbrukning'), errors='coerce')
                consumption_value = consumption if pd.notna(consumption) else 0
                total_cost += get_cost(row['SI']) * consumption_value
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

# --- Sidebar Navigation ---
st.sidebar.title("Navigering")
nav_options = [
    "📊 Aktuellt Lagersaldo",
    "💰 Marginaler",
    "📥 Registrera Inleverans",
    "🏭 Registrera Daglig Produktion",    
    "➕ Lägg till ny artikel"
]

selected_page = st.sidebar.radio("Välj en sida:", nav_options)

# ==============================================================================
# PAGE 1: CURRENT STOCK (Aktuellt Lagersaldo)
# ==============================================================================
if selected_page == "📊 Aktuellt Lagersaldo":
    st.header("📊 Aktuellt Lagersaldo")
    
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

    st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
    
    search_term = st.text_input("🔍 Sök efter artikelnamn eller SI-kod:", help=HELP_TEXTS["search_stock"])
    
    filtered_df = stock_df
    if search_term and not stock_df.empty:
        mask1 = stock_df['Insatsvara'].astype('string').str.contains(search_term, case=False, na=False)
        mask2 = stock_df['Sl'].astype('string').str.contains(search_term, case=False, na=False)
        filtered_df = stock_df[mask1 | mask2]
    
    COLUMN_MAPPING = {
        'Sl': 'SI-kod',
        'Insatsvara': 'Artikel',
        'Typ': 'Enhet',
        'Initial_Base_Stock': 'Startsaldo',
        'Total_Inbound': 'Inlevererat',
        'Total_Consumed': 'Förbrukat',
        'Current_Stock': 'Aktuellt Saldo'
    }
    
    columns_to_show = [col for col in COLUMN_MAPPING.keys() if col in filtered_df.columns]
    display_df = filtered_df[columns_to_show].copy() if isinstance(filtered_df, pd.DataFrame) else pd.DataFrame(columns=columns_to_show)
    display_df.columns = [COLUMN_MAPPING.get(col, col) for col in display_df.columns]

    def style_low_stock(row):
        if row['Aktuellt Saldo'] <= 0:
            return ['background-color: #FFD2D2'] * len(row)
        return [''] * len(row)

    styled_df = display_df.style.apply(style_low_stock, axis=1)

    st.dataframe(
        styled_df,
        use_container_width=True,
        column_config={
            "Startsaldo": st.column_config.NumberColumn(format="%,.2f g"),
            "Inlevererat": st.column_config.NumberColumn(format="%,.2f g"),
            "Förbrukat": st.column_config.NumberColumn(format="%,.2f g"),
            "Aktuellt Saldo": st.column_config.NumberColumn(format="%,.2f g"),
        },
        hide_index=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# PAGE 2: PROFITABILITY ANALYSIS (Marginaler)
# ==============================================================================
elif selected_page == "💰 Marginaler":
    st.header("💰 Marginaler & Lönsamhet")

    margin_df = calculate_product_cost_and_margin(
        data['df_products'],
        data['df_bom'],
        data['df_insats']
    )

    if not margin_df.empty:
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        display_df = margin_df[['Produkt_id', 'Produkt_namn', 'Utpris', 'Kostpris', 'Vinstmarginal (%)']].copy()
        
        def style_margin(val):
            if val < 10:
                return 'background-color: #FFD2D2'
            elif val < 30:
                return 'background-color: #FFF3CD'
            else:
                return 'background-color: #D4EDDA'

        styled_df = display_df.style
        if 'Vinstmarginal (%)' in display_df.columns:
            styled_df = styled_df.map(style_margin, subset=['Vinstmarginal (%)'])

        st.dataframe(
            styled_df,
            use_container_width=True,
            column_config={
                "Utpris": st.column_config.NumberColumn(format="%.2f kr"),
                "Kostpris": st.column_config.NumberColumn(format="%.2f kr"),
                "Vinstmarginal (%)": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
            },
            hide_index=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# PAGE 3: REGISTER INBOUND (Registrera Inleverans)
# ==============================================================================
elif selected_page == "📥 Registrera Inleverans":
    st.header("📥 Registrera Inleverans av Varor")
    st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
    
    with st.form("inbound_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 2, 2])
        with col1:
            entry_date = st.date_input("Inleveransdatum", date.today(), help=HELP_TEXTS["inbound_date"])
        
        def create_inbound_label(row):
            label = f"{row['Sl']} - {row['Insatsvara']} ({row['Typ']}"
            weight = row.get('Vikt/Pcs')
            if weight and pd.notna(weight) and str(weight).strip():
                label += f" - {weight}g"
            label += ")"
            return label

        with col2:
            item_options = {create_inbound_label(row): row for _, row in data['df_insats'].iterrows()}
            selected_item_str = st.selectbox("Välj artikel / SI-kod", options=list(item_options.keys()), help=HELP_TEXTS["inbound_item"])
            selected_item = item_options[selected_item_str]
        
        with col3:
            pkg_qty = st.number_input("Antal förpackningar", min_value=1.0, step=1.0, help=HELP_TEXTS["inbound_pkg_qty"])
        
        col_submit1, col_submit2 = st.columns([3, 1])
        with col_submit1:
            try:
                vikt_pcs = float(selected_item.get('Vikt/Pcs') or 1.0)
            except (ValueError, TypeError):
                vikt_pcs = 1.0
            total_base = pkg_qty * vikt_pcs
            st.info(f"Total basmängd som läggs till: **{total_base:,.2f}g**")
        
        with col_submit2:
            if st.form_submit_button("➕ Lägg till", type="primary"):
                new_row = [str(entry_date), str(selected_item['Sl']), selected_item['Insatsvara'], pkg_qty, total_base]
                st.session_state.inbound_basket.append(new_row)
                st.rerun()
                
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.inbound_basket:
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        st.subheader("Poster att spara")
        for i, row in enumerate(st.session_state.inbound_basket):
            row_cols = st.columns([2, 2, 4, 1, 2, 1])
            row_cols[0].write(row[0])
            row_cols[1].write(row[1])
            row_cols[2].write(row[2])
            row_cols[3].write(row[3])
            row_cols[4].write(f"{row[4]:,.2f}g")
            if row_cols[5].button("🗑️", key=f"del_inbound_{i}"):
                st.session_state.inbound_basket.pop(i)
                st.rerun()

        secret_key_inbound = st.text_input("🔑 Säkerhetsnyckel", type="password", key="secret_inbound", help=HELP_TEXTS["inbound_secret"])
        action_cols = st.columns(2)
        if action_cols[0].button("💾 Spara alla", type="primary"):
            if secret_key_inbound.strip() == str(APP_SECRET_KEY).strip():
                append_rows_to_sheet(SPREADSHEET_NAME, "Inbound_Log", st.session_state.inbound_basket)
                st.session_state.inbound_basket = []
                st.cache_data.clear()
                st.success("✅ Inleveranser registrerades!")
                st.rerun()
            else:
                st.error("⛔ Felaktig nyckel.")
            
        if action_cols[1].button("🗑️ Töm listan"):
            st.session_state.inbound_basket = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# PAGE 4: REGISTER DAILY PRODUCTION (Registrera Daglig Produktion)
# ==============================================================================
elif selected_page == "🏭 Registrera Daglig Produktion":
    st.header("🏭 Registrera Daglig Produktion")
    st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
    
    with st.form("production_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([2, 2, 2])
        with col1:
            prod_date = st.date_input("Produktionsdatum", date.today(), help=HELP_TEXTS["prod_date"])
        
        unique_product_ids = data['df_bom']['Produkt_id'].unique() if not data['df_bom'].empty else []
        df_products_copy = data['df_products'].copy() if not data['df_products'].empty else pd.DataFrame()
        product_name_map = df_products_copy.set_index('Produkt_id')['Produkt_namn'].to_dict() if 'Produkt_id' in df_products_copy.columns else {}

        with col2:
            product_options = {f"{pid} - {product_name_map.get(str(pid), 'Okänd')}": pid for pid in unique_product_ids}
            selected_prod_label = st.selectbox("Välj produkt", options=list(product_options.keys()), help=HELP_TEXTS["prod_item"]) if product_options else None
            selected_prod_id = product_options[selected_prod_label] if selected_prod_label else None

        with col3:
            prod_qty = st.number_input("Antal producerade", min_value=1.0, step=1.0, help=HELP_TEXTS["prod_qty"])
        
        if st.form_submit_button("➕ Lägg till", type="primary"):
            if selected_prod_id is not None:
                product_name = product_name_map.get(str(selected_prod_id), 'Okänd')
                st.session_state.production_basket.append([str(prod_date), str(selected_prod_id), product_name, prod_qty])
                st.rerun()
                
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.production_basket:
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        st.subheader("Produktioner att spara")
        for i, row in enumerate(st.session_state.production_basket):
            row_cols = st.columns([2, 3, 4, 1, 1])
            row_cols[0].write(row[0])
            row_cols[1].write(row[1])
            row_cols[2].write(row[2])
            row_cols[3].write(row[3])
            if row_cols[4].button("🗑️", key=f"del_prod_{i}"):
                st.session_state.production_basket.pop(i)
                st.rerun()

        secret_key_prod = st.text_input("🔑 Säkerhetsnyckel", type="password", key="secret_prod", help=HELP_TEXTS["prod_secret"])
        action_cols = st.columns(2)
        if action_cols[0].button("💾 Spara all produktion", type="primary"):
            if secret_key_prod.strip() == str(APP_SECRET_KEY).strip():
                append_rows_to_sheet(SPREADSHEET_NAME, "Production_Log", st.session_state.production_basket)
                st.session_state.production_basket = []
                st.cache_data.clear()
                st.success("✅ Produktion registrerades!")
                st.rerun()
            else:
                st.error("⛔ Felaktig nyckel.")
            
        if action_cols[1].button("🗑️ Töm listan"):
            st.session_state.production_basket = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# PAGE 5: PERFECTLY ALIGNED BOM BUILDER (Metrics right above Recipe Canvas)
# ==============================================================================
elif selected_page == "➕ Lägg till ny artikel":
    st.header("➕ Lägg till ny artikel eller produkt")

    add_choice = st.radio(
        "Vad vill du lägga till?",
        ("Ny insatsvara (råmaterial)", "Ny färdig produkt (med BOM)"),
        horizontal=True,
        label_visibility="collapsed"
    )

    # --- Option 1: Add Raw Material ---
    if add_choice == "Ny insatsvara (råmaterial)":
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        st.subheader("Lägg till ny insatsvara")
        
        with st.form("new_insats_form", clear_on_submit=True):
            next_sl = get_next_sl(data['df_insats'])
            st.info(f"Nästa tillgängliga SI-kod (Sl): **{next_sl}**")

            cols = st.columns(2)
            insats_name = cols[0].text_input("Artikelnamn", help=HELP_TEXTS["new_insats_name"])

            unique_types = sorted(data['df_insats']['Typ'].dropna().unique()) if not data['df_insats'].empty else []
            type_options = unique_types + ["--- Ange ny ---"]
            selected_type = cols[1].selectbox("Typ", options=type_options, help=HELP_TEXTS["new_insats_type"])
            insats_type = cols[1].text_input("Ange ny typ:", key="new_type_input") if selected_type == "--- Ange ny ---" else selected_type

            vikt_pcs = cols[0].number_input("Vikt/Pcs (om typ är 'g')", min_value=0.0, format="%.2f", help=HELP_TEXTS["new_insats_vikt_pcs"])
            initial_stock = cols[1].number_input("Startsaldo", min_value=0.0, step=1.0, help=HELP_TEXTS["new_insats_initial_stock"])
            price = cols[0].number_input("Pris (Kr)", min_value=0.0, format="%.2f", help=HELP_TEXTS["new_insats_price"])

            unique_suppliers = sorted(data['df_insats']['Leverantör'].dropna().unique()) if not data['df_insats'].empty else []
            supplier_options = unique_suppliers + ["--- Ange ny ---"]
            selected_supplier = cols[1].selectbox("Leverantör", options=supplier_options, help=HELP_TEXTS["new_insats_supplier"])
            supplier = cols[1].text_input("Ange ny leverantör:", key="new_supplier_input") if selected_supplier == "--- Ange ny ---" else selected_supplier

            if st.form_submit_button("➕ Lägg till", type="primary"):
                if insats_name:
                    st.session_state.insats_basket.append([next_sl, insats_name, insats_type, vikt_pcs, initial_stock, price, supplier])
                    st.rerun()

        if st.session_state.insats_basket:
            st.subheader("Nya insatsvaror att spara")
            df_basket = pd.DataFrame(st.session_state.insats_basket, columns=INSATS_COLUMNS)
            st.dataframe(df_basket, hide_index=True)

            secret_key_insats = st.text_input("🔑 Säkerhetsnyckel", type="password", key="secret_insats", help=HELP_TEXTS["new_insats_secret"])
            action_cols = st.columns(2)
            if action_cols[0].button("💾 Spara alla", type="primary"):
                if secret_key_insats.strip() == str(APP_SECRET_KEY).strip():
                    append_rows_to_sheet(SPREADSHEET_NAME, "Insatsvara", st.session_state.insats_basket)
                    st.session_state.insats_basket = []
                    st.cache_data.clear()
                    st.success("✅ Insatsvaror sparades!")
                    st.rerun()
                else:
                    st.error("⛔ Felaktig nyckel.")
            if action_cols[1].button("🗑️ Töm listan"):
                st.session_state.insats_basket = []
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # --- Option 2: BOM Builder with Metrics Placed Cleanly in Right Column ---
    elif add_choice == "Ny färdig produkt (med BOM)":
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        st.markdown("##### 📌 Steg 1: Produktinformation")
        
        prod_cols = st.columns([2, 3, 2])
        product_id_input = prod_cols[0].text_input("Produkt-ID (unikt)", help=HELP_TEXTS["new_prod_id"])
        product_name = prod_cols[1].text_input("Produktnamn", help=HELP_TEXTS["new_prod_name"])
        utpris_input = prod_cols[2].number_input("Utpris (kr)", min_value=0.0, format="%.2f", help=HELP_TEXTS["new_prod_utpris"])
        st.markdown('</div>', unsafe_allow_html=True)

        if 'bom_components' not in st.session_state:
            st.session_state.bom_components = []

        # Sync & recalculate live total costs dynamically from current session state keys
        estimated_total_cost = 0.0
        for idx, comp in enumerate(st.session_state.bom_components):
            key = f"qty_input_{comp['SI']}_{idx}"
            if key in st.session_state:
                st.session_state.bom_components[idx]['Förbrukning'] = float(st.session_state[key])
            estimated_total_cost += float(st.session_state.bom_components[idx]['Förbrukning']) * float(comp.get('UnitCost', 0.0))

        estimated_margin = ((utpris_input - estimated_total_cost) / utpris_input * 100) if utpris_input > 0 else 0

        # Side-by-side BOM builder layout
        col_left, col_right = st.columns([1, 1])

        # Left Column: Raw Materials Search Library
        with col_left:
            st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
            st.markdown("###### 🔍 Sök & Välj Råvaror")
            search_query = st.text_input("Sök råvara eller SI-kod:", placeholder="T.ex. Vetemjöl", key="bom_search_input")

            if not data['df_insats'].empty:
                df_filtered = data['df_insats'].copy()
                if search_query.strip():
                    m1 = df_filtered['Insatsvara'].astype(str).str.contains(search_query, case=False, na=False)
                    m2 = df_filtered['Sl'].astype(str).str.contains(search_query, case=False, na=False)
                    df_filtered = df_filtered[m1 | m2]

                with st.container(height=380):
                    for _, row in df_filtered.iterrows():
                        si_code = str(row['Sl'])
                        mat_name = str(row['Insatsvara'])
                        unit = str(row.get('Typ', 'g'))
                        price = float(row.get('Pris (Kr)', 0.0)) if pd.notna(row.get('Pris (Kr)')) else 0.0
                        vikt_pcs = float(row.get('Vikt/Pcs', 1.0)) if pd.notna(row.get('Vikt/Pcs')) and float(row.get('Vikt/Pcs', 1.0)) > 0 else 1.0
                        unit_cost = price / vikt_pcs

                        c_info, c_btn = st.columns([3, 1])
                        c_info.markdown(f"**{mat_name}** (`{si_code}`)  \n<small>{price:.2f} Kr / {unit}</small>", unsafe_allow_html=True)
                        
                        if c_btn.button("➕", key=f"add_raw_{si_code}"):
                            if not any(comp['SI'] == si_code for comp in st.session_state.bom_components):
                                st.session_state.bom_components.append({
                                    'SI': si_code,
                                    'Insatsvara': mat_name,
                                    'Enhet': unit if unit else 'g',
                                    'Förbrukning': 1.0,
                                    'UnitCost': unit_cost
                                })
                                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # Right Column: Metrics Cards placed DIRECTLY above Recipe Canvas
        with col_right:
            st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
            
            # Compact metrics right above recipe components
            m1, m2 = st.columns(2)
            m1.metric("Kostpris", f"{estimated_total_cost:,.2f} Kr")
            m2.metric("Vinstmarginal", f"{estimated_margin:.1f}%")
            
            st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
            st.markdown("###### 📋 Valda Komponenter i Receptet")

            with st.container(height=380):
                if not st.session_state.bom_components:
                    st.info("👈 Sök och klicka på ➕ till vänster för att lägga till råvaror.")
                else:
                    for idx, comp in enumerate(st.session_state.bom_components):
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.write(f"**{comp['Insatsvara']}** (`{comp['SI']}`)")
                        
                        c2.number_input(
                            label="",
                            min_value=0.01,
                            value=float(comp['Förbrukning']),
                            step=1.0,
                            key=f"qty_input_{comp['SI']}_{idx}",
                            label_visibility="collapsed"
                        )
                        
                        if c3.button("🗑️", key=f"remove_comp_{comp['SI']}_{idx}"):
                            st.session_state.bom_components.pop(idx)
                            st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

        # Step 3: Compact integrated commit row
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        col_sec, col_act = st.columns([2, 1])
        secret_key_product = col_sec.text_input("🔑 Säkerhetsnyckel", type="password", key="secret_new_product", help=HELP_TEXTS["new_prod_secret"])
        
        col_act.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        if col_act.button("💾 Spara produkt och BOM", type="primary", use_container_width=True):
            existing_ids = set(data['df_products']['Produkt_id'].astype(str)) if not data['df_products'].empty else set()
            
            if not product_id_input or not product_name or not st.session_state.bom_components or utpris_input <= 0:
                st.warning("Ange Produkt-ID, Namn, Utpris och minst en komponent.")
            elif product_id_input in existing_ids:
                st.error(f"⛔ Produkt-ID '{product_id_input}' finns redan.")
            elif secret_key_product.strip() == str(APP_SECRET_KEY).strip():
                append_rows_to_sheet(SPREADSHEET_NAME, "Products", [[product_id_input, product_name, utpris_input]])
                bom_rows = [[product_id_input, comp['SI'], comp['Insatsvara'], comp['Enhet'], comp['Förbrukning']] for comp in st.session_state.bom_components]
                append_rows_to_sheet(SPREADSHEET_NAME, "BOM", bom_rows)
                
                st.session_state.bom_components = []
                st.cache_data.clear()
                st.success(f"✅ Produkt '{product_name}' har sparats!")
            else:
                st.error("⛔ Felaktig nyckel.")
        st.markdown('</div>', unsafe_allow_html=True)