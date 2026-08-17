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

# Safe retrieval of APP_SECRET_KEY from secrets
APP_SECRET_KEY = st.secrets.get("APP_SECRET_KEY", None)

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

# --- Help Text Dictionary (i18n) ---
HELP_TEXTS = {
    # Inbound Page
    "inbound_date": "Välj det datum då varorna togs emot i lagret. Klicka för att öppna kalendern.",
    "inbound_item": "Välj den råvara (insatsvara) som har levererats. Listan visar SI-kod, namn och typ.",
    "inbound_pkg_qty": "Ange antalet mottagna förpackningar (t.ex. kartonger, säckar). Använd heltal.",
    "inbound_secret": "Ange den hemliga nyckeln för att bekräfta och spara alla poster i listan till databasen.",
    
    # Production Page
    "prod_date": "Välj det datum då produktionen ägde rum.",
    "prod_item": "Välj den färdiga produkt som har tillverkats. Listan baseras på produkter definierade i BOM.",
    "prod_qty": "Ange det totala antalet enheter som producerats av den valda produkten.",
    "prod_secret": "Ange den hemliga nyckeln för att bekräfta och spara alla produktionsposter till databasen.",

    # Add New Item Page
    "new_insats_name": "Ange det fullständiga namnet på den nya råvaran (t.ex. 'Vetemjöl Special').",
    "new_insats_type": "Välj en befintlig typ (t.ex. 'g', 'st') eller välj '--- Ange ny ---' för att skapa en ny.",
    "new_insats_new_type": "Om du valt '--- Ange ny ---', skriv in den nya typen/enheten här (t.ex. 'ml', 'kg').",
    "new_insats_vikt_pcs": "Om varan hanteras i vikt, ange basvikten per enhet (t.ex. vikten för 1 st). Lämna 0 om ej relevant.",
    "new_insats_initial_stock": "Ange startsaldot för denna vara. Detta är antalet förpackningar du har från början.",
    "new_insats_price": "Ange inköpspriset per förpackning/enhet.",
    "new_insats_supplier": "Välj en befintlig leverantör eller välj '--- Ange ny ---' för att lägga till en ny.",
    "new_insats_new_supplier": "Om du valt '--- Ange ny ---', skriv in namnet på den nya leverantören här.",
    "new_insats_secret": "Ange den hemliga nyckeln för att spara de nya råvarorna till databasen.",

    # Add New Product Page
    "new_prod_id": "Ange ett unikt ID för den nya produkten (t.ex. 'PROD-105'). Detta kan inte ändras senare.",
    "new_prod_name": "Ange det fullständiga namnet på den nya färdiga produkten (t.ex. 'Kanelbulle Stor').",
    "new_prod_utpris": "Ange försäljningspriset för produkten (priset till kund). Använd punkt som decimalavskiljare.",
    "new_prod_bom_item": "Välj en råvara som ingår i produkten.",
    "new_prod_bom_unit": "Ange enheten för förbrukningen (standard är 'g' för gram).",
    "new_prod_bom_consumption": "Ange hur mycket av råvaran (i vald enhet) som går åt för att tillverka EN enhet av produkten.",
    "new_prod_secret": "Ange den hemliga nyckeln för att spara den nya produkten och dess materialförteckning (BOM).",
    "search_stock": "Sök fritt på artikelnamn eller SI-kod för att snabbt filtrera lagerlistan."
}

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

INSATS_COLUMNS = ['Sl', 'Insatsvara', 'Typ', 'Vikt/Pcs', 'Antal', 'Pris (Kr)', 'Leverantör']

def get_next_sl(df_insats: pd.DataFrame) -> int:
    sl_series = pd.Series(df_insats['Sl'])
    sl_numeric = pd.to_numeric(sl_series, errors='coerce')

    if not isinstance(sl_numeric, pd.Series):
        return 501

    non_null_values = sl_numeric.dropna()
    if not non_null_values.empty:
        max_sl = float(non_null_values.to_numpy(dtype=float).max())
        return int(max_sl) + 1
    return 501

def get_existing_sl_codes(df_insats: pd.DataFrame) -> set[str]:
    return {str(sl).strip() for sl in df_insats['Sl'].astype(str) if str(sl).strip()}

data = load_all_data()

# Initialize session state for batch processing baskets
if 'inbound_basket' not in st.session_state:
    st.session_state['inbound_basket'] = []
if 'production_basket' not in st.session_state:
    st.session_state['production_basket'] = []
