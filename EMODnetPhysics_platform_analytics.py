# -*- coding: utf-8 -*-
"""
EMODnet Physics – Statistics Dashboard
"""

from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
import streamlit as st

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EMODnet Physics · Stats Dashboard",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"], .stApp, div[data-testid="stAppViewContainer"] {
    background-color: #ffffff !important;
    font-family: 'DM Sans', sans-serif;
}

/* Hide sidebar collapse button */
button[data-testid="collapsedControl"] { display: none !important; }

.dash-header {
    background: linear-gradient(135deg, #003d6b 0%, #005f9e 60%, #0080c8 100%);
    border-radius: 12px;
    padding: 2rem 2.4rem 1.6rem;
    margin-bottom: 1.2rem;
    color: #fff;
    position: relative;
    overflow: hidden;
}
.dash-header::before {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 200px; height: 200px;
    background: rgba(255,255,255,0.05);
    border-radius: 50%;
}
.dash-header h1 { 
    font-family: 'Space Mono', monospace; 
    font-size: 2.1rem; 
    margin: 0; 
    letter-spacing: -0.5px; 
}
.dash-header p { 
    margin: .5rem 0 0; 
    opacity: .85; 
    font-size: 1rem; 
}

/* KPI Cards */
.kpi-row { 
    display: flex; 
    gap: 1.2rem; 
    margin-bottom: 1.8rem; 
    flex-wrap: wrap; 
}
.kpi-card {
    flex: 1; 
    min-width: 170px;
    background: #f8fafd;
    border: 1px solid #dce8f5;
    border-left: 5px solid #0080c8;
    border-radius: 10px;
    padding: 1.1rem 1.3rem;
}
.kpi-card .label { 
    font-size: 0.73rem; 
    font-weight: 600; 
    letter-spacing: .1em; 
    text-transform: uppercase; 
    color: #5a7a9a; 
}
.kpi-card .value { 
    font-family: 'Space Mono', monospace; 
    font-size: 2rem; 
    color: #003d6b; 
    font-weight: 700; 
    line-height: 1; 
}
.kpi-card .sub { 
    font-size: 0.78rem; 
    color: #7a9ab8; 
    margin-top: .3rem; 
}

/* Section titles */
.section-title {
    font-family: 'Space Mono', monospace;
    font-size: 1.15rem;
    color: #003d6b;
    border-bottom: 3px solid #0080c8;
    padding-bottom: .5rem;
    margin: 2rem 0 1.2rem;
    letter-spacing: .03em;
}

.badge {
    display: inline-block;
    padding: .25rem .7rem;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: .08em;
    text-transform: uppercase;
    margin-right: .5rem;
}
.badge-erd { background: #e8f4e8; color: #2d7a2d; }
.badge-map { background: #e8eef8; color: #2d4d9a; }
.badge-prod { background: #fef3e2; color: #9a6a00; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def load_platform_metadata() -> pd.DataFrame:
    """Load platform metadata from EMODnet Physics ERDDAP"""
    base = "https://data-erddap.emodnet-physics.eu/erddap/tabledap/EP_PLATFORMS_METADATA_V2.csv?"
    fields = [
        "PLATFORMCODE", "call_name", "latitude", "longitude", "datafeaturetype",
        "firstdateobservation", "lastdateobservation", "platformtypecode",
        "platformtypedescription", "dataownername", "dataownercountryname",
        "integrator", "dataassemblycenter"
    ]
    url = base + "%2C".join(fields)
    df = pd.read_csv(url, skiprows=[1])
    return df

@st.cache_data(show_spinner=False, ttl=1800)
def load_matomo_stats(token: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Load Matomo analytics"""
    if not token:
        st.error("MATOMO_TOKEN not found in secrets!")
        return pd.DataFrame()
    
    url = (
        "https://piwik.vliz.be/index.php?module=API&format=TSV"
        f"&idSite=25&period=range&date={start_date},{end_date}"
        "&method=Actions.getPageUrls&flat=1"
        "&translateColumnNames=1&language=en&showMetadata=0"
        f"&token_auth={token}&filter_limit=-1"
    )
    try:
        df = pd.read_csv(url, sep="\t", encoding="utf-8")
        return df
    except Exception as e:
        st.error(f"Matomo API error: {e}")
        return pd.DataFrame()

def classify_rows(df: pd.DataFrame):
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    erddap_df = df[df["Label"].str.contains("erddap", case=False, na=False)].copy()
    platform_df = df[df["Label"].str.contains("platformid=|platformcode=|platformpage|home", case=False, na=False)].copy()
    prod_df = df[df["Label"].str.contains("EP_MAP", case=False, na=False)].copy()

    erddap_df["category"] = "ERDDAP"
    platform_df["category"] = "MAP"
    prod_df["category"] = "PRODUCT"
    
    return erddap_df, platform_df, prod_df

def kpi(df: pd.DataFrame):
    if df.empty:
        return 0, 0, 0.0
    uv = int(df["Unique Pageviews"].sum()) if "Unique Pageviews" in df.columns else 0
    pv = int(df["Pageviews"].sum()) if "Pageviews" in df.columns else 0
    tt = df["Total time spent by visitors (in seconds)"].mean() if "Total time spent by visitors (in seconds)" in df.columns else 0
    return uv, pv, round(tt or 0, 1)

def kpi_card(label: str, value, sub: str = ""):
    return f"""
    <div class="kpi-card">
        <div class="label">{label}</div>
        <div class="value">{value:,}</div>
        <div class="sub">{sub}</div>
    </div>"""

# ─────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="dash-header">
    <h1>🌊 EMODnet Physics — Stats Dashboard</h1>
    <p>Web interaction analytics • Matomo @ VLIZ • ERDDAP Platform Metadata</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# DATE RANGE
# ─────────────────────────────────────────────────────────────
token = st.secrets.get("MATOMO_TOKEN", "")

today = date.today()
first_last = today.replace(day=1) - relativedelta(months=1)
last_last = today.replace(day=1) - relativedelta(days=1)

st.markdown('<div class="section-title">📅 Date range</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    start_date = st.date_input("Start date", value=first_last)
with col2:
    end_date = st.date_input("End date", value=last_last)
with col3:
    st.markdown("<br>", unsafe_allow_html=True)
    load_btn = st.button("🔄 Refresh Data", use_container_width=True, type="primary")

st.caption(f"**Period:** {start_date.strftime('%d %b %Y')} → {end_date.strftime('%d %b %Y')}")

# ─────────────────────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────────────────────
if load_btn or "platforms" not in st.session_state:
    with st.spinner("Loading platform metadata from ERDDAP..."):
        st.session_state["platforms"] = load_platform_metadata()

if load_btn or "matomo" not in st.session_state:
    with st.spinner("Loading Matomo analytics..."):
        st.session_state["matomo"] = load_matomo_stats(token, str(start_date), str(end_date))

platforms = st.session_state.get("platforms", pd.DataFrame())
matomo = st.session_state.get("matomo", pd.DataFrame())

if matomo.empty:
    st.error("No Matomo data available. Please check your MATOMO_TOKEN in `.streamlit/secrets.toml`")
    st.stop()

erddap_df, platform_df, prod_df = classify_rows(matomo)

# ─────────────────────────────────────────────────────────────
# SECTION 1 – OVERALL KPIs
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📊 Overall Statistics</div>', unsafe_allow_html=True)

uv_all, pv_all, tt_all = kpi(matomo)
uv_erd, pv_erd, tt_erd = kpi(erddap_df)
uv_map, pv_map, tt_map = kpi(platform_df)
uv_pro, pv_pro, tt_pro = kpi(prod_df)

st.markdown(f"""
<div class="kpi-row">
  {kpi_card("Total Unique Pageviews", uv_all, "All categories")}
  {kpi_card("Total Pageviews", pv_all, "All categories")}
  {kpi_card("Avg. Time on Page (s)", tt_all, "All categories")}
</div>
""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown('<span class="badge badge-erd">ERDDAP</span> Data Access', unsafe_allow_html=True)
    st.metric("Unique", f"{uv_erd:,}")
    st.metric("Pageviews", f"{pv_erd:,}")
    st.metric("Avg Time", f"{tt_erd:.1f}s")

with c2:
    st.markdown('<span class="badge badge-map">MAP</span> Platform Explorer', unsafe_allow_html=True)
    st.metric("Unique", f"{uv_map:,}")
    st.metric("Pageviews", f"{pv_map:,}")
    st.metric("Avg Time", f"{tt_map:.1f}s")

with c3:
    st.markdown('<span class="badge badge-prod">PRODUCT</span> EP_MAP', unsafe_allow_html=True)
    st.metric("Unique", f"{uv_pro:,}")
    st.metric("Pageviews", f"{pv_pro:,}")
    st.metric("Avg Time", f"{tt_pro:.1f}s")

# ─────────────────────────────────────────────────────────────
# SECTION 2 – FILTER BY INSTITUTION / PLATFORM
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🔍 Filter by Institution & Platform</div>', unsafe_allow_html=True)

if platforms.empty:
    st.warning("Platform metadata not available.")
else:
    owner_col = "dataownername" if "dataownername" in platforms.columns else None
    country_col = "dataownercountryname" if "dataownercountryname" in platforms.columns else None
    pcode_col = "PLATFORMCODE" if "PLATFORMCODE" in platforms.columns else None

    col_a, col_b = st.columns(2)
    with col_a:
        owners = sorted(platforms[owner_col].dropna().unique()) if owner_col else []
        sel_owners = st.multiselect("Institution", options=owners, placeholder="Select institutions...")
    with col_b:
        countries = sorted(platforms[country_col].dropna().unique()) if country_col else []
        sel_countries = st.multiselect("Country", options=countries, placeholder="Select countries...")

    filtered = platforms.copy()
    if sel_owners and owner_col:
        filtered = filtered[filtered[owner_col].isin(sel_owners)]
    if sel_countries and country_col:
        filtered = filtered[filtered[country_col].isin(sel_countries)]

    if pcode_col:
        codes = sorted(filtered[pcode_col].dropna().unique())
        sel_codes = st.multiselect("Platform Code(s)", options=codes, placeholder="All platforms")
        if sel_codes:
            filtered = filtered[filtered[pcode_col].isin(sel_codes)]

    st.caption(f"**{len(filtered):,} platforms** matching current filters")
    st.dataframe(filtered.head(300), use_container_width=True, height=320)

# ─────────────────────────────────────────────────────────────
# DOWNLOAD SECTION
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">💾 Downloads</div>', unsafe_allow_html=True)

today_str = datetime.today().strftime("%Y%m%d")

col_d1, col_d2, col_d3 = st.columns(3)
with col_d1:
    st.download_button(
        "⬇ Full Matomo Data",
        data=matomo.to_csv(index=False).encode("utf-8"),
        file_name=f"{today_str}_emodnet_physics_matomo_full.csv",
        mime="text/csv",
        use_container_width=True
    )

with col_d2:
    summary = pd.DataFrame([
        {"Category": "ERDDAP", "Unique PV": uv_erd, "Pageviews": pv_erd, "Avg Time(s)": tt_erd},
        {"Category": "MAP", "Unique PV": uv_map, "Pageviews": pv_map, "Avg Time(s)": tt_map},
        {"Category": "PRODUCT", "Unique PV": uv_pro, "Pageviews": pv_pro, "Avg Time(s)": tt_pro},
    ])
    st.download_button(
        "⬇ Summary by Category",
        data=summary.to_csv(index=False).encode("utf-8"),
        file_name=f"{today_str}_emodnet_physics_summary.csv",
        mime="text/csv",
        use_container_width=True
    )

with col_d3:
    if not filtered.empty:
        st.download_button(
            "⬇ Filtered Platforms",
            data=filtered.to_csv(index=False).encode("utf-8"),
            file_name=f"{today_str}_emodnet_physics_filtered.csv",
            mime="text/csv",
            use_container_width=True
        )

st.caption("EMODnet Physics Stats Dashboard • Built for CS-MACH1")
