"""Admin/glassbox read endpoints that had no direct coverage before V3.0."""

from __future__ import annotations

import pytest

from tests.helpers import api_client, memory_db

pytestmark = [pytest.mark.integration, pytest.mark.api]


@pytest.fixture()
def client():
    engine, factory = memory_db()
    try:
        with api_client(factory) as test_client:
            yield test_client
    finally:
        engine.dispose()


def test_system_jobs_and_schedule_contract(client) -> None:
    jobs = client.get("/api/system/jobs")
    assert jobs.status_code == 200
    assert isinstance(jobs.json()["data"], list)

    schedule = client.get("/api/system/schedule")
    assert schedule.status_code == 200
    assert "jobs" in schedule.json()


def test_schedule_check_list_and_detail_404(client) -> None:
    listing = client.get("/api/system/schedule-check")
    assert listing.status_code == 200
    assert {"data", "schedule"} <= set(listing.json())
    missing = client.get("/api/system/schedule-check/not-a-real-id")
    assert missing.status_code == 404


def test_unknown_job_run_returns_404(client) -> None:
    response = client.post("/api/system/jobs/not_a_job/run")
    assert response.status_code == 404


def test_quality_gate_and_coverage_contract(client) -> None:
    gate = client.get("/api/system/quality-gate")
    assert gate.status_code == 200
    assert "status" in gate.json()

    coverage = client.get("/api/system/coverage")
    assert coverage.status_code == 200
    assert isinstance(coverage.json(), (dict, list))


def test_glassbox_methods_observations_status(client) -> None:
    methods = client.get("/api/v2/methods")
    assert methods.status_code == 200
    assert {"items", "total"} <= set(methods.json())

    observations = client.get("/api/v2/observations", params={"limit": 5})
    assert observations.status_code == 200
    assert {"items", "total"} <= set(observations.json())

    status = client.get("/api/v2/status")
    assert status.status_code == 200


def test_timeline_powers_contract(client) -> None:
    powers = client.get("/api/v2/timeline/powers")
    assert powers.status_code == 200
    assert {"gdp", "reserve"} <= set(powers.json())
