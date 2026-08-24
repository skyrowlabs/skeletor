"""Not generated. If this fails, the skeleton is broken rather than the app."""

from __future__ import annotations


def test_healthz_reports_database_reachable(client) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True


def test_static_css_is_served(client) -> None:
    assert client.get("/static/app.css").status_code == 200
