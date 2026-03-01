import streamlit as st
import requests
import pandas as pd
from datetime import date
import plotly.express as px
import plotly.graph_objects as go

API_URL = "http://127.0.0.1:8000"

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(page_title="SmartMoney Portfolio", layout="wide")
st.title("📊 SmartMoney Portfolio Dashboard")

# -----------------------------
# Initialize session state
# -----------------------------
if "refresh_transactions" not in st.session_state:
    st.session_state["refresh_transactions"] = False
if "transactions" not in st.session_state:
    st.session_state["transactions"] = []

# -----------------------------
# Helper function to mark refresh
# -----------------------------
def trigger_refresh():
    st.session_state["refresh_transactions"] = True

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
        price = st.number_input("Price", min_value=0.0, step=0.01)
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
            trigger_refresh()
        else:
            st.error(r.json().get("detail", "Failed to add transaction"))

# -----------------------------
# Transactions Table & Delete
# -----------------------------
st.header("📋 Transactions")

# Fetch transactions if refresh requested
if st.session_state["refresh_transactions"]:
    r = requests.get(f"{API_URL}/transactions")
    st.session_state["transactions"] = r.json() if r.status_code == 200 else []
    st.session_state["refresh_transactions"] = False

transactions = st.session_state["transactions"]

if transactions:
    df = pd.DataFrame(transactions)
    st.dataframe(df, width="stretch")

    delete_id = st.number_input("Transaction ID to delete", min_value=1, step=1)
    if st.button("Delete Transaction"):
        d = requests.delete(f"{API_URL}/transactions/{delete_id}")
        if d.status_code == 200:
            st.success("Transaction deleted")
            trigger_refresh()
        else:
            st.error("Transaction not found")
else:
    st.info("No transactions yet")

# -----------------------------
# Portfolio Summary & Analytics
# -----------------------------
st.header("📈 Portfolio Summary & Analytics")

r = requests.get(f"{API_URL}/portfolio/analytics")
if r.status_code == 200:
    portfolio = r.json()

    # Metrics (safe access)
    total_invested = portfolio.get("total_invested", 0)
    total_value = portfolio.get("total_value", 0)
    total_gain_loss = portfolio.get("total_gain_loss", 0)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Invested", f"R {total_invested:.2f}")
    col2.metric("Current Value", f"R {total_value:.2f}")
    col3.metric("Total Gain / Loss", f"R {total_gain_loss:.2f}")

    # Positions Table
    positions = portfolio.get("positions", [])
    if positions:
        st.subheader("Positions")
        positions_df = pd.DataFrame(positions)
        st.dataframe(positions_df, width="stretch")

    # Sector Allocation Pie Chart
    sector_breakdown = portfolio.get("sector_breakdown", {})
    if sector_breakdown:
        st.subheader("Sector Allocation")
        sector_df = pd.DataFrame({
            "Sector": list(sector_breakdown.keys()),
            "Allocation": list(sector_breakdown.values())
        })
        fig_sector = px.pie(sector_df, names="Sector", values="Allocation", title="Sector Allocation")
        st.plotly_chart(fig_sector, use_container_width=True)

    # Industry Allocation Pie Chart
    industry_breakdown = portfolio.get("industry_breakdown", {})
    if industry_breakdown:
        st.subheader("Industry Allocation")
        industry_df = pd.DataFrame({
            "Industry": list(industry_breakdown.keys()),
            "Allocation": list(industry_breakdown.values())
        })
        fig_industry = px.pie(industry_df, names="Industry", values="Allocation", title="Industry Allocation")
        st.plotly_chart(fig_industry, use_container_width=True)

    # Weighted Metrics Table
    weighted_metrics = portfolio.get("weighted_metrics", {})
    if weighted_metrics:
        st.subheader("Weighted Portfolio Metrics")
        metrics_df = pd.DataFrame([weighted_metrics])
        st.dataframe(metrics_df, width="stretch")

    # Portfolio Value vs Invested Value Over Time
    history = portfolio.get("history", [])
    if history:
        st.subheader("Portfolio Value Over Time")
        history_df = pd.DataFrame(history)
        fig_history = go.Figure()
        fig_history.add_trace(go.Scatter(
            x=history_df['date'], y=history_df.get('total_value', [0]*len(history_df)), name='Current Value'
        ))
        fig_history.add_trace(go.Scatter(
            x=history_df['date'], y=history_df.get('total_invested', [0]*len(history_df)), name='Invested'
        ))
        fig_history.update_layout(
            title='Portfolio Value vs Invested Over Time',
            xaxis_title='Date',
            yaxis_title='R Value',
            legend_title='Legend'
        )
        st.plotly_chart(fig_history, use_container_width=True)

else:
    st.error("Failed to load portfolio")