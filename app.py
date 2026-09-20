import sys
import os
from datetime import date
import pandas as pd  # type: ignore
from pandas.api.types import (
    is_categorical_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
    is_object_dtype,
)
import streamlit as st  # type: ignore
from builtins import Exception

# Ensure imports reference the local modules package to satisfy linters
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
from modules.inventory_engine import calculate_current_stock
from modules.gsheet_connector import load_sheet_data, append_rows_to_sheet

# --- Database & Config Settings ---
SPREADSHEET_NAME = "Inventory_System_DB"

# Safe retrieval of APP_SECRET_KEY from environment variables or Streamlit secrets
def get_app_secret(key, default=None):
    val = os.getenv(key)
    if val:
        return val
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

APP_SECRET_KEY = get_app_secret("APP_SECRET_KEY", None)

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
        "df_products": "Products",
        "df_stickprov": "Stickprov_Log"
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
if 'stickprov_basket' not in st.session_state:
    st.session_state['stickprov_basket'] = []

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

# --- Mobile Detection & Layout Adjustments ---
# Using query parameters as a reliable way to force mobile view during testing (e.g. ?mobile=true)
query_params = st.query_params
force_mobile = query_params.get("mobile", "").lower() == "true"

def is_mobile_device():
    """Detects if the user is accessing from a mobile device using headers or testing parameters."""
    if force_mobile:
        return True
    try:
        user_agent = st.context.headers.get("User-Agent", "").lower()
        mobile_keywords = ["android", "webos", "iphone", "ipad", "ipod", "blackberry", "windows phone", "mobile"]
        return any(keyword in user_agent for keyword in mobile_keywords)
    except Exception:
        return False

is_mobile = is_mobile_device()

# --- Sidebar Navigation ---
if is_mobile:
    selected_page = "📥 Registrera Inleverans"
    # Hide sidebar, header (which contains the hamburger menu), and remove top padding
    st.markdown("""
        <style>
            /* Hide the main Streamlit sidebar and its contents */
            [data-testid="stSidebar"] {display: none !important; visibility: hidden !important;}
            /* Hide the hamburger menu (sidebar expand/collapse button) */
            [data-testid="collapsedControl"] {display: none !important;}
            [data-testid="stSidebarCollapsedControl"] {display: none !important;}
            /* Hide the header completely */
            header[data-testid="stHeader"] {display: none !important;}
            /* Adjust top padding since header is gone */
            .block-container {padding-top: 1rem !important;}
        </style>
    """, unsafe_allow_html=True)
else:
    st.sidebar.title("Navigering")
    nav_options = [
        "📊 Aktuellt Lagersaldo",
        "💰 Marginaler",
        "📥 Registrera Inleverans",
        "🏭 Registrera Daglig Produktion",    
        "📝 Registrera Stickprov",
        "➕ Lägg till ny artikel",
        "📉 Avvikelserapport",
        "📈 Inleveransrapport",
        "⚙️ Inställningar"
    ]
    selected_page = st.sidebar.radio("Välj en sida:", nav_options, index=0)

