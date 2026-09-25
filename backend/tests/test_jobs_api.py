"""Integration tests for /jobs."""

import pytest
from sqlalchemy.orm import Session

from app.models import Job
from app.models.enums import JobStatus
from tests.api_helpers import ApiUser


def test_create_and_get(owner: ApiUser) -> None:
    client = owner.create_client()
    job = owner.ok(
        "post",
        "/jobs",
        201,
        json={"client_id": client["id"], "title": "Repaint", "address": "1 Main St"},
    )

    assert (job["status"], job["client_id"], job["address"]) == (
        "quoted",
        client["id"],
        "1 Main St",
    )
    assert owner.ok("get", f"/jobs/{job['id']}") == job


def test_unknown_client_is_404(owner: ApiUser) -> None:
    response = owner.post(
        "/jobs", json={"client_id": "00000000-0000-0000-0000-000000000000", "title": "x"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Client not found"}


def test_list_filters_by_status_and_client(owner: ApiUser, db_session: Session) -> None:
    client = owner.create_client()
    first = owner.create_job(client["id"])
    owner.create_job(client["id"])
    owner.create_job()  # another client
    job = db_session.get(Job, first["id"])
    assert job is not None
    job.status = JobStatus.SCHEDULED
    db_session.flush()

    by_status = owner.ok("get", "/jobs", params={"status": "scheduled"})
    by_client = owner.ok("get", "/jobs", params={"client_id": client["id"]})

    assert [j["id"] for j in by_status["items"]] == [first["id"]]
    assert by_client["total"] == 2
    assert owner.ok("get", "/jobs")["total"] == 3


def test_patch_title_and_address(owner: ApiUser) -> None:
    job = owner.create_job()
    updated = owner.ok("patch", f"/jobs/{job['id']}", json={"title": "New title", "address": None})
    assert (updated["title"], updated["address"]) == ("New title", None)


def _set_status(session: Session, job_id: str, status: JobStatus) -> None:
    job = session.get(Job, job_id)
    assert job is not None
    job.status = status
    session.flush()


def test_board_moves_follow_the_transition_table(owner: ApiUser, db_session: Session) -> None:
    job = owner.create_job()
    _set_status(db_session, job["id"], JobStatus.APPROVED)  # Milestone 6 will do this

    for status in ("scheduled", "in_progress", "completed", "in_progress"):
        moved = owner.ok("patch", f"/jobs/{job['id']}", json={"status": status})
        assert moved["status"] == status


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobStatus.QUOTED, "approved"),  # only by approving a quote
        (JobStatus.QUOTED, "scheduled"),  # can't skip approval
        (JobStatus.COMPLETED, "paid"),  # only by recording payment
        (JobStatus.APPROVED, "completed"),  # no skipping steps
        (JobStatus.PAID, "completed"),  # paid is final
    ],
)
def test_disallowed_moves_are_409(
    owner: ApiUser, db_session: Session, current: JobStatus, target: str
) -> None:
    job = owner.create_job()
    _set_status(db_session, job["id"], current)

    response = owner.patch(f"/jobs/{job['id']}", json={"status": target})

    assert response.status_code == 409
    assert owner.ok("get", f"/jobs/{job['id']}")["status"] == current.value


def test_setting_the_same_status_is_a_no_op(owner: ApiUser) -> None:
    job = owner.create_job()
    assert owner.ok("patch", f"/jobs/{job['id']}", json={"status": "quoted"})["status"] == "quoted"


@pytest.mark.parametrize("body", [{"title": None}, {"status": None}, {"status": "bogus"}])
def test_invalid_updates_are_422(owner: ApiUser, body: dict[str, object]) -> None:
    job = owner.create_job()
    assert owner.patch(f"/jobs/{job['id']}", json=body).status_code == 422
