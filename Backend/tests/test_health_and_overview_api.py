import main
from tests.conftest import seed_instrument


# --- GET /health ---

def test_health_shallow_reports_ok_and_instrument_count(client, db):
    seed_instrument(db, "AAPL")
    seed_instrument(db, "MSFT")

    r = client.get("/health")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"]["reachable"] is True
    assert body["database"]["instrument_count"] == 2
    assert "market_data" not in body  # deep check is opt-in only


def test_health_deep_reachable_keeps_status_ok(client, monkeypatch):
    monkeypatch.setattr(main, "get_live_price", lambda ticker: 100.0)

    r = client.get("/health", params={"deep": "true"})

    body = r.json()
    assert body["market_data"]["reachable"] is True
    assert body["status"] == "ok"


def test_health_deep_unreachable_marks_status_degraded(client, monkeypatch):
    monkeypatch.setattr(main, "get_live_price", lambda ticker: None)

    r = client.get("/health", params={"deep": "true"})

    body = r.json()
    assert body["market_data"]["reachable"] is False
    assert body["status"] == "degraded"


def test_health_includes_rate_limit_stats(client, monkeypatch):
    monkeypatch.setattr(main, "get_rate_limit_state", lambda: {"hits": 3, "last_hit_at": None})

    r = client.get("/health")

    assert r.json()["rate_limit"] == {"hits": 3, "last_hit_at": None}


# --- GET /markets/overview ---

def test_markets_overview_passes_through(client, monkeypatch):
    fake_overview = {"by_type": {"stocks": []}, "by_country": {"US": []}}
    monkeypatch.setattr(main, "get_market_overview", lambda force=False: fake_overview)

    r = client.get("/markets/overview")

    assert r.status_code == 200
    assert r.json() == fake_overview


def test_markets_overview_force_param_is_threaded_through(client, monkeypatch):
    captured = {}

    def fake_overview(force=False):
        captured["force"] = force
        return {"by_type": {}, "by_country": {}}

    monkeypatch.setattr(main, "get_market_overview", fake_overview)

    client.get("/markets/overview")
    assert captured["force"] is False

    client.get("/markets/overview", params={"force": "true"})
    assert captured["force"] is True


# --- Unhandled-exception global handler ---

def test_unhandled_exception_returns_json_not_plain_text(client, monkeypatch):
    def boom(ticker):
        raise RuntimeError("something broke")

    monkeypatch.setattr(main, "get_live_price", boom)

    r = client.post("/instruments", json={"ticker": "AAPL", "type": "Stock"})

    assert r.status_code == 500
    assert r.headers["content-type"].startswith("application/json")
    assert "detail" in r.json()
