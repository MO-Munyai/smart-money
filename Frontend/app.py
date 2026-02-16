import streamlit as st
import requests
import pandas as pd
from datetime import date

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Stock Portfolio Dashboard",
    layout="wide"
)

st.title("📊 Personal Stock Portfolio")

# -----------------------------
# Add Transaction
# -----------------------------
st.header("➕ Add Transaction")

with st.form("add_transaction"):
    col1, col2, col3 = st.columns(3)

    with col1:
        ticker = st.text_input("Ticker (e.g. AAPL, NPN.JO)")
        quantity = st.number_input("Quantity", min_value=0.0, step=1.0)
    with col2:
        price = st.number_input("Price", min_value=0.0)
        txn_type = st.selectbox("Type", ["buy", "sell"])
    with col3:
        txn_date = st.date_input("Date", value=date.today())

    submitted = st.form_submit_button("Add Transaction")

    if submitted:
        payload = {
            "ticker": ticker,
            "quantity": quantity,
            "price": price,
            "type": txn_type,
            "date": str(txn_date)
        }

        r = requests.post(f"{API_URL}/transactions", json=payload)

        if r.status_code == 200:
            st.success("Transaction added successfully")
        else:
            st.error(r.json().get("detail", "Failed to add transaction"))

# -----------------------------
# View Transactions
# -----------------------------
st.header("📋 Transactions")

r = requests.get(f"{API_URL}/transactions")
transactions = r.json() if r.status_code == 200 else []

if transactions:
    df = pd.DataFrame(transactions)
    st.dataframe(df, use_container_width=True)

    delete_id = st.number_input(
        "Transaction ID to delete",
        min_value=1,
        step=1
    )

    if st.button("Delete Transaction"):
        d = requests.delete(f"{API_URL}/transactions/{delete_id}")
        if d.status_code == 200:
            st.success("Transaction deleted")
            st.experimental_rerun()
        else:
            st.error("Transaction not found")
else:
    st.info("No transactions yet")

# -----------------------------
# Portfolio Summary
# -----------------------------
st.header("📈 Portfolio Summary")

r = requests.get(f"{API_URL}/portfolio")

if r.status_code == 200:
    portfolio = r.json()

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Invested", f"R {portfolio['total_invested']:.2f}")
    col2.metric("Current Value", f"R {portfolio['current_value']:.2f}")
    col3.metric(
        "Total Gain / Loss",
        f"R {portfolio['total_gain_loss']:.2f}"
    )

    if portfolio["positions"]:
        positions_df = pd.DataFrame(portfolio["positions"])
        st.subheader("Positions")
        st.dataframe(positions_df, use_container_width=True)
else:
    st.error("Failed to load portfolio")