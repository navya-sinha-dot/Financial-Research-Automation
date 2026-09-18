"""Financial Research Automation (FRA) Executive Dashboard.

Built with Streamlit. Communicates with the database EXCLUSIVELY via the FastAPI REST API.
"""
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path regardless of how or from where Streamlit is launched
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import time
from typing import Dict, Any, List, Optional
import pandas as pd
import streamlit as st

from src.dashboard.api_client import FRAApiClient

# -----------------------------------------------------------------------------
# Page Configuration & Visual Theme
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Financial Research Automation | FRA",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for executive dark theme and glassmorphism styling
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    /* Background and containers */
    .stApp {
        background: radial-gradient(circle at 10% 20%, #0B0F19 0%, #030712 100%);
        color: #F3F4F6;
    }

    /* Header gradient hero */
    .hero-banner {
        background: linear-gradient(135deg, rgba(30, 58, 138, 0.4) 0%, rgba(88, 28, 135, 0.3) 100%);
        border: 1px solid rgba(59, 130, 246, 0.25);
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }

    .hero-title {
        font-size: 28px;
        font-weight: 800;
        background: linear-gradient(90deg, #60A5FA, #A78BFA);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }

    .hero-subtitle {
        color: #9CA3AF;
        font-size: 14px;
        font-weight: 500;
    }

    /* Executive KPI Cards */
    .kpi-card {
        background: rgba(17, 24, 39, 0.7);
        border: 1px solid rgba(55, 65, 81, 0.6);
        border-radius: 12px;
        padding: 16px 20px;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: rgba(96, 165, 250, 0.5);
    }
    .kpi-label {
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94A3B8;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 24px;
        font-weight: 800;
        color: #F8FAFC;
    }
    .kpi-delta {
        font-size: 12px;
        font-weight: 600;
        margin-top: 4px;
    }
    .delta-positive { color: #34D399; }
    .delta-negative { color: #F87171; }

    /* Custom pill badges */
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.04em;
    }
    .badge-blue { background: rgba(59, 130, 246, 0.15); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.3); }
    .badge-green { background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-purple { background: rgba(139, 92, 246, 0.15); color: #C084FC; border: 1px solid rgba(139, 92, 246, 0.3); }

    /* Status indicator */
    .status-box {
        background: rgba(15, 23, 42, 0.8);
        border-left: 4px solid #3B82F6;
        padding: 12px 16px;
        border-radius: 4px;
        margin: 12px 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Initialize API Client
# -----------------------------------------------------------------------------
@st.cache_resource
def get_api_client() -> FRAApiClient:
    return FRAApiClient()

client = get_api_client()

# -----------------------------------------------------------------------------
# Sidebar: Company Selector & Ingestion Controls
# -----------------------------------------------------------------------------
st.sidebar.markdown("### 🏛️ Portfolio Companies")

companies = client.get_companies()
if not companies:
    st.sidebar.warning("No companies found. Starting initial check...")
    companies = []

company_options = {f"{c['ticker']} — {c['name']}": c for c in companies}

selected_label = st.sidebar.selectbox(
    "Select Target Company",
    options=list(company_options.keys()) if company_options else ["None"],
    index=0 if company_options else None,
)

selected_company = company_options.get(selected_label) if company_options else None

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚡ Live Data Ingestion")
st.sidebar.caption("Trigger async scraping & line item extraction for any ticker:")
new_ticker = st.sidebar.text_input("Ticker Symbol (e.g., AAPL, GOOGL, INFY)", value="").strip().upper()
if st.sidebar.button("Fetch & Ingest Ticker", use_container_width=True):
    if new_ticker:
        with st.sidebar.status(f"Triggering ingestion for {new_ticker}..."):
            ingest_res = client.trigger_ingestion(new_ticker)
            if ingest_res and ingest_res.get("status") in ("QUEUED", "SUCCESS"):
                st.sidebar.success(f"Task queued! Task ID: {ingest_res.get('task_id')[:8]}")
                time.sleep(1)
                st.rerun()
            else:
                st.sidebar.error("Failed to queue ingestion job.")
    else:
        st.sidebar.warning("Please enter a valid ticker.")

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style='font-size: 11px; color: #64748B;'>
        <b>FRA System Architecture:</b><br/>
        • Scraping: BeautifulSoup + Retries<br/>
        • Analytics: Isolated Python Engine<br/>
        • Reports: python-pptx Async Tasks<br/>
        • Database: PostgreSQL (SQLAlchemy)<br/>
        • API Gateway: FastAPI
    </div>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Main Application Content
# -----------------------------------------------------------------------------
if not selected_company:
    st.info("👋 Welcome to Financial Research Automation. Please select or ingest a company using the sidebar to begin.")
    st.stop()

# Fetch company financials and computed ratios via API
comp_id = selected_company["id"]
ticker = selected_company["ticker"]
company_name = selected_company["name"]
sector = selected_company.get("sector") or "Information Technology"
exchange = selected_company.get("exchange") or "NASDAQ"

financials_data = client.get_financials(comp_id)
ratios_data = client.get_ratios(comp_id)

periods = financials_data.get("periods", []) if financials_data else []

# -----------------------------------------------------------------------------
# Hero Banner & Report Generation Trigger
# -----------------------------------------------------------------------------
hero_col1, hero_col2 = st.columns([3, 1.2])

with hero_col1:
    st.markdown(
        f"""
        <div class="hero-banner">
            <div class="badge badge-blue">{exchange}</div>
            <div class="badge badge-purple">{sector}</div>
            <div class="hero-title">{company_name} ({ticker})</div>
            <div class="hero-subtitle">Quarterly Institutional Analysis & Automated Investor Research</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with hero_col2:
    st.markdown("### 📊 Investor Report")
    st.caption("Generate institutional 4-slide PowerPoint (.pptx) deck:")
    
    # Session state for active report job
    if f"report_job_{comp_id}" not in st.session_state:
        st.session_state[f"report_job_{comp_id}"] = None

    active_job_id = st.session_state[f"report_job_{comp_id}"]

    if st.button("🚀 Generate PPTX Report", key=f"btn_gen_{comp_id}", use_container_width=True):
        req_res = client.request_report(comp_id)
        if req_res and "id" in req_res:
            st.session_state[f"report_job_{comp_id}"] = req_res["id"]
            st.rerun()
        else:
            st.error("Failed to request report generation.")

    # Non-blocking async status polling
    if active_job_id:
        status_info = client.get_report_job_status(active_job_id)
        if status_info:
            current_status = status_info.get("status")
            if current_status in ("PENDING", "PROCESSING"):
                st.info(f"⏳ Job #{active_job_id}: Status is **{current_status}**. Polling background worker...")
                time.sleep(1.5)
                st.rerun()
            elif current_status == "COMPLETED":
                st.success(f"✅ Job #{active_job_id}: Report is ready!")
                pptx_bytes = client.download_report_bytes(active_job_id)
                if pptx_bytes:
                    st.download_button(
                        label="📥 Download Presentation (.pptx)",
                        data=pptx_bytes,
                        file_name=f"{ticker}_Investor_Report.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True,
                    )
            elif current_status == "FAILED":
                st.error(f"❌ Report generation failed: {status_info.get('error_message')}")
                if st.button("Reset Job Status", key=f"reset_{active_job_id}"):
                    st.session_state[f"report_job_{comp_id}"] = None
                    st.rerun()

# -----------------------------------------------------------------------------
# KPI Overview Cards
# -----------------------------------------------------------------------------
if periods:
    latest_p = periods[-1]
    latest_items = {item["item_name"]: item["value"] for item in latest_p.get("line_items", [])}
    
    # Pull latest ratios
    ratios_list = ratios_data.get("ratios_by_period", []) if ratios_data else []
    latest_ratios = ratios_list[-1].get("computed_ratios", {}) if ratios_list else {}

    rev = latest_items.get("revenue", 0.0)
    net_inc = latest_items.get("net_income", 0.0)
    nm = latest_ratios.get("net_margin")
    roe = latest_ratios.get("roe")
    cr = latest_ratios.get("current_ratio")
    yoy = latest_ratios.get("yoy_growth")

    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Quarterly Revenue</div>
                <div class="kpi-value">${rev:,.1f}M</div>
                <div class="kpi-delta {'delta-positive' if (yoy or 0) >= 0 else 'delta-negative'}">
                    {'▲' if (yoy or 0) >= 0 else '▼'} {f"{yoy*100:+.1f}% YoY" if yoy is not None else "YoY Base Period"}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Net Profit Margin</div>
                <div class="kpi-value">{f"{nm*100:.1f}%" if nm is not None else "N/A"}</div>
                <div class="kpi-delta delta-positive">Net Income: ${net_inc:,.1f}M</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Return on Equity (ROE)</div>
                <div class="kpi-value">{f"{roe*100:.1f}%" if roe is not None else "N/A"}</div>
                <div class="kpi-delta" style="color:#A78BFA">Annualized Return</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Current Ratio (Liquidity)</div>
                <div class="kpi-value">{f"{cr:.2f}x" if cr is not None else "N/A"}</div>
                <div class="kpi-delta {'delta-positive' if (cr or 0) >= 1.5 else 'delta-negative'}">
                    {'Healthy Buffer' if (cr or 0) >= 1.5 else 'Tight Liquidity'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c5:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Reporting Period</div>
                <div class="kpi-value">{latest_p.get('period_type')} {latest_p.get('fiscal_year')}</div>
                <div class="kpi-delta" style="color:#94A3B8">{latest_p.get('report_date')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("<br/>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Multi-Tab Analytics View
# -----------------------------------------------------------------------------
tab_trend, tab_ratios, tab_peer, tab_tables = st.tabs([
    "📈 Financial Trajectory",
    "🎯 Ratio & Margin Dynamics",
    "👥 Peer Benchmark Ranking",
    "📋 Financial Statements (Line Items)",
])

# Build DataFrame of all periods
period_rows = []
for p in periods:
    items_map = {item["item_name"]: item["value"] for item in p.get("line_items", [])}
    p_label = f"{p.get('period_type')} {p.get('fiscal_year')}"
    row = {
        "Period": p_label,
        "Fiscal Year": p.get("fiscal_year"),
        "Quarter": p.get("period_type"),
        "Report Date": str(p.get("report_date")),
        **items_map,
    }
    period_rows.append(row)

df_periods = pd.DataFrame(period_rows) if period_rows else pd.DataFrame()

# Tab 1: Financial Trajectory
with tab_trend:
    if not df_periods.empty and "revenue" in df_periods.columns:
        st.subheader("Quarterly Revenue & Profit Trajectory")
        chart_cols = [col for col in ["revenue", "net_income", "operating_income"] if col in df_periods.columns]
        st.bar_chart(
            df_periods.set_index("Period")[chart_cols],
            height=380,
        )
    else:
        st.warning("No revenue line items available to plot.")

# Tab 2: Ratio Dynamics
with tab_ratios:
    st.subheader("Profitability & Efficiency Ratios")
    ratios_by_period = ratios_data.get("ratios_by_period", []) if ratios_data else []
    if ratios_by_period:
        ratio_rows = []
        for r in ratios_by_period:
            p_label = f"{r.get('period_type')} {r.get('fiscal_year')}"
            comp = r.get("computed_ratios", {})
            ratio_rows.append({
                "Period": p_label,
                "Net Margin (%)": round(comp.get("net_margin", 0.0) * 100, 2) if comp.get("net_margin") is not None else None,
                "ROE (%)": round(comp.get("roe", 0.0) * 100, 2) if comp.get("roe") is not None else None,
                "Current Ratio (x)": round(comp.get("current_ratio", 0.0), 2) if comp.get("current_ratio") is not None else None,
                "YoY Revenue Growth (%)": round(comp.get("yoy_growth", 0.0) * 100, 2) if comp.get("yoy_growth") is not None else None,
                "QoQ Revenue Growth (%)": round(comp.get("qoq_growth", 0.0) * 100, 2) if comp.get("qoq_growth") is not None else None,
            })
        df_ratios = pd.DataFrame(ratio_rows)
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("#### Profitability Margins (Net Margin vs ROE)")
            st.line_chart(df_ratios.set_index("Period")[["Net Margin (%)", "ROE (%)"]], height=320)
        with col_c2:
            st.markdown("#### Liquidity & Growth")
            st.line_chart(df_ratios.set_index("Period")[["Current Ratio (x)"]], height=320)
            
        st.dataframe(df_ratios, use_container_width=True, hide_index=True)
    else:
        st.info("No ratios computed yet.")

# Tab 3: Peer Benchmark Ranking
with tab_peer:
    st.subheader("Cross-Company Peer Percentile Ranking")
    all_comp_ids = [c["id"] for c in companies]
    if len(all_comp_ids) > 1:
        compare_res = client.compare_companies(all_comp_ids)
        if compare_res and "companies" in compare_res:
            peer_comps = compare_res["companies"]
            peer_table_rows = []
            for pc in peer_comps:
                pct = pc.get("percentile_rankings", {})
                peer_table_rows.append({
                    "Ticker": pc.get("ticker"),
                    "Company Name": pc.get("name"),
                    "Latest Revenue ($M)": round(pc.get("latest_revenue") or 0.0, 1),
                    "Net Margin (%)": round((pc.get("net_margin") or 0.0) * 100, 2),
                    "ROE (%)": round((pc.get("roe") or 0.0) * 100, 2),
                    "Current Ratio (x)": round(pc.get("current_ratio") or 0.0, 2),
                    "Net Margin Percentile Rank": f"{pct.get('net_margin', 0.0):.0f}th percentile",
                })
            df_peers = pd.DataFrame(peer_table_rows)
            
            # Highlight target company
            st.dataframe(df_peers, use_container_width=True, hide_index=True)

            # Bar chart comparing net margins
            st.markdown("#### Net Margin Comparison vs Industry Peers")
            chart_df = df_peers.set_index("Ticker")[["Net Margin (%)"]]
            st.bar_chart(chart_df, height=320)
    else:
        st.info("Add more companies to unlock peer percentile comparison rankings.")

# Tab 4: Raw Line Items
with tab_tables:
    st.subheader("Normalized Financial Line Items")
    st.caption("Normalized key-value metric line items stored in database:")
    if not df_periods.empty:
        st.dataframe(df_periods, use_container_width=True, hide_index=True)
    else:
        st.info("No line items available.")
