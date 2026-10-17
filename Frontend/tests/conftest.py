from pathlib import Path

import pytest
import requests
import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parent.parent


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", json_error=False):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("not JSON")
        return self._json_data


class FakeBackend:
    """
    Routes the pages' requests.request calls to canned responses, keyed by
    (METHOD, path) where path excludes the host. A value may be a
    FakeResponse, a callable(params, json) -> FakeResponse, or an Exception
    to raise (simulating an unreachable backend). Unrouted calls fail loudly
    so a test can't silently hit the real network.
    """

    def __init__(self):
        self.routes = {}
        self.calls = []

    def set(self, method, path, response):
        self.routes[(method.upper(), path)] = response

    def __call__(self, method, url, **kwargs):
        path = "/" + url.split("://", 1)[-1].split("/", 1)[-1]
        self.calls.append((method.upper(), path, kwargs.get("params"), kwargs.get("json")))
        route = self.routes.get((method.upper(), path))
        if route is None:
            raise AssertionError(f"Unrouted backend call: {method} {path}")
        if isinstance(route, Exception):
            raise route
        if callable(route):
            return route(kwargs.get("params"), kwargs.get("json"))
        return route

    def calls_to(self, method, path):
        return [c for c in self.calls if c[0] == method.upper() and c[1] == path]


@pytest.fixture()
def backend(monkeypatch):
    fake = FakeBackend()
    monkeypatch.setattr(requests, "request", fake)
    st.cache_data.clear()
    yield fake
    st.cache_data.clear()


def page_path(name):
    return str(FRONTEND_DIR / name)


def unreachable():
    return requests.exceptions.ConnectionError("refused")
