import streamlit as st
import requests
import pandas as pd

API_URL = "http://127.0.0.1:8000"

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
                st.error(r.json().get("detail", "Failed to register instrument"))

# -----------------------------
# Instrument Registry
# -----------------------------
st.header("📋 Instrument Registry")

r = requests.get(f"{API_URL}/instruments")
if r.status_code == 200:
    instruments = r.json()
    if instruments:
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
                    st.error(d.json().get("detail", "Failed to remove instrument"))
    else:
        st.info("No instruments registered yet")
else:
    st.error("Failed to load instrument registry")
