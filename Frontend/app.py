import streamlit as st
import requests

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
        instrument_type = st.selectbox("Type", ["stock", "etf", "crypto", "index"])

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
