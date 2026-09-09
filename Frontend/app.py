import streamlit as st
import requests
import pandas as pd

API_URL = "http://127.0.0.1:8000"


def error_detail(response, fallback):
    """
    Safely pulls a {"detail": ...} message out of a failed response.
    FastAPI's default handler returns plain text (not JSON) for unhandled
    server errors (e.g. a 500), so response.json() itself can raise - this
    falls back to the raw text, or the given fallback, instead of crashing.
    """
    try:
        return response.json().get("detail", fallback)
    except ValueError:
        return response.text or fallback

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(page_title="SmartMoney", layout="wide")
st.title("📊 SmartMoney")

# -----------------------------
# Register Instrument
# -----------------------------
st.header("➕ Register Instrument")

with st.form("register_instrument"):
    col1, col2 = st.columns(2)
    with col1:
        ticker = st.text_input("Ticker (e.g. AAPL, NPN.JO, BTC-USD)")
    with col2:
        instrument_type = st.selectbox("Type", ["Stock", "EFT", "Crypto", "Index"])

    submitted = st.form_submit_button("Register")
    if submitted:
        if not ticker.strip():
            st.error("Enter a ticker first")
        else:
            r = requests.post(
                f"{API_URL}/instruments",
                json={"ticker": ticker.strip(), "type": instrument_type}
            )
            if r.status_code == 200:
                st.success(f"{ticker.upper()} registered")
            else:
                st.error(error_detail(r, "Failed to register instrument"))

# -----------------------------
# Instrument Registry
# -----------------------------
st.header("📋 Instrument Registry")

r = requests.get(f"{API_URL}/instruments")
if r.status_code == 200:
    try:
        instruments = r.json()
    except ValueError:
        st.error("Instrument registry returned an unreadable response")
        instruments = None

    if instruments is None:
        pass  # error already shown above
    elif instruments:
        df = pd.DataFrame(instruments)
        st.dataframe(df, width="stretch")

        tickers = [i["ticker"] for i in instruments]
        col1, col2 = st.columns([3, 1])
        with col1:
            ticker_to_remove = st.selectbox("Remove instrument", tickers)
        with col2:
            st.write("")
            st.write("")
            if st.button("Remove"):
                d = requests.delete(f"{API_URL}/instruments/{ticker_to_remove}")
                if d.status_code == 200:
                    st.success(f"{ticker_to_remove} removed")
                    st.rerun()
                else:
                    st.error(error_detail(d, "Failed to remove instrument"))
        # -----------------------------
        # Instrument Detail
        # -----------------------------
        st.header("🔎 Instrument Detail")

        selected_ticker = st.selectbox("View instrument", tickers, key="detail_ticker")
        d = requests.get(f"{API_URL}/instruments/{selected_ticker}")
        if d.status_code == 200:
            detail = d.json()

            st.subheader(detail.get("name") or detail["ticker"])
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Live Price (ZAR)", f"R {detail['live_price']:.2f}" if detail.get("live_price") is not None else "N/A")
            col2.metric("P/E Ratio", f"{detail['pe_ratio']:.2f}" if detail.get("pe_ratio") is not None else "N/A")
            col3.metric("Beta", f"{detail['beta']:.2f}" if detail.get("beta") is not None else "N/A")
            col4.metric("Dividend Yield", f"{detail['dividend_yield']:.2f}%" if detail.get("dividend_yield") is not None else "N/A")

            st.table(pd.DataFrame([{
                "Type": detail.get("type"),
                "Sector": detail.get("sector") or "N/A",
                "Industry": detail.get("industry") or "N/A",
                "Country": detail.get("country") or "N/A",
                "Market Cap": detail.get("market_cap") or "N/A",
                "ROE": detail.get("roe"),
                "Added": detail.get("added_at")
            }]))
        else:
            st.error(error_detail(d, "Failed to load instrument detail"))
    else:
        st.info("No instruments registered yet")
else:
    st.error("Failed to load instrument registry")