if 'insats_basket' not in st.session_state:
    st.session_state['insats_basket'] = []

def calculate_product_cost_and_margin(df_products: pd.DataFrame, df_bom: pd.DataFrame, df_insats: pd.DataFrame) -> pd.DataFrame:
    """Calculates cost price and profit margin for each product."""
    if df_products.empty or 'Produkt_id' not in df_products.columns:
        return pd.DataFrame()

    # Ensure 'Utpris' column exists and is numeric, fill missing with 0
    if 'Utpris' not in df_products.columns:
        df_products['Utpris'] = 0.0

    utpris_values = pd.to_numeric(df_products['Utpris'], errors='coerce')
    df_products['Utpris'] = pd.Series(utpris_values, index=df_products.index).fillna(0.0)

    # --- Data Type Standardization ---
    # Ensure all ID columns used for matching are strings to prevent type mismatches.
    df_bom['Produkt_id'] = df_bom['Produkt_id'].astype(str)
    df_bom['SI'] = df_bom['SI'].astype(str)

    # --- Multi-Level BOM Cost Calculation Logic ---
    df_insats_copy = df_insats.copy()
    vikt_per_pcs = pd.to_numeric(df_insats_copy['Vikt/Pcs'], errors='coerce')
    df_insats_copy['Vikt/Pcs'] = pd.Series(vikt_per_pcs, index=df_insats_copy.index).fillna(1.0)
    pris_kr = pd.to_numeric(df_insats_copy['Pris (Kr)'], errors='coerce')
    df_insats_copy['Pris (Kr)'] = pd.Series(pris_kr, index=df_insats_copy.index).fillna(0.0)

    # 1. Create a price map for raw materials (Insatsvara)
    raw_material_price_map = {}
    for _, row in df_insats_copy.iterrows():
        si_code = str(row['Sl']) # Convert key to string to match item_id type
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
            # For 'st' (piece) type items, the price is per package.
            # 'Vikt/Pcs' for 'st' items should represent the number of pieces in the package.
            # The unit cost is Price / Pieces per package.
            pieces_per_pkg = weight_per_pkg
            raw_material_price_map[si_code] = price / pieces_per_pkg if pieces_per_pkg > 0 else price

    # 2. Recursive function to calculate cost for any product/sub-product
    memo = {} # Memoization to avoid re-calculating costs
    # A product is anything that has a BOM. This includes final products and sub-assemblies.
    # This is the key change to fix the "zero cost" issue.
    all_product_ids_in_bom = set(df_bom['Produkt_id'].unique())


    def get_cost(item_id):
        item_id = str(item_id)
        if item_id in memo:
            return memo[item_id]
        
        # Priority 1: Check if the item is a product/sub-product and calculate its cost recursively.
        if item_id in all_product_ids_in_bom:
            bom_for_item = df_bom[df_bom['Produkt_id'] == item_id] # Find the recipe for this item
            total_cost = 0
            for _, row in bom_for_item.iterrows():
                consumption = pd.to_numeric(row.get('Förbrukning'), errors='coerce')
                consumption_value = consumption if pd.notna(consumption) else 0
                total_cost += get_cost(row['SI']) * consumption_value
            memo[item_id] = total_cost
            return total_cost
        
        # Priority 2: If not a product, check if it's a raw material and return its price.
        if item_id in raw_material_price_map:
            return raw_material_price_map[item_id]
        
        return 0 # Item not found

    # 3. Calculate cost for all final products
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

