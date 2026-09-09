import streamlit as st
import pandas as pd

from api_client import API_URL, api_request, error_detail, safe_json

st.set_page_config(page_title="SmartMoney - Markets", layout="wide")
st.title("🌍 Markets Overview")

st.caption(
    "Live top-10 lists, always fetched fresh (nothing is stored). "
    "This pulls ~80 tickers from Yahoo Finance in one batched request, "
    "usually taking 5-10 seconds to load."
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


if st.button("🔄 Load / Refresh Markets Overview"):
    st.session_state["markets_overview_loaded"] = True

if not st.session_state.get("markets_overview_loaded"):
    st.info("Click the button above to fetch live market data (not loaded automatically, since it's an ~80-ticker live fetch).")
else:
    with st.spinner("Fetching ~80 tickers live from Yahoo Finance..."):
        r, err = api_request("GET", f"{API_URL}/markets/overview", timeout=45)

    if err:
        st.error(err)
    elif r.status_code != 200:
        st.error(error_detail(r, "Failed to load markets overview"))
    else:
        overview = safe_json(r)
        if overview is None:
            st.error("Markets overview returned an unreadable response")
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
