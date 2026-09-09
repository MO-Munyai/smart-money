import streamlit as st
import pandas as pd

from api_client import API_URL, api_request, error_detail, safe_json

st.set_page_config(page_title="SmartMoney - Markets", layout="wide")
st.title("🌍 Markets Overview")

st.caption(
    "Live top-10 lists (~80 tickers, one batched request, usually 5-10s). "
    "Loads automatically and is cached for 60s so navigating around the app "
    "doesn't keep re-hitting Yahoo Finance - use Refresh Now for the latest."
)


def entries_to_df(entries):
    rows = []
    for e in entries:
        if "error" in e:
            rows.append({
                "Ticker": e["ticker"], "Name": e.get("name", "N/A"),
                "Native Price": "N/A", "Currency": "N/A",
                "FX Rate (-> ZAR)": "N/A", "ZAR Price": e["error"]
            })
        else:
            rows.append({
                "Ticker": e["ticker"],
                "Name": e.get("name", "N/A"),
                "Native Price": round(e["native_price"], 2),
                "Currency": e["currency"],
                "FX Rate (-> ZAR)": round(e["fx_rate"], 4) if e["fx_rate"] is not None else "1:1 (ZAR-equivalent)",
                "ZAR Price": f"R {e['zar_price']:,.2f}"
            })
    return pd.DataFrame(rows)


@st.cache_data(ttl=60, show_spinner=False)
def fetch_overview():
    """
    Cached for 60s: this page auto-loads on every visit, and without a
    cache that would mean re-hitting Yahoo for ~80 tickers every time
    someone navigates here (or Streamlit reruns for any other reason).
    Caches only plain dict/str/int - not the raw response object.
    """
    r, err = api_request("GET", f"{API_URL}/markets/overview", timeout=45)
    if err:
        return None, err
    if r.status_code != 200:
        return None, error_detail(r, "Failed to load markets overview")
    overview = safe_json(r)
    if overview is None:
        return None, "Markets overview returned an unreadable response"
    return overview, None


if st.button("🔄 Refresh Now"):
    fetch_overview.clear()
    st.rerun()

with st.spinner("Fetching ~80 tickers live from Yahoo Finance..."):
    overview, err = fetch_overview()

if err:
    st.error(err)
else:
    by_type = overview.get("by_type", {})
    by_country = overview.get("by_country", {})

    st.header("By Instrument Type")
    type_tabs = st.tabs([category.capitalize() for category in by_type.keys()])
    for tab, (category, entries) in zip(type_tabs, by_type.items()):
        with tab:
            st.dataframe(entries_to_df(entries), width="stretch")

    st.header("By Country / Market")
    country_tabs = st.tabs(list(by_country.keys()))
    for tab, (country, entries) in zip(country_tabs, by_country.items()):
        with tab:
            st.dataframe(entries_to_df(entries), width="stretch")
