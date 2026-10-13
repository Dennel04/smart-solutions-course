import pytest

from server.app import create_app


def claim(client, atom_headers, valid_poll):
    return client.post("/api/atom/poll", headers=atom_headers, json=valid_poll)


def test_valid_letter_job_creation_normalizes_letter(create_letter):
    response = create_letter("a")
    assert response.status_code == 201
    job = response.get_json()
    assert job["job"] == "letter"
    assert job["arg"] == {"letter": "A"}
    assert job["status"] == "queued"
    assert job["created_at"].endswith("Z")
    assert job["expires_at"].endswith("Z")


def test_invalid_job_type_is_rejected(client, user_headers):
    response = client.post(
        "/api/jobs",
        headers=user_headers,
        json={"job": "move_robot", "arg": {}, "ttl_seconds": 60},
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "unknown_job"


def test_valid_pick_place_job_creation(create_pick_place):
    response = create_pick_place()
    assert response.status_code == 201
    assert response.get_json()["arg"] == {"routine": "source_to_finished"}


@pytest.mark.parametrize("routine", ["", "other", None])
def test_unknown_or_missing_pick_place_routine_is_rejected(create_pick_place, routine):
    response = create_pick_place(routine)
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_routine"


@pytest.mark.parametrize(
    "field,value",
    [
        ("x", 100),
        ("y", 20),
        ("z", -80),
        ("r", 0),
        ("speed", 20),
        ("pump", "on"),
        ("do", 1),
        ("repetitions", 2),
        ("trajectory", [[1, 2, 3]]),
    ],
)
def test_pick_place_direct_control_fields_are_rejected(create_pick_place, field, value):
    response = create_pick_place(extra_arg={field: value})
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "unexpected_field"


def test_invalid_letter_is_rejected(create_letter):
    response = create_letter("AB")
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_letter"


def test_expired_job_is_never_delivered(
    create_letter, clock, client, atom_headers, valid_poll, user_headers
):
    created = create_letter("E", ttl_seconds=1).get_json()
    clock.advance(2)
    response = claim(client, atom_headers, valid_poll)
    assert response.status_code == 200
    assert response.get_json()["job"] is None
    stored = client.get("/api/jobs/" + created["id"], headers=user_headers).get_json()
    assert stored["status"] == "expired"
    assert stored["reason"] == "ttl_expired"


def test_expired_pick_place_is_never_delivered(
    create_pick_place, clock, client, atom_headers, valid_poll, user_headers
):
    created = create_pick_place(ttl_seconds=1).get_json()
    clock.advance(2)
    assert claim(client, atom_headers, valid_poll).get_json()["job"] is None
    stored = client.get("/api/jobs/" + created["id"], headers=user_headers).get_json()
    assert stored["status"] == "expired"


def test_atom_key_is_required(client, valid_poll):
    response = client.post("/api/atom/poll", json=valid_poll)
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "atom_key_required"


def test_wrong_atom_key_is_rejected(client, valid_poll):
    response = client.post(
        "/api/atom/poll",
        headers={"Authorization": "Bearer wrong-test-key"},
        json=valid_poll,
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "invalid_atom_key"


def test_poll_updates_last_seen(client, atom_headers, valid_poll, user_headers):
    response = claim(client, atom_headers, valid_poll)
    assert response.status_code == 200
    status = client.get("/api/status", headers=user_headers).get_json()["atom"]
    assert status["status"] == "online"
    assert status["last_seen"] == "2030-01-01T12:00:00Z"
    assert status["device"]["poll_interval_ms"] == 1000


def test_queued_job_can_be_claimed(create_letter, client, atom_headers, valid_poll):
    created = create_letter("Q").get_json()
    delivered = claim(client, atom_headers, valid_poll).get_json()["job"]
    assert delivered["id"] == created["id"]
    assert delivered["status"] == "claimed"


def test_claimed_and_completed_job_is_not_delivered_twice(
    create_letter, client, atom_headers, valid_poll
):
    created = create_letter("D").get_json()
    first = claim(client, atom_headers, valid_poll).get_json()["job"]
    assert first["id"] == created["id"]
    assert claim(client, atom_headers, valid_poll).get_json()["job"] is None
    result = client.post(
        "/api/atom/result",
        headers=atom_headers,
        json={"id": created["id"], "status": "done", "result": {"simulated": True}},
    )
    assert result.status_code == 200
    assert claim(client, atom_headers, valid_poll).get_json()["job"] is None


def test_duplicate_result_reporting_is_idempotent(
    create_letter, client, atom_headers, valid_poll
):
    job = create_letter("I").get_json()
    claim(client, atom_headers, valid_poll)
    payload = {"id": job["id"], "status": "done", "result": {"simulated": True}}
    first = client.post("/api/atom/result", headers=atom_headers, json=payload)
    second = client.post("/api/atom/result", headers=atom_headers, json=payload)
    assert first.get_json()["duplicate"] is False
    assert second.status_code == 200
    assert second.get_json()["duplicate"] is True


def test_conflicting_duplicate_result_is_rejected(
    create_letter, client, atom_headers, valid_poll
):
    job = create_letter("C").get_json()
    claim(client, atom_headers, valid_poll)
    client.post(
        "/api/atom/result",
        headers=atom_headers,
        json={"id": job["id"], "status": "done", "result": {"value": 1}},
    )
    conflict = client.post(
        "/api/atom/result",
        headers=atom_headers,
        json={"id": job["id"], "status": "done", "result": {"value": 2}},
    )
    assert conflict.status_code == 409
    assert conflict.get_json()["error"]["code"] == "state_conflict"


def test_refused_result_is_stored_and_visible(
    create_letter, client, atom_headers, valid_poll, user_headers
):
    job = create_letter("R").get_json()
    claim(client, atom_headers, valid_poll)
    client.post(
        "/api/atom/result",
        headers=atom_headers,
        json={"id": job["id"], "status": "refused", "reason": "mock_station_refused"},
    )
    stored = client.get("/api/jobs/" + job["id"], headers=user_headers).get_json()
    assert stored["status"] == "refused"
    assert stored["reason"] == "mock_station_refused"


def test_completed_result_is_stored_and_visible(
    create_letter, client, atom_headers, valid_poll, user_headers
):
    job = create_letter("S").get_json()
    claim(client, atom_headers, valid_poll)
    client.post(
        "/api/atom/result",
        headers=atom_headers,
        json={"id": job["id"], "status": "done", "result": {"letter": "S"}},
    )
    stored = client.get("/api/jobs/" + job["id"], headers=user_headers).get_json()
    assert stored["status"] == "done"
    assert stored["result"] == {"letter": "S"}


def test_coordinates_and_direct_motion_fields_are_rejected(client, user_headers):
    response = client.post(
        "/api/jobs",
        headers=user_headers,
        json={
            "job": "letter",
            "arg": {"letter": "A", "x": 100, "speed": 50, "pump": "on"},
        },
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "unexpected_field"


def test_online_stale_offline_status_without_sleep(
    client, atom_headers, valid_poll, user_headers, clock
):
    claim(client, atom_headers, valid_poll)
    status = lambda: client.get("/api/status", headers=user_headers).get_json()["atom"][
        "status"
    ]
    assert status() == "online"
    clock.advance(11)
    assert status() == "stale"
    clock.advance(20)
    assert status() == "offline"


def test_post_office_exposes_no_camera_routes(app, client, user_headers):
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert not any("camera" in rule or "stream" in rule for rule in rules)
    assert client.get("/api/cameras", headers=user_headers).status_code == 404


def test_user_api_requires_authentication(client):
    response = client.get("/api/jobs")
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "user_auth_required"


def test_unknown_job_returns_json_404(client, user_headers):
    response = client.get("/api/jobs/not-a-real-job", headers=user_headers)
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "job_not_found"


def test_user_page_creates_and_lists_letter_job(client, user_headers):
    created = client.post(
        "/jobs",
        headers=user_headers,
        data={"job": "letter", "letter": "B", "ttl_seconds": "60"},
    )
    assert created.status_code == 302
    page = client.get("/", headers=user_headers)
    assert page.status_code == 200
    assert b"queued" in page.data
    assert b"Lab 2 postkontor" in page.data


def test_user_page_creates_predefined_pick_place_job(client, user_headers):
    created = client.post(
        "/jobs",
        headers=user_headers,
        data={
            "job": "pick_place",
            "routine": "source_to_finished",
            "ttl_seconds": "60",
        },
    )
    assert created.status_code == 302
    page = client.get("/", headers=user_headers)
    assert b"pick_place" in page.data
    assert b"source_to_finished" in page.data


def test_startup_refuses_missing_required_secrets(tmp_path, monkeypatch):
    monkeypatch.delenv("ATOM_API_KEY", raising=False)
    monkeypatch.delenv("POST_OFFICE_PASSWORD", raising=False)
    common = {"TESTING": True, "DATABASE_PATH": str(tmp_path / "missing.sqlite3")}
    with pytest.raises(RuntimeError, match="ATOM_API_KEY"):
        create_app(dict(common, ATOM_API_KEY=None, USER_PASSWORD="configured"))
    with pytest.raises(RuntimeError, match="POST_OFFICE_PASSWORD"):
        create_app(dict(common, ATOM_API_KEY="configured", USER_PASSWORD=None))
