import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from api_client import API_URL, api_request, error_detail, safe_json

# Yahoo's actual valid intervals, each mapped to the period choices that stay
# within that interval's real lookback limit (confirmed empirically - Yahoo
# silently returns 0 rows rather than erroring when a period/interval
# combination exceeds its limit, e.g. 1m data is capped at 8 days,
# 5m/15m/30m at 60 days). Keeping period options dependent on the chosen
# interval means every combination in the UI is guaranteed to actually work.
HISTORY_INTERVAL_PERIODS = {
    "1m": ["1d", "5d"],
    "5m": ["1d", "5d", "1mo"],
    "15m": ["1d", "5d", "1mo"],
    "30m": ["1d", "5d", "1mo"],
    "1h": ["5d", "1mo", "3mo", "6mo", "1y", "2y"],
    "4h": ["5d", "1mo", "3mo", "6mo", "1y", "2y"],
    "1d": ["1mo", "3mo", "6mo", "1y", "5y"],
}


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
            r, err = api_request(
                "POST", f"{API_URL}/instruments",
                json={"ticker": ticker.strip(), "type": instrument_type}
            )
            if err:
                st.error(err)
            elif r.status_code == 200:
                st.success(f"{ticker.upper()} registered")
            else:
                st.error(error_detail(r, "Failed to register instrument"))

# -----------------------------
# Instrument Registry
# -----------------------------
st.header("📋 Instrument Registry")

r, err = api_request("GET", f"{API_URL}/instruments")
if err:
    st.error(err)
elif r.status_code != 200:
    st.error(error_detail(r, "Failed to load instrument registry"))
else:
    instruments = safe_json(r)
    if instruments is None:
        st.error("Instrument registry returned an unreadable response")
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
                d, derr = api_request("DELETE", f"{API_URL}/instruments/{ticker_to_remove}")
                if derr:
                    st.error(derr)
                elif d.status_code == 200:
                    st.success(f"{ticker_to_remove} removed")
                    st.rerun()
                else:
                    st.error(error_detail(d, "Failed to remove instrument"))

        # -----------------------------
        # Instrument Detail
        # -----------------------------
        st.header("🔎 Instrument Detail")

        selected_ticker = st.selectbox("View instrument", tickers, key="detail_ticker")
        d, derr = api_request("GET", f"{API_URL}/instruments/{selected_ticker}")
        if derr:
            st.error(derr)
        elif d.status_code != 200:
            st.error(error_detail(d, "Failed to load instrument detail"))
        else:
            detail = safe_json(d)
            if detail is None:
                st.error("Instrument detail returned an unreadable response")
            else:
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

                # -----------------------------
                # Price History
                # -----------------------------
                st.subheader("Price History")

                hist_col1, hist_col2 = st.columns(2)
                with hist_col1:
                    interval = st.selectbox(
                        "Interval", list(HISTORY_INTERVAL_PERIODS.keys()),
                        index=6, key="history_interval"  # default "1d"
                    )
                with hist_col2:
                    period_options = HISTORY_INTERVAL_PERIODS[interval]
                    default_period_index = period_options.index("6mo") if "6mo" in period_options else 0
                    # Keyed per-interval so switching interval can't leave a
                    # stale selection that isn't in the new options list
                    # (Streamlit raises if a widget's cached value isn't
                    # among its current options).
                    period = st.selectbox(
                        "Period", period_options, index=default_period_index,
                        key=f"history_period_{interval}"
                    )

                h, herr = api_request(
                    "GET", f"{API_URL}/instruments/{selected_ticker}/history",
                    params={"period": period, "interval": interval}
                )
                if herr:
                    st.error(herr)
                elif h.status_code != 200:
                    st.error(error_detail(h, "Failed to load price history"))
                else:
                    history_payload = safe_json(h)
                    if history_payload is None:
                        st.error("Price history returned an unreadable response")
                    else:
                        bars = history_payload.get("history", [])
                        if bars:
                            hist_df = pd.DataFrame(bars)
                            fig = go.Figure(data=[go.Candlestick(
                                x=hist_df["date"],
                                open=hist_df["open"],
                                high=hist_df["high"],
                                low=hist_df["low"],
                                close=hist_df["close"]
                            )])
                            fig.update_layout(
                                title=f"{selected_ticker} - {period} @ {interval} (ZAR)",
                                xaxis_rangeslider_visible=False
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("No price history available for this period")

        # -----------------------------
        # Compare Instruments
        # -----------------------------
        st.header("⚖️ Compare Instruments")

        compare_tickers = st.multiselect(
            "Select 2 or more instruments to compare", tickers, key="compare_tickers"
        )
        if len(compare_tickers) < 2:
            st.info("Select at least two instruments to compare")
        else:
            c, cerr = api_request(
                "GET", f"{API_URL}/instruments/compare",
                params={"tickers": ",".join(compare_tickers)}
            )
            if cerr:
                st.error(cerr)
            elif c.status_code != 200:
                st.error(error_detail(c, "Failed to load comparison"))
            else:
                compare_payload = safe_json(c)
                if compare_payload is None:
                    st.error("Comparison returned an unreadable response")
                else:
                    compared = compare_payload.get("instruments", [])
                    if compared:
                        compare_df = pd.DataFrame(compared).set_index("ticker").T
                        st.dataframe(compare_df, width="stretch")
                    else:
                        st.info("No valid data returned for the selected instruments")
    else:
        st.info("No instruments registered yet")
