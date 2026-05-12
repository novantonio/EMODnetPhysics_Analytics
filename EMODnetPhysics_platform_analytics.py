# -*- coding: utf-8 -*-
"""
EMODnet Physics – Interaction Statistics Dashboard
Streamlit app for exploring Matomo web analytics + platform metadata.
"""

import io
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

import pandas as pd
import requests
import streamlit as st

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EMODnet Physics · Stats Dashboard",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }

/* Header */
.dash-header {
    background: linear-gradient(135deg, #003d6b 0%, #005f9e 60%, #0080c8 100%);
    border-radius: 12px;
    padding: 2rem 2.4rem 1.6rem;
    margin-bottom: 1.8rem;
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
.dash-header h1 { font-family: 'Space Mono', monospace; font-size: 1.9rem; margin: 0; letter-spacing: -0.5px; }
.dash-header p  { margin: .4rem 0 0; opacity: .8; font-size: .95rem; font-weight: 300; }

/* KPI cards */
.kpi-row { display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
.kpi-card {
    flex: 1; min-width: 160px;
    background: #f7fafd;
    border: 1px solid #dce8f5;
    border-left: 4px solid #0080c8;
    border-radius: 10px;
    padding: 1rem 1.2rem;
}
.kpi-card .label { font-size: .72rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #5a7a9a; }
.kpi-card .value { font-family: 'Space Mono', monospace; font-size: 1.8rem; color: #003d6b; font-weight: 700; line-height: 1.1; }
.kpi-card .sub   { font-size: .75rem; color: #7a9ab8; margin-top: .2rem; }

/* Section headers */
.section-title {
    font-family: 'Space Mono', monospace;
    font-size: 1rem;
    color: #003d6b;
    border-bottom: 2px solid #0080c8;
    padding-bottom: .4rem;
    margin: 1.8rem 0 1rem;
    letter-spacing: .02em;
}

/* Source badge */
.badge {
    display: inline-block;
    padding: .2rem .6rem;
    border-radius: 4px;
    font-size: .7rem;
    font-weight: 700;
    letter-spacing: .06em;
    text-transform: uppercase;
    margin-right: .4rem;
}
.badge-erd  { background: #e8f4e8; color: #2d7a2d; }
.badge-map  { background: #e8eef8; color: #2d4d9a; }
.badge-prod { background: #fef3e2; color: #9a6a00; }

/* Download btn override */
div[data-testid="stDownloadButton"] > button {
    background: #003d6b;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-family: 'Space Mono', monospace;
    font-size: .82rem;
    padding: .55rem 1.4rem;
    transition: background .2s;
}
div[data-testid="stDownloadButton"] > button:hover { background: #0080c8; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_platform_metadata() -> pd.DataFrame:
    """Download platform metadata from EMODnet ERDDAP."""
    fields = [
        "PLATFORMCODE", "call_name", "id", "wmo",
        "latitude", "longitude", "datafeaturetype",
        "firstdateobservation", "lastdateobservation",
        "p33_watertemperature", "p33_currents", "p33_optical",
        "p33_river", "p33_sealevel", "p33_waves", "p33_winds",
        "p33_biochemical", "p33_carbonsystem", "p33_dissolvedoxygen",
        "p33_seaice", "p33_underwatersound", "p33_watersalinity",
        "p33_meteorological",
        "best_practices_doi", "data_doi", "dataassemblycenter",
        "platformtypecode", "platformtypedescription",
        "dataownername", "dataownercountrycod", "dataownercountryname",
        "integrator_id", "integrator",
        "creationdate", "updatedate", "datafiles",
    ]
    base = "https://data-erddap.emodnet-physics.eu/erddap/tabledap/EP_PLATFORMS_METADATA_V2.csv?"
    url = base + "%2C".join(fields)
    df = pd.read_csv(url, skiprows=[1])
    return df


@st.cache_data(show_spinner=False)
def load_matomo_stats(token: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Download page-URL stats from Matomo/Piwik."""
    url = (
        "https://piwik.vliz.be/index.php?module=API&format=TSV"
        "&idSite=25&period=range"
        f"&date={start_date},{end_date}"
        "&method=Actions.getPageUrls&flat=1"
        "&translateColumnNames=1&language=en&showMetadata=0"
        f"&token_auth={token}&filter_limit=-1"
    )
    df = pd.read_csv(url, sep="\t", encoding="utf-16")
    cols = [
        "Label",
        "Unique Pageviews",
        "Pageviews",
        "Total time spent by visitors (in seconds)",
        "nb_hits_with_time_network",
    ]
    existing = [c for c in cols if c in df.columns]
    return df[existing]


def classify_rows(df: pd.DataFrame):
    """Split Matomo rows into ERDDAP / MAP / PRODUCT sub-frames."""
    erddap_df   = df[df["Label"].str.contains("erddap", case=False, na=False)].copy()
    platform_df = df[df["Label"].str.contains(
        "platformid=|platformcode=|platformpage|home", case=False, na=False
    )].copy()
    prod_df     = df[df["Label"].str.contains("EP_MAP", case=False, na=False)].copy()

    erddap_df["category"]   = "ERDDAP"
    platform_df["category"] = "MAP"
    prod_df["category"]     = "PRODUCT"
    return erddap_df, platform_df, prod_df


def kpi(df: pd.DataFrame):
    uv = int(df["Unique Pageviews"].sum()) if "Unique Pageviews" in df.columns else 0
    pv = int(df["Pageviews"].sum()) if "Pageviews" in df.columns else 0
    tt = df["Total time spent by visitors (in seconds)"].mean() if "Total time spent by visitors (in seconds)" in df.columns else 0
    return uv, pv, round(tt or 0, 1)


def kpi_card(label: str, value, sub: str = "") -> str:
    return f"""
    <div class="kpi-card">
        <div class="label">{label}</div>
        <div class="value">{value:,}</div>
        <div class="sub">{sub}</div>
    </div>"""


# ─────────────────────────────────────────────────────────────
# SIDEBAR – CONFIGURATION
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")

    token = st.text_input(
        "Matomo token_auth",
        value=st.secrets.get("MATOMO_TOKEN", ""),
        type="password",
        help="Loaded from .streamlit/secrets.toml (MATOMO_TOKEN). You can override it here.",
    )

    # Default: last complete calendar month
    today = date.today()
    first_last = (today.replace(day=1) - relativedelta(months=1))
    last_last  = today.replace(day=1) - relativedelta(days=1)

    col_a, col_b = st.columns(2)
    start_date = col_a.date_input("Start date", value=first_last)
    end_date   = col_b.date_input("End date",   value=last_last)

    load_btn = st.button("🔄 Load / Refresh data", use_container_width=True)

    st.markdown("---")
    st.caption("Data sources: EMODnet ERDDAP · Matomo/Piwik @ VLIZ")


# ─────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="dash-header">
    <h1>🌊 EMODnet Physics — Stats Dashboard</h1>
    <p>Web interaction analytics · {start_date.strftime('%d %b %Y')} → {end_date.strftime('%d %b %Y')}</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# DATA LOADING (session state)
# ─────────────────────────────────────────────────────────────
if "platforms" not in st.session_state or load_btn:
    with st.spinner("Loading platform metadata from ERDDAP…"):
        try:
            st.session_state["platforms"] = load_platform_metadata()
        except Exception as e:
            st.error(f"Could not load platform metadata: {e}")
            st.session_state["platforms"] = pd.DataFrame()

if "matomo" not in st.session_state or load_btn:
    with st.spinner("Loading Matomo analytics…"):
        try:
            raw = load_matomo_stats(token, str(start_date), str(end_date))
            st.session_state["matomo"] = raw
        except Exception as e:
            st.error(f"Could not load Matomo stats: {e}")
            st.session_state["matomo"] = pd.DataFrame()

platforms: pd.DataFrame = st.session_state.get("platforms", pd.DataFrame())
matomo:    pd.DataFrame = st.session_state.get("matomo",    pd.DataFrame())

if matomo.empty:
    st.warning("No Matomo data available. Check token / dates and reload.")
    st.stop()

erddap_df, platform_df, prod_df = classify_rows(matomo)


# ─────────────────────────────────────────────────────────────
# SECTION 1 – OVERALL KPIs
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📊 Overall monthly statistics</div>', unsafe_allow_html=True)

uv_all, pv_all, tt_all = kpi(matomo)
uv_erd, pv_erd, tt_erd = kpi(erddap_df)
uv_map, pv_map, tt_map = kpi(platform_df)
uv_pro, pv_pro, tt_pro = kpi(prod_df)

st.markdown(f"""
<div class="kpi-row">
  {kpi_card("Total unique pageviews", uv_all, "all categories")}
  {kpi_card("Total pageviews", pv_all, "all categories")}
  {kpi_card("Avg. time on page (s)", tt_all, "all categories")}
</div>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<span class="badge badge-erd">ERDDAP</span> Data access', unsafe_allow_html=True)
    st.metric("Unique pageviews", f"{uv_erd:,}")
    st.metric("Pageviews",        f"{pv_erd:,}")
    st.metric("Avg time (s)",     f"{tt_erd:,.1f}")

with col2:
    st.markdown('<span class="badge badge-map">MAP</span> Platform explorer', unsafe_allow_html=True)
    st.metric("Unique pageviews", f"{uv_map:,}")
    st.metric("Pageviews",        f"{pv_map:,}")
    st.metric("Avg time (s)",     f"{tt_map:,.1f}")

with col3:
    st.markdown('<span class="badge badge-prod">PRODUCT</span> EP_MAP products', unsafe_allow_html=True)
    st.metric("Unique pageviews", f"{uv_pro:,}")
    st.metric("Pageviews",        f"{pv_pro:,}")
    st.metric("Avg time (s)",     f"{tt_pro:,.1f}")

with st.expander("📋 Raw Matomo data (all rows)", expanded=False):
    st.dataframe(matomo, use_container_width=True)


# ─────────────────────────────────────────────────────────────
# SECTION 2 – FILTERED VIEW BY OWNER / PLATFORM
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🔍 Filter by institution & platform</div>', unsafe_allow_html=True)

if platforms.empty:
    st.warning("Platform metadata unavailable — cannot filter by owner/platform.")
else:
    # Normalise column names
    owner_col   = "dataownername"       if "dataownername"  in platforms.columns else None
    country_col = "dataownercountryname" if "dataownercountryname" in platforms.columns else None
    pcode_col   = "PLATFORMCODE"        if "PLATFORMCODE"   in platforms.columns else None

    filter_col1, filter_col2 = st.columns([1, 1])

    with filter_col1:
        if owner_col:
            owners = sorted(platforms[owner_col].dropna().unique().tolist())
            sel_owners = st.multiselect(
                "Institution (data owner)",
                options=owners,
                placeholder="Select one or more institutions…",
            )
        else:
            sel_owners = []

    with filter_col2:
        if country_col:
            countries = sorted(platforms[country_col].dropna().unique().tolist())
            sel_countries = st.multiselect(
                "Country",
                options=countries,
                placeholder="Filter by country…",
            )
        else:
            sel_countries = []

    # Filter platform metadata
    filtered_plat = platforms.copy()
    if sel_owners and owner_col:
        filtered_plat = filtered_plat[filtered_plat[owner_col].isin(sel_owners)]
    if sel_countries and country_col:
        filtered_plat = filtered_plat[filtered_plat[country_col].isin(sel_countries)]

    # Platform code selector (driven by owner filter)
    if pcode_col:
        available_codes = sorted(filtered_plat[pcode_col].dropna().unique().tolist())
        sel_codes = st.multiselect(
            "Platform code(s)",
            options=available_codes,
            placeholder="Pick platform codes (leave empty = all filtered platforms)…",
        )
        if sel_codes:
            filtered_plat = filtered_plat[filtered_plat[pcode_col].isin(sel_codes)]

    st.caption(f"Platforms matching filters: **{len(filtered_plat):,}**")

    # Show platform metadata table
    display_cols = [c for c in [
        "PLATFORMCODE", "call_name", "dataownername", "dataownercountryname",
        "platformtypedescription", "datafeaturetype",
        "firstdateobservation", "lastdateobservation",
        "integrator", "dataassemblycenter",
    ] if c in filtered_plat.columns]

    st.dataframe(filtered_plat[display_cols], use_container_width=True, height=280)

    # Match Matomo platform rows to selected platforms
    if not filtered_plat.empty and pcode_col:
        codes_lower = filtered_plat[pcode_col].dropna().str.lower().tolist()
        # platform_df labels contain platformcode= or platformid=
        matched_matomo = platform_df[
            platform_df["Label"].str.lower().apply(
                lambda lbl: any(c in lbl for c in codes_lower)
            )
        ]

        st.markdown(f"**Matomo MAP rows matching selected platforms:** {len(matched_matomo):,}")

        if not matched_matomo.empty:
            uv_m, pv_m, tt_m = kpi(matched_matomo)
            st.markdown(f"""
            <div class="kpi-row">
              {kpi_card("Unique pageviews (filtered)", uv_m)}
              {kpi_card("Pageviews (filtered)", pv_m)}
              {kpi_card("Avg time (s)", tt_m)}
            </div>
            """, unsafe_allow_html=True)

            st.dataframe(
                matched_matomo.sort_values("Pageviews", ascending=False),
                use_container_width=True,
                height=260,
            )
        else:
            st.info("No Matomo MAP visits found for the selected platforms in this period.")

        # Merge: platform metadata + matched Matomo
        combined_df = filtered_plat.copy()
        if not matched_matomo.empty and pcode_col:
            # aggregate per platform code from matomo
            def extract_pcode(label: str) -> str:
                label_l = label.lower()
                for marker in ["platformcode=", "platformid="]:
                    idx = label_l.find(marker)
                    if idx != -1:
                        raw = label[idx + len(marker):]
                        return raw.split("&")[0].split("/")[0].upper()
                return ""

            mm2 = matched_matomo.copy()
            mm2["_pcode"] = mm2["Label"].apply(extract_pcode)
            agg = mm2.groupby("_pcode").agg(
                matomo_unique_pv=("Unique Pageviews", "sum"),
                matomo_pv=("Pageviews", "sum"),
                matomo_avg_time=("Total time spent by visitors (in seconds)", "mean"),
            ).reset_index().rename(columns={"_pcode": pcode_col})

            combined_df = combined_df.merge(agg, on=pcode_col, how="left")

        # Store for download
        st.session_state["filtered_combined"] = combined_df
    else:
        st.session_state["filtered_combined"] = filtered_plat


# ─────────────────────────────────────────────────────────────
# SECTION 3 – DOWNLOAD
# ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">💾 Download results</div>', unsafe_allow_html=True)

today_str = datetime.today().strftime("%Y%m%d")

dl_col1, dl_col2, dl_col3 = st.columns(3)

# Download 1 – full Matomo export
with dl_col1:
    st.markdown("**Full Matomo stats**")
    csv_matomo = matomo.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇ Download full stats CSV",
        data=csv_matomo,
        file_name=f"{today_str}_matomo_emodnet_full.csv",
        mime="text/csv",
        use_container_width=True,
    )

# Download 2 – summary by category
with dl_col2:
    st.markdown("**Summary by category**")
    rows = []
    for label, df_sub in [("ERDDAP", erddap_df), ("MAP", platform_df), ("PRODUCT", prod_df)]:
        uv, pv, tt = kpi(df_sub)
        rows.append({"Category": label, "Unique Pageviews": uv, "Pageviews": pv, "Avg Time (s)": tt})
    summary_df = pd.DataFrame(rows)
    csv_summary = summary_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇ Download summary CSV",
        data=csv_summary,
        file_name=f"{today_str}_matomo_emodnet_summary.csv",
        mime="text/csv",
        use_container_width=True,
    )

# Download 3 – filtered / combined result
with dl_col3:
    st.markdown("**Filtered platform data**")
    filtered_to_download = st.session_state.get("filtered_combined", platforms)
    if not filtered_to_download.empty:
        csv_filtered = filtered_to_download.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇ Download filtered CSV",
            data=csv_filtered,
            file_name=f"{today_str}_matomo_emodnet_filtered.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("Apply filters above to enable this download.")

st.markdown("---")
st.caption("EMODnet Physics Stats Dashboard · Built with Streamlit · Data: ERDDAP + Matomo/VLIZ")
