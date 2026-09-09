import streamlit as st

from api_client import API_URL, api_request, error_detail, safe_json

st.set_page_config(page_title="SmartMoney - Admin", layout="wide")
st.title("🛠️ Admin")


def format_uptime(seconds):
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


col1, col2 = st.columns([1, 3])
with col1:
    refresh = st.button("🔄 Refresh")
with col2:
    deep = st.checkbox(
        "Deep check (also verifies Yahoo Finance is reachable right now)",
        value=False,
        help="Makes a real yfinance call, so it isn't on by default - "
             "avoids turning routine admin-page visits into rate-limit exposure."
    )

r, err = api_request("GET", f"{API_URL}/health", params={"deep": deep} if deep else {})
if err:
    st.error(err)
elif r.status_code != 200:
    st.error(error_detail(r, "Failed to load health status"))
else:
    health = safe_json(r)
    if health is None:
        st.error("Health endpoint returned an unreadable response")
    else:
        status = health.get("status", "unknown")
        if status == "ok":
            st.success(f"Status: {status}")
        else:
            st.warning(f"Status: {status}")

        st.caption(
            f"Started {health.get('started_at', 'N/A')} · "
            f"Checked {health.get('checked_at', 'N/A')}"
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("Uptime", format_uptime(health.get("uptime_seconds", 0)))

        db = health.get("database", {})
        col2.metric(
            "Database",
            "Reachable" if db.get("reachable") else "Unreachable",
            f"{db.get('latency_ms', 0)} ms" if db.get("reachable") else db.get("error", "")
        )

        rate_limit = health.get("rate_limit", {})
        col3.metric(
            "Rate-Limit Hits",
            rate_limit.get("hits", 0),
            rate_limit.get("last_hit_at") or "never"
        )

        st.subheader("Database")
        st.write(f"Instruments registered: **{db.get('instrument_count', 'N/A')}**")

        st.subheader("System")
        system = health.get("system", {})
        sys_col1, sys_col2 = st.columns(2)
        sys_col1.write(f"Python: **{system.get('python_version', 'N/A')}**")
        sys_col1.write(f"Platform: **{system.get('platform', 'N/A')}**")
        if "process_memory_mb" in system:
            sys_col2.write(f"Process memory: **{system['process_memory_mb']} MB**")
            sys_col2.write(f"Process CPU: **{system['process_cpu_percent']}%**")
        else:
            sys_col2.info(system.get("process_stats", "Process stats unavailable"))

        if deep:
            st.subheader("Market Data (Yahoo Finance)")
            market = health.get("market_data")
            if market is None:
                st.info("Deep check was requested but no market_data was returned")
            elif market.get("reachable"):
                st.success(
                    f"Reachable - checked {market.get('checked_ticker')} "
                    f"in {market.get('latency_ms')} ms"
                )
            else:
                st.error(f"Not reachable (checked {market.get('checked_ticker')})")