# ==============================================================================
# PAGE 1: CURRENT STOCK (Aktuellt Lagersaldo)
# ==============================================================================
if selected_page == "📊 Aktuellt Lagersaldo":
    st.header("📊 Aktuellt Lagersaldo")
    
    stock_df = calculate_current_stock(
        data['df_insats'], 
        data['df_bom'], 
        data['df_inbound'], 
        data['df_production'],
        data.get('df_stickprov')
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
        'Vikt/Pcs': 'Mängd/Enhet',
        'Initial_Base_Stock': 'Startsaldo',
        'Total_Inbound': 'Inlevererat',
        'Total_Consumed': 'Förbrukat',
        'Current_Stock': 'Aktuellt Saldo'
    }
    
    columns_to_show = [col for col in COLUMN_MAPPING.keys() if col in filtered_df.columns]
    
    # Create display dataframe
    display_df = filtered_df[columns_to_show].copy() if isinstance(filtered_df, pd.DataFrame) else pd.DataFrame(columns=columns_to_show)
    
    # Convert base unit to item units based on Vikt/Pcs for display
    vikt_per_pcs = pd.to_numeric(filtered_df['Vikt/Pcs'], errors='coerce').fillna(1.0)
    for col in ['Initial_Base_Stock', 'Total_Inbound', 'Total_Consumed', 'Current_Stock']:
        if col in display_df.columns:
            display_df[col] = display_df[col] / vikt_per_pcs

    display_df.columns = [COLUMN_MAPPING.get(col, col) for col in display_df.columns]

    def style_low_stock(row):
        if row['Aktuellt Saldo'] <= 0:
            return ['background-color: #FFD2D2'] * len(row)
        return [''] * len(row)

    styled_df = display_df.style.apply(style_low_stock, axis=1)

    # dynamically format the columns to show the "Typ/Enhet" from the row
    st.dataframe(
        styled_df,
        use_container_width=True,
        column_config={
            "Mängd/Enhet": st.column_config.NumberColumn(format="%,.2f"),
            "Startsaldo": st.column_config.NumberColumn(format="%,.2f"),
            "Inlevererat": st.column_config.NumberColumn(format="%,.2f"),
            "Förbrukat": st.column_config.NumberColumn(format="%,.2f"),
            "Aktuellt Saldo": st.column_config.NumberColumn(format="%,.2f"),
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

        # ---------------------------------------------------------
        # NEW SECTION: Ingredient Visualization (BOM Breakdown)
        # ---------------------------------------------------------
        st.markdown("### 🔍 Analys av produktens ingredienser")
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        
        # Dropdown for selecting a product
        product_options = margin_df['Produkt_namn'].tolist()
        selected_product_name = st.selectbox("Välj produkt för att se fördelning av kostnader:", product_options)
        
        if selected_product_name:
            selected_product_id = margin_df[margin_df['Produkt_namn'] == selected_product_name]['Produkt_id'].values[0]
            
            # Filter BOM and Insats data
            df_bom = data['df_bom'].copy()
            df_bom['Produkt_id'] = df_bom['Produkt_id'].astype(str)
            prod_bom = df_bom[df_bom['Produkt_id'] == str(selected_product_id)].copy()
            
            if not prod_bom.empty:
                df_insats = data['df_insats'].copy()
                df_insats['Sl'] = df_insats['Sl'].astype(str)
                
                # Merge BOM with Raw Materials to get prices
                merged_bom = pd.merge(prod_bom, df_insats[['Sl', 'Insatsvara', 'Vikt/Pcs', 'Pris (Kr)', 'Typ']], left_on='SI', right_on='Sl', how='left')
                
                # Calculate costs for each ingredient
                merged_bom['Vikt/Pcs'] = pd.to_numeric(merged_bom['Vikt/Pcs'], errors='coerce').fillna(1.0)
                merged_bom['Pris (Kr)'] = pd.to_numeric(merged_bom['Pris (Kr)'], errors='coerce').fillna(0.0)
                merged_bom['Förbrukning'] = pd.to_numeric(merged_bom['Förbrukning'], errors='coerce').fillna(0.0)
                
                # Logic to calculate base price per unit
                merged_bom['Enhetspris'] = merged_bom['Pris (Kr)'] / merged_bom['Vikt/Pcs']
                merged_bom['Total Kostnad'] = merged_bom['Förbrukning'] * merged_bom['Enhetspris']
                
                # Layout: Table on the left, Chart on the right
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.markdown("##### 📋 Recept / Innehåll")
                    
                    # Both dataframes might have had an 'Insatsvara' column before merge.
                    # pandas typically renames them to 'Insatsvara_x' and 'Insatsvara_y' 
                    # We dynamically check which one is available.
                    insats_col_name = 'Insatsvara_y' if 'Insatsvara_y' in merged_bom.columns else ('Insatsvara_x' if 'Insatsvara_x' in merged_bom.columns else 'Insatsvara')
                    
                    display_bom = merged_bom[[insats_col_name, 'Förbrukning', 'Enhet', 'Total Kostnad']].copy()
                    display_bom.rename(columns={insats_col_name: 'Ingrediens'}, inplace=True)
                    
                    st.dataframe(
                        display_bom,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Förbrukning": st.column_config.NumberColumn(format="%,.2f"),
                            "Total Kostnad": st.column_config.NumberColumn(format="%.2f kr")
                        }
                    )
                
                with col2:
                    st.markdown("##### 📊 Kostnadsfördelning")
                    import plotly.express as px # type: ignore
                    import plotly.graph_objects as go # type: ignore
                    
                    # Ensure utpris is numeric
                    utpris_val = float(margin_df[margin_df['Produkt_id'] == selected_product_id]['Utpris'].values[0])
                    total_cost = merged_bom['Total Kostnad'].sum()
                    margin_val = utpris_val - total_cost
                    margin_pct = (margin_val / utpris_val * 100) if utpris_val > 0 else 0
                    
                    # We create a donut chart where the pieces are ingredients, 
                    # and we add an extra piece for the "Margin" (Vinst) so the total pie = Utpris
                    
                    # Prepare data for plotting
                    plot_data = merged_bom[[insats_col_name, 'Total Kostnad']].copy()
                    plot_data.rename(columns={insats_col_name: 'Kategori', 'Total Kostnad': 'Värde'}, inplace=True)
                    
                    # Append Margin as a slice if Utpris > Total Cost
                    if margin_val > 0:
                        margin_row = pd.DataFrame([{'Kategori': 'Vinst (Marginal)', 'Värde': margin_val}])
                        plot_data = pd.concat([plot_data, margin_row], ignore_index=True)
                    
                    # Set colors: Pastel colors for ingredients, distinct green for Margin
                    colors = px.colors.qualitative.Pastel
                    color_map = {row['Kategori']: colors[i % len(colors)] for i, row in plot_data.iterrows() if row['Kategori'] != 'Vinst (Marginal)'}
                    color_map['Vinst (Marginal)'] = '#D4EDDA' # Light green for profit
                    
                    fig = px.pie(
                        plot_data, 
                        values='Värde', 
                        names='Kategori', 
                        hole=0.55,
                        color='Kategori',
                        color_discrete_map=color_map
                    )
                    
                    # Add central text showing Utpris and Margin %
                    fig.update_layout(
                        margin=dict(t=0, b=0, l=0, r=0),
                        annotations=[dict(text=f"<b>Utpris</b><br>{utpris_val:.2f} kr<br><span style='color:#0E4722; font-size:12px;'>Marginal: {margin_pct:.1f}%</span>", x=0.5, y=0.5, font_size=16, showarrow=False)]
                    )
                    
                    # Format hover info
                    fig.update_traces(hovertemplate='<b>%{label}</b><br>Belopp: %{value:.2f} kr<br>Andel av utpris: %{percent}<extra></extra>')
                    
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Ingen BOM (recept) hittades för denna produkt.")
                
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# PAGE 3: REGISTER INBOUND (Registrera Inleverans)
# ==============================================================================
elif selected_page == "📥 Registrera Inleverans":
    st.header("📥 Registrera Inleverans av Varor")
    st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
    
    with st.form("inbound_form", clear_on_submit=True):
        col1, col2 = st.columns([2, 3])
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
            
        unique_suppliers = sorted(data['df_insats']['Leverantör'].dropna().unique()) if not data['df_insats'].empty else []
        
        col_sup, col_qty = st.columns([3, 2])
        
        with col_sup:
            default_supplier = selected_item.get('Leverantör', '')
            supplier_options = unique_suppliers
            
            final_supplier = st.selectbox(
                "Leverantör", 
                options=supplier_options, 
                index=supplier_options.index(default_supplier) if default_supplier in supplier_options else 0,
                key="inbound_supplier_select",
                help="Välj vilken leverantör denna inleverans kommer ifrån"
            )
            
        with col_qty:
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
                # If they opened the text field but wrote nothing, default back to original or blank
                if not final_supplier:
                    final_supplier = "Okänd"
                new_row = [str(entry_date), str(selected_item['Sl']), selected_item['Insatsvara'], pkg_qty, total_base, final_supplier]
                st.session_state.inbound_basket.append(new_row)
                st.rerun()
                
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.inbound_basket:
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        st.subheader("Poster att spara")
        for i, row in enumerate(st.session_state.inbound_basket):
            row_cols = st.columns([2, 1, 3, 1, 2, 2, 1])
            row_cols[0].write(row[0]) # Date
            row_cols[1].write(row[1]) # SI
            row_cols[2].write(row[2]) # Artikel
            row_cols[3].write(row[3]) # Qty
            row_cols[4].write(f"{row[4]:,.2f}g") # Base Qty
            
            # Handling older basket items that might not have a supplier appended
            if len(row) > 5:
                row_cols[5].write(row[5]) # Supplier
            else:
                row_cols[5].write("-")
                
            if row_cols[6].button("🗑️", key=f"del_inbound_{i}"):
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
        
        # اطمینان از اینکه شناسه‌ها در نقشه نام‌ها حتماً رشته هستند
        if not df_products_copy.empty and 'Produkt_id' in df_products_copy.columns:
            df_products_copy['Produkt_id'] = df_products_copy['Produkt_id'].astype(str).str.strip()
            product_name_map = df_products_copy.set_index('Produkt_id')['Produkt_namn'].to_dict()
        else:
            product_name_map = {}

        with col2:
            # تبدیل pid به رشته و حذف فاصله‌ها برای جستجوی دقیق
            product_options = {
                f"{str(pid).strip()} - {product_name_map.get(str(pid).strip(), 'Okänd')}": pid 
                for pid in unique_product_ids
            }
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
# PAGE: REGISTER STICKPROV (Registrera Stickprov)
# ==============================================================================
elif selected_page == "📝 Registrera Stickprov":
    st.header("📝 Registrera Stickprov (Lagerinventering)")
    st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
    
    # Calculate live stock to show system stock
    live_stock = calculate_current_stock(
        data['df_insats'], data['df_bom'], data['df_inbound'], data['df_production'], data.get('df_stickprov')
    )

    with st.form("stickprov_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            entry_date = st.date_input("Datum", date.today())
            
            # Select Item
            if not live_stock.empty:
                item_options = {f"{row['Sl']} - {row['Insatsvara']}": str(row['Sl']) for _, row in live_stock.iterrows()}
                selected_item_label = st.selectbox("Välj artikel / SI-kod", options=list(item_options.keys()))
                selected_si = item_options[selected_item_label]
                
                # Get Current System Stock Base Amount
                item_data = live_stock[live_stock['Sl'] == selected_si].iloc[0]
                sys_stock_base = item_data['Current_Stock']
                vikt_pcs = item_data['Vikt/Pcs'] if pd.notna(item_data['Vikt/Pcs']) and item_data['Vikt/Pcs'] > 0 else 1.0
                sys_stock_display = sys_stock_base / vikt_pcs
                typ_enhet = item_data['Typ']
                
                st.info(f"Systemsaldo: **{sys_stock_display:,.2f} {typ_enhet}**")
            else:
                st.warning("Inga artiklar hittades.")
                selected_si = None
            
        with col2:
            actual_stock = st.number_input("Faktiskt saldo (fysiskt)", min_value=0.0, step=1.0)
            note = st.text_input("Anmärkning / Orsak (frivilligt)")
            
        if st.form_submit_button("➕ Lägg till", type="primary"):
            if selected_si is not None:
                actual_stock_base = actual_stock * vikt_pcs
                deviation_base = actual_stock_base - sys_stock_base
                
                artikel_namn = selected_item_label.split(" - ")[1]
                st.session_state.stickprov_basket.append([
                    str(entry_date), selected_si, artikel_namn, sys_stock_base, actual_stock_base, deviation_base, note
                ])
                st.rerun()
                
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.stickprov_basket:
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        st.subheader("Stickprov att spara")
        for i, row in enumerate(st.session_state.stickprov_basket):
            row_cols = st.columns([2, 1, 3, 2, 2, 2, 2, 1])
            row_cols[0].write(row[0]) # Date
            row_cols[1].write(row[1]) # SI
            row_cols[2].write(row[2]) # Artikel
            # Display deviations in base unit for accuracy, could be divided by vikt_pcs for display if preferred
            row_cols[3].write(f"Sys: {row[3]:,.1f}") 
            row_cols[4].write(f"Fys: {row[4]:,.1f}")
            
            dev = row[5]
            dev_color = "red" if dev < 0 else "green" if dev > 0 else "black"
            row_cols[5].markdown(f"<span style='color:{dev_color}; font-weight:bold;'>Avv: {dev:,.1f}</span>", unsafe_allow_html=True)
            
            row_cols[6].write(row[6]) # Note
            if row_cols[7].button("🗑️", key=f"del_stickprov_{i}"):
                st.session_state.stickprov_basket.pop(i)
                st.rerun()

        secret_key_stickprov = st.text_input("🔑 Säkerhetsnyckel", type="password", key="secret_stickprov")
        action_cols = st.columns(2)
        if action_cols[0].button("💾 Spara alla", type="primary"):
            if secret_key_stickprov.strip() == str(APP_SECRET_KEY).strip():
                append_rows_to_sheet(SPREADSHEET_NAME, "Stickprov_Log", st.session_state.stickprov_basket)
                st.session_state.stickprov_basket = []
                st.cache_data.clear()
                st.success("✅ Stickprov registrerades och lagersaldot har uppdaterats!")
                st.rerun()
            else:
                st.error("⛔ Felaktig nyckel.")
            
        if action_cols[1].button("🗑️ Töm listan"):
            st.session_state.stickprov_basket = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# PAGE: DEVIATION REPORT (Avvikelserapport)
# ==============================================================================
elif selected_page == "📉 Avvikelserapport":
    st.header("📉 Avvikelserapport (Stickprov Analys)")
    
    df_stickprov = data.get('df_stickprov')
    
    if df_stickprov is None or df_stickprov.empty:
        st.warning("Det finns ingen data om stickprov ännu. Registrera ett stickprov först.")
    else:
        # کپی گرفتن و تمیز کردن داده‌ها
        df_dev = df_stickprov.copy()
        
        # اطمینان از اینکه تاریخ‌ها در فرمت مناسب هستند
        df_dev['Datum'] = pd.to_datetime(df_dev['Datum'], errors='coerce')
        df_dev = df_dev.dropna(subset=['Datum'])
        
        # تبدیل مقادیر عددی
        for col in ['System_Stock', 'Actual_Stock', 'Deviation']:
            if col in df_dev.columns:
                df_dev[col] = pd.to_numeric(df_dev[col], errors='coerce').fillna(0.0)
                
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        
        # فیلتر تاریخ
        min_date = df_dev['Datum'].min().date() if not df_dev.empty else date.today()
        max_date = df_dev['Datum'].max().date() if not df_dev.empty else date.today()
        
        filter_col, _, _ = st.columns([1, 1, 1])
        date_range = filter_col.date_input("📅 Välj tidsperiod", [min_date, max_date])
        
        if len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = date_range[0], date_range[0]
            
        # اعمال فیلتر زمانی
        mask = (df_dev['Datum'].dt.date >= start_date) & (df_dev['Datum'].dt.date <= end_date)
        filtered_df = df_dev[mask].copy()
        
        # KPIs
        # For financial values, we merge with df_insats to get the price per unit
        df_insats = data.get('df_insats', pd.DataFrame())
        
        if not df_insats.empty and 'Sl' in df_insats.columns and 'Pris (Kr)' in df_insats.columns:
            df_insats_prices = df_insats[['Sl', 'Pris (Kr)', 'Vikt/Pcs']].copy()
            df_insats_prices['Sl'] = df_insats_prices['Sl'].astype(str)
            filtered_df['SI_Code'] = filtered_df['SI_Code'].astype(str)
            
            merged_dev = pd.merge(filtered_df, df_insats_prices, left_on='SI_Code', right_on='Sl', how='left')
            
            # Calculate Base Price (price per base unit, e.g., per gram if Vikt/Pcs exists)
            merged_dev['Vikt/Pcs'] = pd.to_numeric(merged_dev['Vikt/Pcs'], errors='coerce').fillna(1.0)
            merged_dev['Pris (Kr)'] = pd.to_numeric(merged_dev['Pris (Kr)'], errors='coerce').fillna(0.0)
            merged_dev['Base_Price'] = merged_dev['Pris (Kr)'] / merged_dev['Vikt/Pcs']
            
            # Calculate Financial Deviation
            merged_dev['Financial_Deviation'] = merged_dev['Deviation'] * merged_dev['Base_Price']
            
            total_shortage_val = merged_dev[merged_dev['Deviation'] < 0]['Financial_Deviation'].sum()
            total_surplus_val = merged_dev[merged_dev['Deviation'] > 0]['Financial_Deviation'].sum()
        else:
            total_shortage_val = 0.0
            total_surplus_val = 0.0
            
        total_checks = len(filtered_df)
        
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Antal kontroller", total_checks)
        kpi2.metric("Värde av svinn (Negativ)", f"{total_shortage_val:,.2f} Kr")
        kpi3.metric("Värde av överskott (Positiv)", f"{total_surplus_val:,.2f} Kr")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # گرافیک و جدول
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        st.subheader("Avvikelser per artikel")
        
        if not filtered_df.empty:
            # محاسبه مجموع انحراف برای هر کالا
            agg_df = filtered_df.groupby('Artikel')['Deviation'].sum().reset_index()
            # مرتب‌سازی برای نمایش بهتر
            agg_df = agg_df.sort_values(by='Deviation')
            
            # Use Plotly for custom coloring based on positive/negative values
            import plotly.express as px # type: ignore
            
            fig = px.bar(
                agg_df, 
                x='Artikel', 
                y='Deviation',
                color='Deviation',
                color_continuous_scale=[(0, '#D32F2F'), (0.5, '#D32F2F'), (0.5, '#388E3C'), (1, '#388E3C')],
                color_continuous_midpoint=0
            )
            fig.update_layout(
                showlegend=False,
                coloraxis_showscale=False,
                margin=dict(l=20, r=20, t=20, b=20),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            fig.update_traces(hovertemplate='<b>%{x}</b><br>Avvikelse: %{y:,.2f}<extra></extra>')
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Inga avvikelser hittades i den valda perioden.")
            
        st.markdown('</div>', unsafe_allow_html=True)
        
        # جدول کامل لاگ‌ها
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        st.subheader("Historik för stickprov")
        
        if not filtered_df.empty:
            if 'Financial_Deviation' in merged_dev.columns:
                # Need to ensure Datum is the same type in both before merging
                filtered_df['Datum'] = pd.to_datetime(filtered_df['Datum'])
                merged_dev['Datum'] = pd.to_datetime(merged_dev['Datum'])
                
                filtered_df = pd.merge(
                    filtered_df, 
                    merged_dev[['Datum', 'SI_Code', 'Financial_Deviation', 'Vikt/Pcs']], 
                    on=['Datum', 'SI_Code'], 
                    how='left'
                ).drop_duplicates()
                
            # فرمت تاریخ برای نمایش
            filtered_df['Datum'] = filtered_df['Datum'].dt.strftime('%Y-%m-%d')
            
            # تبدیل انحراف به کیلوگرم (با فرض اینکه انحراف به گرم ثبت شده است)
            def calculate_display_dev(row):
                # If deviation is based on pieces/pkgs, it remains as is, but typically weight based items are in 'g'
                return row['Deviation'] / 1000.0
                
            filtered_df['Deviation'] = filtered_df.apply(calculate_display_dev, axis=1)
            filtered_df['System_Stock'] = filtered_df['System_Stock'] / 1000.0
            filtered_df['Actual_Stock'] = filtered_df['Actual_Stock'] / 1000.0

            def style_deviation(val):
                try:
                    v = float(val)
                    if v < 0:
                        return 'color: #D32F2F; font-weight: bold;'
                    elif v > 0:
                        return 'color: #388E3C; font-weight: bold;'
                    return ''
                except:
                    return ''
            
            def style_money(val):
                try:
                    v = float(val)
                    if v < 0:
                        return 'color: #D32F2F; font-weight: bold;'
                    elif v > 0:
                        return 'color: #388E3C; font-weight: bold;'
                    return ''
                except:
                    return ''

            display_cols = ['Datum', 'SI_Code', 'Artikel', 'System_Stock', 'Actual_Stock', 'Deviation', 'Financial_Deviation', 'Note']
            existing_cols = [c for c in display_cols if c in filtered_df.columns]
            
            st.dataframe(
                filtered_df[existing_cols].style.map(style_deviation, subset=['Deviation']).map(style_money, subset=['Financial_Deviation'] if 'Financial_Deviation' in existing_cols else []),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "System_Stock": st.column_config.NumberColumn("Systemsaldo (kg/st)", format="%,.3f"),
                    "Actual_Stock": st.column_config.NumberColumn("Fysiskt saldo (kg/st)", format="%,.3f"),
                    "Deviation": st.column_config.NumberColumn("Avvikelse (kg/st)", format="%,.3f"),
                    "Financial_Deviation": st.column_config.NumberColumn("Värde (Kr)", format="%,.2f kr"),
                    "SI_Code": st.column_config.TextColumn("SI-kod"),
                    "Note": st.column_config.TextColumn("Anmärkning")
                }
            )
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
            base_next_sl = get_next_sl(data['df_insats'])
            # افزودن تعداد آیتم‌های موجود در سبد برای تولید شناسه جدید و جلوگیری از تکرار
            next_sl = base_next_sl + len(st.session_state.insats_basket)
            st.info(f"Nästa tillgängliga SI-kod (Sl): **{next_sl}**")

            cols = st.columns(2)
            insats_name = cols[0].text_input("Artikelnamn", help=HELP_TEXTS["new_insats_name"])

            unique_types = sorted(data['df_insats']['Typ'].dropna().unique()) if not data['df_insats'].empty else []
            selected_type = cols[1].selectbox("Typ (välj befintlig)", options=unique_types, help=HELP_TEXTS["new_insats_type"])
            insats_type_new = cols[1].text_input("Eller skriv in ny typ:", help="Fyll i denna om du vill skapa en ny typ")
            
            insats_type = insats_type_new.strip() if insats_type_new.strip() else selected_type

            vikt_pcs = cols[0].number_input("Vikt/Pcs (om typ är 'g')", min_value=0.0, format="%.2f", help=HELP_TEXTS["new_insats_vikt_pcs"])
            initial_stock = cols[1].number_input("Startsaldo", min_value=0.0, step=1.0, help=HELP_TEXTS["new_insats_initial_stock"])
            price = cols[0].number_input("Pris (Kr)", min_value=0.0, format="%.2f", help=HELP_TEXTS["new_insats_price"])

            unique_suppliers = sorted(data['df_insats']['Leverantör'].dropna().unique()) if not data['df_insats'].empty else []
            selected_supplier = cols[1].selectbox("Leverantör (välj befintlig)", options=unique_suppliers, help=HELP_TEXTS["new_insats_supplier"])
            supplier_new = cols[1].text_input("Eller skriv in ny leverantör:", help="Fyll i denna om du vill lägga till en ny leverantör")
            
            supplier = supplier_new.strip() if supplier_new.strip() else selected_supplier

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
            
            st.markdown("<h6 style='margin-top: -20px; margin-bottom: 10px;'>📋 Valda Komponenter i Receptet</h6>", unsafe_allow_html=True)

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

# ==============================================================================
# PAGE 6: INBOUND REPORT (Inleveransrapport)
# ==============================================================================
elif selected_page == "📈 Inleveransrapport":
    st.header("📈 Rapport: Inleveransanalys")
    
    df_inbound = data['df_inbound'].copy()
    df_insats = data['df_insats'].copy()
    
    if df_inbound.empty or df_insats.empty:
        st.warning("Ingen inleveransdata tillgänglig för analys.")
    else:
        # تغییر نام ستون‌ها با توجه به ایندکس برای اطمینان از یکپارچگی
        has_inbound_supplier = len(df_inbound.columns) >= 6
        if has_inbound_supplier:
            # We assume column 6 is the Supplier, taking first 6 cols
            df_inbound = df_inbound.iloc[:, :6].copy()
            df_inbound.columns = ['Datum', 'SI_Code', 'Artikel', 'Antal_Förpackningar', 'Total_Basmängd', 'Leverantör_Inbound']
        else:
            df_inbound = df_inbound.iloc[:, :5].copy()
            df_inbound.columns = ['Datum', 'SI_Code', 'Artikel', 'Antal_Förpackningar', 'Total_Basmängd']
            
        # تبدیل فرمت‌ها و ترکیب (Join) داده‌های ورودی با داده‌های کالاها
        df_inbound['SI_Code'] = df_inbound['SI_Code'].astype(str)
        df_insats['Sl'] = df_insats['Sl'].astype(str)
        
        # Only merge Supplier from Insats if it's not present in Inbound log
        merge_cols = ['Sl', 'Typ', 'Pris (Kr)']
        if not has_inbound_supplier:
            merge_cols.append('Leverantör')
            
        merged_df = pd.merge(
            df_inbound, 
            df_insats[merge_cols], 
            left_on='SI_Code', 
            right_on='Sl', 
            how='left'
        )
        
        # Resolve Supplier column
        if has_inbound_supplier:
            merged_df['Leverantör'] = merged_df['Leverantör_Inbound']
            merged_df = merged_df.drop(columns=['Leverantör_Inbound'])
        
        # محاسبه مبلغ 
        merged_df['Antal_Förpackningar'] = pd.to_numeric(merged_df['Antal_Förpackningar'], errors='coerce').fillna(0)
        merged_df['Pris (Kr)'] = pd.to_numeric(merged_df['Pris (Kr)'], errors='coerce').fillna(0)
        merged_df['Totalt_Belopp'] = merged_df['Antal_Förpackningar'] * merged_df['Pris (Kr)']
        
        # مدیریت فرمت تاریخ
        merged_df['Datum'] = pd.to_datetime(merged_df['Datum'], errors='coerce')
        
        st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
        
        min_date = merged_df['Datum'].min()
        max_date = merged_df['Datum'].max()
        
        # ردیف اول: فیلتر تاریخ
        if pd.isna(min_date) or pd.isna(max_date):
            start_date, end_date = date.today(), date.today()
        else:
            c_date, _, _ = st.columns([1, 1, 1])
            date_range = c_date.date_input("📅 Period", [min_date, max_date], help="Filtrera på datum")
            if len(date_range) == 2:
                start_date, end_date = date_range
            else:
                start_date, end_date = date_range[0], date_range[0]
                
        # اعمال فیلتر تاریخ (برای اینکه گزینه‌های بعدی بصورت آبشاری آپدیت شوند)
        mask_date = (merged_df['Datum'].dt.date >= start_date) & (merged_df['Datum'].dt.date <= end_date)
        filtered_df = merged_df[mask_date].copy()
        
        st.markdown("<hr style='margin: 0.5em 0; border-color: #DDD7C0;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 0.85em; color: #146331; font-weight: bold; margin-bottom: 0.5em;'>🔍 Kolumnfilter (Välj 'Alla' för att visa alla)</div>", unsafe_allow_html=True)
        
        # ردیف دوم: فیلترهای کالا و تامین‌کننده چسبیده به جدول (با استفاده از دراپ‌دان چندگانه و رادیوباتن افقی)
        
        artiklar_options = filtered_df['Artikel'].dropna().unique().tolist()
        selected_artiklar = st.multiselect("📦 Artikel", options=artiklar_options, default=[], help="Lämna tomt för att visa alla")
        if selected_artiklar:
            filtered_df = filtered_df[filtered_df['Artikel'].isin(selected_artiklar)]
            
        suppliers_options = ["Alla"] + filtered_df['Leverantör'].dropna().unique().tolist()
        selected_supplier = st.radio("🏢 Leverantör", options=suppliers_options, index=0, horizontal=True)
        if selected_supplier != "Alla":
            filtered_df = filtered_df[filtered_df['Leverantör'] == selected_supplier]
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # کارت‌های آمار بر اساس فیلترهای نهایی
        m1, m2 = st.columns(2)
        m1.metric("Totalt Antal Förpackningar", f"{filtered_df['Antal_Förpackningar'].sum():,.2f}")
        m2.metric("Totalt Värde / Belopp", f"{filtered_df['Totalt_Belopp'].sum():,.2f} Kr")
        
        # مدیریت فرمت تاریخ برای نمایش در جدول
        filtered_df['Datum'] = filtered_df['Datum'].dt.strftime('%Y-%m-%d')
        
        display_columns = ['Datum', 'Artikel', 'Typ', 'Leverantör', 'Antal_Förpackningar', 'Pris (Kr)', 'Totalt_Belopp']
        
        st.dataframe(
            filtered_df[display_columns], 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Antal_Förpackningar": st.column_config.NumberColumn(format="%,.2f"),
                "Pris (Kr)": st.column_config.NumberColumn(format="%,.2f"),
                "Totalt_Belopp": st.column_config.NumberColumn(format="%,.2f"),
            }
        )

# ==============================================================================
# PAGE 7: SETTINGS (Inställningar) - Cache Management
# ==============================================================================
elif selected_page == "⚙️ Inställningar":
    st.header("⚙️ Inställningar & Underhåll")
    st.markdown('<div class="smartlager-card">', unsafe_allow_html=True)
    
    st.subheader("Rensa Appens Cache")
    st.write("Om du upplever att appen inte visar den senaste datan från Google Sheets (t.ex. efter att du har ändrat något direkt i arket), kan du tvinga appen att hämta ny data genom att rensa cachen.")
    
    if st.button("🔄 Rensa Cache & Uppdatera Data", type="primary"):
        # Clear Streamlit's data cache
        st.cache_data.clear()
        
        # Clear session state variables that might hold old data/baskets
        keys_to_clear = ['inbound_basket', 'production_basket', 'insats_basket', 'bom_components', 'stickprov_basket']
        for key in keys_to_clear:
            if key in st.session_state:
                st.session_state[key] = []
                
        st.success("✅ Cachen har rensats! Appen hämtar nu den senaste datan.")
        # Rerun to immediately fetch fresh data
        st.rerun()
        
    st.markdown('</div>', unsafe_allow_html=True)