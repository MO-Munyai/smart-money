from urllib.parse import quote

import streamlit as st

from api_client import API_URL, api_request, error_detail, safe_json

st.set_page_config(page_title="SmartMoney - Instrument Overview", layout="wide")
st.title("🏢 Instrument Overview")

# The ticker arrives as ?ticker=... - set by st.switch_page(query_params=...)
# from the search/registry buttons, or typed straight into the URL. Using the
# URL (rather than session state) means a refresh or a shared link still works.
ticker = (st.query_params.get("ticker") or "").strip()

if st.button("← Back to search and registry"):
    st.switch_page("app.py")

if not ticker:
    st.info(
        "No instrument selected. Search for one on the main page and click "
        "its Overview button, or open this page with `?ticker=SYMBOL`."
    )
    st.stop()

with st.spinner(f"Loading {ticker} overview..."):
    r, err = api_request("GET", f"{API_URL}/instruments/{quote(ticker, safe='')}/overview")

if err:
    st.error(err)
    st.stop()

if r.status_code == 404:
    st.warning(f"No instrument found for '{ticker}'. Check the ticker and its exchange suffix.")
    st.stop()

if r.status_code == 503:
    st.warning(error_detail(r, "Yahoo Finance is rate-limiting requests right now - try again shortly"))
    st.stop()

if r.status_code != 200:
    st.error(error_detail(r, "Failed to load instrument overview"))
    st.stop()

overview = safe_json(r)
if overview is None:
    st.error("Instrument overview returned an unreadable response")
    st.stop()

st.header(overview.get("name") or overview["ticker"])
st.caption(" · ".join(
    str(part) for part in (
        overview.get("ticker"), overview.get("type"),
        overview.get("exchange"), overview.get("currency")
    ) if part
))

if overview.get("registered"):
    st.success("In your registry")
else:
    st.info("Not in your registry yet")
