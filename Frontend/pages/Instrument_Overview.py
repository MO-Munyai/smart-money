from urllib.parse import quote

import pandas as pd
import streamlit as st

from api_client import API_URL, api_request, error_detail, safe_json
from overview_format import (
    build_facts, build_links, build_officers, empty_profile_message,
    is_empty_profile, split_summary,
)

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
    # Yahoo types we don't support (e.g. mutual funds) come back with type
    # None and can't be registered, so no button for those.
    if overview.get("type"):
        if st.button("Register", key="register_overview"):
            reg_r, reg_err = api_request(
                "POST", f"{API_URL}/instruments",
                json={"ticker": overview["ticker"], "type": overview["type"]}
            )
            if reg_err:
                st.error(reg_err)
            elif reg_r.status_code == 200:
                # Rerun so the overview is refetched and the status flips to
                # "In your registry".
                st.rerun()
            else:
                st.error(error_detail(reg_r, "Failed to register instrument"))
    else:
        st.caption("This type of instrument can't be added to the registry.")

if is_empty_profile(overview):
    st.info(empty_profile_message(overview))
    st.stop()

# Every section below only renders when it has real content - empty fields are
# hidden entirely rather than shown as "N/A".
preview, remainder = split_summary(overview.get("summary"))
if preview:
    st.subheader("About")
    st.write(preview)
    if remainder:
        with st.expander("Read the full description"):
            st.write(remainder)

facts = build_facts(overview)
if facts:
    st.subheader("Key facts")
    for row_start in range(0, len(facts), 3):
        columns = st.columns(3)
        for column, (label, value) in zip(columns, facts[row_start:row_start + 3]):
            column.markdown(f"**{label}**  \n{value}")

links = build_links(overview)
if links:
    st.subheader("Links")
    for label, url in links:
        st.markdown(f"[{label}]({url})")

officers = build_officers(overview)
if officers:
    st.subheader("Key officers")
    st.dataframe(pd.DataFrame(officers), width="stretch", hide_index=True)