st.markdown("---") # Visual separator remains in the main panel
# ------------------- Page 1: Register Inbound -------------------
if selected_page == "📥 Registrera Inleverans":
    st.header("Registrera Inleverans av Varor")
    st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
    
    with st.form("inbound_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([1, 3, 1])
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
        
        st.markdown("---")
        col_submit1, col_submit2 = st.columns([3, 1])
        with col_submit1:
            try:
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
        
        # Security Key Verification
        secret_key_inbound = st.text_input("🔑 Ange säkerhetsnyckel för att spara", type="password", key="secret_inbound", help=HELP_TEXTS["inbound_secret"])
        
        action_cols = st.columns(2)
        if action_cols[0].button("💾 Spara alla poster till Google Sheets", type="primary", use_container_width=True):
            if not APP_SECRET_KEY:
                st.error("⚠️ APP_SECRET_KEY در Secrets تعریف نشده است!")
            elif secret_key_inbound.strip() == str(APP_SECRET_KEY).strip():
                append_rows_to_sheet(SPREADSHEET_NAME, "Inbound_Log", st.session_state.inbound_basket)
                st.session_state.inbound_basket = []
                st.cache_data.clear()
                st.success("✅ Alla inleveranser har registrerats!")
                st.rerun()
            else:
                st.error("⛔ Felaktig säkerhetsnyckel. Posterna sparades inte.")
            
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
            prod_date = st.date_input("Produktionsdatum", date.today(), help=HELP_TEXTS["prod_date"])
        
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
                selected_prod_label = st.selectbox("Välj produkt", options=list(product_options.keys()), help=HELP_TEXTS["prod_item"])
                selected_prod_id = product_options[selected_prod_label]
            else:
                st.warning("Inga produkter hittades i BOM.")
                selected_prod_id = None

        with col3:
            prod_qty = st.number_input("Antal producerade", min_value=1.0, step=1.0, help=HELP_TEXTS["prod_qty"])
        
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
        
        # Security Key Verification
        secret_key_prod = st.text_input("🔑 Ange säkerhetsnyckel för att spara", type="password", key="secret_prod", help=HELP_TEXTS["prod_secret"])
        
        action_cols = st.columns(2)
        if action_cols[0].button("💾 Spara all produktion till Google Sheets", type="primary", use_container_width=True):
            if not APP_SECRET_KEY:
                st.error("⚠️ APP_SECRET_KEY در Secrets تعریف نشده است!")
            elif secret_key_prod.strip() == str(APP_SECRET_KEY).strip():
                append_rows_to_sheet(SPREADSHEET_NAME, "Production_Log", st.session_state.production_basket)
                st.session_state.production_basket = []
                st.cache_data.clear()
                st.success("✅ All produktion har registrerats!")
                st.rerun()
            else:
                st.error("⛔ Felaktig säkerhetsnyckel. Posterna sparades inte.")
            
        if action_cols[1].button("🗑️ Töm hela listan", use_container_width=True):
            st.session_state.production_basket = []
            st.rerun()
            
        st.markdown('</div>', unsafe_allow_html=True)

# ------------------- Page 4: Add New Item/Product -------------------
elif selected_page == "➕ Lägg till ny artikel":
    st.header("Lägg till ny artikel eller produkt")

    add_choice = st.radio(
        "Vad vill du lägga till?",
        ("Ny insatsvara (råmaterial)", "Ny färdig produkt (med BOM)"),
        horizontal=True,
        label_visibility="collapsed"
    )

    st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)

    # --- Add New Raw Material (Insatsvara) ---
    if add_choice == "Ny insatsvara (råmaterial)":
        st.subheader("Lägg till ny insatsvara")
        with st.form("new_insats_form", clear_on_submit=True):
            next_sl = get_next_sl(data['df_insats'])
            st.info(f"Nästa tillgängliga SI-kod (Sl) är: **{next_sl}**")

            cols = st.columns(2)
            
            # --- Input fields with dynamic options ---
            insats_name = cols[0].text_input("Artikelnamn (Insatsvara)", help=HELP_TEXTS["new_insats_name"])

            # Dynamic options for 'Typ'
            unique_types = sorted(data['df_insats']['Typ'].dropna().unique()) if not data['df_insats'].empty else []
            type_options = unique_types + ["--- Ange ny ---"]
            selected_type = cols[1].selectbox("Typ", options=type_options, help=HELP_TEXTS["new_insats_type"])
            if selected_type == "--- Ange ny ---":
                insats_type = cols[1].text_input("Ange ny typ:", key="new_type_input", help=HELP_TEXTS["new_insats_new_type"])
            else:
                insats_type = selected_type

            vikt_pcs = cols[0].number_input("Vikt/Pcs (om typ är 'g')", min_value=0.0, format="%.2f", help=HELP_TEXTS["new_insats_vikt_pcs"])
            initial_stock = cols[1].number_input("Startsaldo (Antal)", min_value=0.0, step=1.0, help=HELP_TEXTS["new_insats_initial_stock"])
            price = cols[0].number_input("Pris (Kr)", min_value=0.0, format="%.2f", help=HELP_TEXTS["new_insats_price"])

            # Dynamic options for 'Leverantör'
            unique_suppliers = sorted(data['df_insats']['Leverantör'].dropna().unique()) if not data['df_insats'].empty else []
            supplier_options = unique_suppliers + ["--- Ange ny ---"]
            selected_supplier = cols[1].selectbox("Leverantör", options=supplier_options, help=HELP_TEXTS["new_insats_supplier"])
            if selected_supplier == "--- Ange ny ---":
                supplier = cols[1].text_input("Ange ny leverantör:", key="new_supplier_input", help=HELP_TEXTS["new_insats_new_supplier"])
            else:
                supplier = selected_supplier
            # --- End of input fields ---

            if st.form_submit_button("➕ Lägg till i listan", use_container_width=True, type="primary"):
                if not insats_name:
                    st.warning("Artikelnamn får inte vara tomt.")
                else:
                    new_row = [next_sl, insats_name, insats_type, vikt_pcs, initial_stock, price, supplier]
                    st.session_state.insats_basket.append(new_row)
                    st.success(f"✔️ Lade till '{insats_name}' i listan.")
                    st.rerun()

        if st.session_state.insats_basket:
            st.markdown("---")
            st.subheader("Nya insatsvaror att spara")
            df_basket = pd.DataFrame(st.session_state.insats_basket, columns=INSATS_COLUMNS)
            st.dataframe(df_basket, hide_index=True, use_container_width=True)

            secret_key_insats = st.text_input("🔑 Ange säkerhetsnyckel för att spara", type="password", key="secret_insats", help=HELP_TEXTS["new_insats_secret"])
            
            action_cols = st.columns(2)
            if action_cols[0].button("💾 Spara alla till Google Sheets", type="primary", use_container_width=True):
                if not APP_SECRET_KEY:
                    st.error("⚠️ APP_SECRET_KEY är inte definierad i Secrets!")
                elif secret_key_insats.strip() == str(APP_SECRET_KEY).strip():
                    append_rows_to_sheet(SPREADSHEET_NAME, "Insatsvara", st.session_state.insats_basket)
                    st.session_state.insats_basket = []
                    st.cache_data.clear()
                    st.success("✅ Alla nya insatsvaror har registrerats!")
                    st.rerun()
                else:
                    st.error("⛔ Felaktig säkerhetsnyckel.")
            
            if action_cols[1].button("🗑️ Töm listan", use_container_width=True):
                st.session_state.insats_basket = []
                st.rerun()

    # --- Add New Product with BOM ---
    elif add_choice == "Ny färdig produkt (med BOM)":
        st.subheader("Lägg till ny produkt och dess materialförteckning (BOM)")

        with st.form("new_product_form"):
            # --- Product Details ---
            st.markdown("##### Steg 1: Ange produktinformation")
            prod_cols = st.columns(3)
            product_id_input = prod_cols[0].text_input("Produkt-ID (unikt)", help=HELP_TEXTS["new_prod_id"])
            product_name = prod_cols[1].text_input("Produktnamn", help=HELP_TEXTS["new_prod_name"])
            utpris_input = prod_cols[2].number_input("Utpris (kr)", min_value=0.0, format="%.2f", help=HELP_TEXTS["new_prod_utpris"])

            # --- BOM Details ---
            st.markdown("##### Steg 2: Bygg materialförteckningen (BOM)")
            
            if 'bom_components' not in st.session_state:
                st.session_state.bom_components = []

            item_options = {f"{row['Sl']} - {row['Insatsvara']}": row['Sl'] for _, row in data['df_insats'].iterrows()}
            
            bom_cols = st.columns([3, 1, 1, 1])
            selected_item_str = bom_cols[0].selectbox("Välj insatsvara", options=list(item_options.keys()), key="bom_item", help=HELP_TEXTS["new_prod_bom_item"])
            enhet_input = bom_cols[1].text_input("Enhet", value="g", help=HELP_TEXTS["new_prod_bom_unit"])
            forbrukning = bom_cols[2].number_input("Förbrukning", min_value=0.01, step=0.01, key="bom_qty", help=HELP_TEXTS["new_prod_bom_consumption"])
            
            add_component_button = bom_cols[3].form_submit_button("Lägg till komponent")

            if st.session_state.bom_components:
                st.markdown("---")
                st.write("**Valda komponenter:**")
                df_bom_preview = pd.DataFrame(st.session_state.bom_components)
                
                # Display with delete buttons
                for i, component in enumerate(st.session_state.bom_components):
                    cols = st.columns([4, 1])
                    cols[0].text(f"  - {component['Insatsvara']} ({component['Förbrukning']} {component['Enhet']})")
                    if cols[1].form_submit_button("🗑️", key=f"del_comp_{i}", help="Ta bort denna komponent"):
                        st.session_state.bom_components.pop(i)
                        st.rerun()
                
                if st.form_submit_button("🗑️ Rensa hela listan", help="Ta bort alla komponenter från listan"):
                    st.session_state.bom_components = []
                    st.rerun()

            if add_component_button:
                if not product_id_input or not product_name:
                    st.warning("Vänligen ange Produkt-ID och Produktnamn innan du lägger till komponenter.")
                else:
                    sl_code = item_options[selected_item_str]
                    insatsvara_name = selected_item_str.split(' - ', 1)[1]
                    st.session_state.bom_components.append({'Produkt_id': product_id_input, 'SI': sl_code, 'Insatsvara': insatsvara_name, 'Enhet': enhet_input, 'Förbrukning': forbrukning})
                    st.rerun()

            # --- Form Submission ---
            st.markdown("---")
            st.markdown("##### Steg 3: Spara produkt och BOM")
            secret_key_product = st.text_input("🔑 Ange säkerhetsnyckel för att spara", type="password", key="secret_new_product", help=HELP_TEXTS["new_prod_secret"])
            
            save_button = st.form_submit_button("💾 Spara produkt och BOM", type="primary", use_container_width=True)

            if save_button:
                existing_ids = set(data['df_products']['Produkt_id'].astype(str))
                if not product_id_input or not product_name or not st.session_state.bom_components or utpris_input <= 0:
                    st.warning("Du måste ange Produkt-ID, Produktnamn, ett Utpris större än noll och minst en BOM-komponent.")
                elif product_id_input in existing_ids:
                    st.error(f"⛔ Produkt-ID '{product_id_input}' finns redan. Välj ett unikt ID.")
                elif not APP_SECRET_KEY:
                    st.error("⚠️ APP_SECRET_KEY är inte definierad i Secrets!")
                elif secret_key_product.strip() == str(APP_SECRET_KEY).strip():
                    # Logic to save Product and BOM
                    append_rows_to_sheet(SPREADSHEET_NAME, "Products", [[product_id_input, product_name, utpris_input]])
                    bom_rows = [[product_id_input, comp['SI'], comp['Insatsvara'], comp['Enhet'], comp['Förbrukning']] for comp in st.session_state.bom_components]
                    append_rows_to_sheet(SPREADSHEET_NAME, "BOM", bom_rows)
                    
                    st.session_state.bom_components = []
                    st.cache_data.clear()
                    st.success(f"✅ Produkt '{product_name}' (ID: {product_id_input}) och dess BOM har sparats!")
                    # No rerun to show success message
                else:
                    st.error("⛔ Felaktig säkerhetsnyckel.")

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
    
    if isinstance(filtered_df, pd.DataFrame):
        display_df = filtered_df[columns_to_show].copy()
    else:
        display_df = pd.DataFrame(columns=columns_to_show).astype(object)

    if isinstance(display_df, pd.DataFrame):
        display_df.columns = [COLUMN_MAPPING.get(col, col) for col in display_df.columns]

    def style_low_stock(row):
        if row['Aktuellt Saldo'] <= 0:
            return ['background-color: #FFD2D2'] * len(row)
        return [''] * len(row)

    styled_df = display_df.style.apply(style_low_stock, axis=1)

    enhet_options = []
    if not display_df.empty and 'Enhet' in display_df.columns:
        enhet_options = display_df['Enhet'].unique().tolist()

    st.dataframe(
        styled_df,
        column_config={
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

# ------------------- Page 5: Profitability Analysis -------------------
elif selected_page == "💰 Marginaler":
    st.header("💰 Marginaler")

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
                return 'background-color: #FFD2D2' # Red
            elif val < 30:
                return 'background-color: #FFF3CD' # Yellow
            else:
                return 'background-color: #D4EDDA' # Green

        # Prepare the dataframe for styling
        styled_df = display_df.style
        
        # Safely apply styling only if the column exists
        if 'Vinstmarginal (%)' in display_df.columns:
            styled_df = styled_df.applymap(style_margin, subset=['Vinstmarginal (%)'])

        st.dataframe(
            styled_df,
            column_config={
                "Utpris": st.column_config.NumberColumn(format="%.2f kr"),
                "Kostpris": st.column_config.NumberColumn(format="%.2f kr"),
                "Vinstmarginal (%)": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
            },
            use_container_width=True,
            hide_index=True
        )
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.warning("Inga produktdata hittades för att analysera lönsamheten.")