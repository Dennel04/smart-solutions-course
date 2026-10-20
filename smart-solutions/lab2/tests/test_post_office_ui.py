"""Rendered HTML contract and form behavior; no browser or hardware required."""

from html.parser import HTMLParser
import json

from flask import render_template
import pytest


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.stack = []
        self.feed(html)
        assert not self.stack, "Unclosed HTML elements"

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "text": "", "parents": tuple(self.stack)}
        self.elements.append(node)
        if tag not in {"meta", "input", "br", "hr", "link", "img", "col"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        assert self.stack and self.stack[-1]["tag"] == tag, "Mismatched HTML tag: " + tag
        self.stack.pop()

    def handle_data(self, text):
        for node in self.stack:
            node["text"] += text

    def tagged(self, tag):
        return [node for node in self.elements if node["tag"] == tag]


def test_page_has_labeled_unchanged_form_contract(client, user_headers):
    page = Page(client.get("/", headers=user_headers).get_data(as_text=True))
    form, = page.tagged("form")
    assert form["attrs"]["method"] == "post"
    assert form["attrs"]["action"] == "/jobs"
    fields = page.tagged("input") + page.tagged("select")
    assert {node["attrs"]["name"] for node in fields} == {
        "job", "letter", "routine", "ttl_seconds"
    }
    for node in fields:
        assert any(label["attrs"].get("for") == node["attrs"]["id"]
                   for label in page.tagged("label"))
        assert form in node["parents"]
    assert [node["attrs"]["value"] for node in page.tagged("option")] == [
        "letter", "pick_place", "source_to_finished"
    ]
    ttl, = [node for node in fields if node["attrs"]["name"] == "ttl_seconds"]
    assert ttl["attrs"]["value"] == "60"
    assert "required" in ttl["attrs"]
    letter, = [node for node in fields if node["attrs"]["name"] == "letter"]
    assert "required" not in letter["attrs"]  # Pick-place needs no letter.
    # Both fields remain usable when JavaScript is disabled.
    for node in fields:
        assert "disabled" not in node["attrs"]
        assert not any("hidden" in parent["attrs"] for parent in node["parents"])
    help_ids = {node["attrs"].get("id") for node in page.elements}
    for node in fields:
        for help_id in node["attrs"].get("aria-describedby", "").split():
            assert help_id in help_ids
    assert "Töid ei ole." in page.tagged("table")[0]["text"]


@pytest.mark.parametrize(
    "job_type,letter,expected",
    [("letter", "b", {"letter": "B"}),
     ("pick_place", "", {"routine": "source_to_finished"})],
)
def test_form_submits_both_job_types_with_all_visible_fields(
    client, user_headers, job_type, letter, expected
):
    response = client.post(
        "/jobs", headers=user_headers,
        data={"job": job_type, "letter": letter,
              "routine": "source_to_finished", "ttl_seconds": "30"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    page = Page(response.get_data(as_text=True))
    jobs = client.get("/api/jobs", headers=user_headers).get_json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["arg"] == expected
    assert jobs[0]["job"] == job_type
    assert jobs[0]["status"] == "queued"
    assert jobs[0]["id"] in page.tagged("table")[0]["text"]


def test_invalid_form_still_shows_error_and_does_not_create_job(client, user_headers):
    response = client.post(
        "/jobs", headers=user_headers,
        data={"job": "letter", "letter": "!", "ttl_seconds": "60"},
        follow_redirects=True,
    )
    page = Page(response.get_data(as_text=True))
    assert any(node["attrs"].get("role") == "alert" and node["text"]
               for node in page.tagged("p"))
    assert client.get("/api/jobs", headers=user_headers).get_json()["jobs"] == []


def test_render_preserves_full_values_and_escapes_untrusted_content(app):
    hostile = '<script>alert("test")</script><img src=x onerror=alert(1)>'
    job = {
        "id": "long-job-id-" * 20 + hostile,
        "job": "letter", "arg": {"letter": hostile}, "status": "refused",
        "created_at": "2030-01-01T12:00:00.123456Z",
        "result": {"detail": hostile}, "reason": hostile,
    }
    with app.test_request_context():
        page = Page(render_template(
            "index.html", jobs=[job], default_ttl=60, error=hostile,
            atom={"status": "offline", "last_seen": "2030-01-01T11:59:00Z"},
        ))
    assert not page.tagged("img")
    script, = page.tagged("script")
    assert hostile not in script["text"]
    assert "src" not in script["attrs"]
    codes = [node["text"] for node in page.tagged("code")]
    assert job["id"] in codes
    assert "2030-01-01T11:59:00Z" in codes
    assert page.tagged("time")[0]["text"] == job["created_at"]
    assert page.tagged("time")[0]["attrs"]["datetime"] == job["created_at"]
    for value in (job["arg"], job["result"], job["reason"]):
        assert any(json.loads(code) == value for code in codes if code.startswith(('"', '{')))
    assert len(page.tagged("td")) == 6
    assert all(node["attrs"].get("scope") == "col" for node in page.tagged("th"))
    assert len(page.tagged("th")) == 6
    assert any(node["attrs"].get("role") == "alert" and hostile in node["text"]
               for node in page.tagged("p"))


def test_page_and_form_remain_authenticated(client):
    assert client.get("/").status_code == 401
    assert client.post("/jobs", data={"job": "letter", "letter": "A"}).status_code == 401


@pytest.mark.parametrize("state,label", [
    ("queued", "Ootel"), ("claimed", "Vastu võetud"), ("done", "Lõpetatud"),
    ("refused", "Keeldutud"), ("expired", "Aegunud"),
])
def test_job_status_has_readable_text_as_well_as_machine_value(app, state, label):
    with app.test_request_context():
        page = Page(render_template(
            "index.html", default_ttl=60, error=None,
            atom={"status": "offline", "last_seen": None},
            jobs=[{"id": "ui-test", "job": "letter", "arg": {"letter": "A"},
                   "status": state, "created_at": "2030-01-01T12:00:00Z",
                   "result": None, "reason": None}],
        ))
    table = page.tagged("table")[0]["text"]
    assert label in table and state in table


@pytest.mark.parametrize("state,expected", [
    ("online", "Roboti töö sõltub jaama kohalikust loast."),
    ("stale", "Töö vastuvõtmine pole kinnitatud."),
    ("offline", "Uus töö jääb järjekorda ja võib enne vastuvõtmist aeguda."),
])
def test_atom_state_explains_execution_limits(app, state, expected):
    with app.test_request_context():
        page = Page(render_template(
            "index.html", jobs=[], default_ttl=60, error=None,
            atom={"status": state, "last_seen": None},
        ))
    assert expected in page.tagged("main")[0]["text"]
    assert "Pole veel ühendunud" in page.tagged("main")[0]["text"]


def test_ui_loads_no_external_styles_scripts_or_fonts(client, user_headers):
    page = Page(client.get("/", headers=user_headers).get_data(as_text=True))
    assert not page.tagged("link")
    assert all("src" not in node["attrs"] for node in page.tagged("script"))
    assert not any("http://" in node["text"] or "https://" in node["text"]
                   for node in page.tagged("style"))
