from streamlit.testing.v1 import AppTest

from tests.conftest import FakeResponse, page_path, unreachable


def health_payload(**overrides):
    payload = {
        "status": "ok",
        "started_at": "2026-10-17T08:00:00",
        "checked_at": "2026-10-17T09:00:00",
        "uptime_seconds": 3725,
        "database": {"reachable": True, "latency_ms": 2, "instrument_count": 6},
        "rate_limit": {"hits": 3, "last_hit_at": "2026-10-17T08:30:00"},
        "system": {"python_version": "3.13", "platform": "Windows",
                   "process_memory_mb": 90.5, "process_cpu_percent": 1.2},
    }
    payload.update(overrides)
    return payload


def run_admin():
    at = AppTest.from_file(page_path("pages/Admin.py"), default_timeout=15)
    at.run()
    return at


def test_ok_status_renders_metrics(backend):
    backend.set("GET", "/health", FakeResponse(200, health_payload()))
    at = run_admin()
    assert not at.exception
    assert any("Status: ok" in s.value for s in at.success)
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Uptime"] == "1h 2m 5s"
    assert metrics["Database"] == "Reachable"
    assert metrics["Rate-Limit Hits"] == "3"


def test_degraded_status_is_a_warning(backend):
    backend.set("GET", "/health", FakeResponse(200, health_payload(status="degraded")))
    at = run_admin()
    assert any("degraded" in w.value for w in at.warning)


def test_unreachable_database_is_reported(backend):
    payload = health_payload(database={"reachable": False, "error": "locked"})
    backend.set("GET", "/health", FakeResponse(200, payload))
    at = run_admin()
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Database"] == "Unreachable"


def test_missing_process_stats_falls_back_to_info(backend):
    payload = health_payload(system={"python_version": "3.13", "platform": "Windows",
                                     "process_stats": "psutil not installed"})
    backend.set("GET", "/health", FakeResponse(200, payload))
    at = run_admin()
    assert not at.exception
    assert any("psutil not installed" in i.value for i in at.info)


def test_backend_unreachable_shows_error_not_crash(backend):
    backend.set("GET", "/health", unreachable())
    at = run_admin()
    assert not at.exception
    assert any("Could not reach backend" in e.value for e in at.error)


def test_backend_error_status_shows_detail(backend):
    backend.set("GET", "/health", FakeResponse(500, text="boom", json_error=True))
    at = run_admin()
    assert any("boom" in e.value for e in at.error)


def test_unreadable_json_shows_error(backend):
    backend.set("GET", "/health", FakeResponse(200, json_error=True))
    at = run_admin()
    assert not at.exception
    assert any("unreadable" in e.value for e in at.error)


def test_deep_check_sends_param_and_shows_reachable(backend):
    payload = health_payload(market_data={"reachable": True, "checked_ticker": "AAPL",
                                          "latency_ms": 120})
    backend.set("GET", "/health", FakeResponse(200, payload))
    at = run_admin()
    at.checkbox[0].check().run()
    assert not at.exception
    assert backend.calls_to("GET", "/health")[-1][2] == {"deep": True}
    assert any("Reachable - checked AAPL" in s.value for s in at.success)


def test_deep_check_unreachable_market_is_an_error(backend):
    payload = health_payload(status="degraded",
                             market_data={"reachable": False, "checked_ticker": "AAPL"})
    backend.set("GET", "/health", FakeResponse(200, payload))
    at = run_admin()
    at.checkbox[0].check().run()
    assert any("Not reachable" in e.value for e in at.error)
