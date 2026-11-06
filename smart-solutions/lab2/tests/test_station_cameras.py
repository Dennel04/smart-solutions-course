import importlib.util
from html.parser import HTMLParser
from pathlib import Path
import socket
import sys
import threading
import time
from unittest import mock

import cv2
import numpy as np
import pytest

from src.camera_server import create_camera_app
from src.cameras import MockCamera
from src.e2e_demo import run_demo


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def wait_for(predicate):
    deadline = time.monotonic() + 2
    while not predicate():
        assert time.monotonic() < deadline
        time.sleep(0.01)


@pytest.fixture(autouse=True)
def no_network_or_usb(monkeypatch):
    import requests
    import urllib.request

    denied = mock.Mock(side_effect=AssertionError("real network/hardware is forbidden"))
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(requests.Session, "request", denied)
    monkeypatch.setattr(urllib.request, "urlopen", denied)
    monkeypatch.setattr(cv2, "VideoCapture", denied)
    yield
    denied.assert_not_called()


@pytest.fixture
def station_page(monkeypatch):
    source = Path(__file__).resolve().parents[2] / "lab1/src/station.py"
    monkeypatch.syspath_prepend(str(source.parent))
    spec = importlib.util.spec_from_file_location("lab1_camera_ui_test", source)
    station = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, station)
    spec.loader.exec_module(station)
    robot = mock.Mock(side_effect=AssertionError("camera UI must never call MG400"))
    monkeypatch.setattr(station, "MG400_CLIENT_FACTORY", robot)
    response = station.app.test_client().get("/")
    assert response.status_code == 200
    yield response.get_data(as_text=True)
    robot.assert_not_called()


@pytest.fixture
def camera_app():
    app = create_camera_app({name: MockCamera(name, target_fps=40) for name in ("table", "tool")})
    try:
        wait_for(lambda: all(item["available"] for item in app.extensions["camera_registry"].status().values()))
        yield app
    finally:
        app.extensions["camera_registry"].stop_all()


def test_station_embeds_existing_two_camera_ui_without_changing_drawing_controls(station_page, camera_app):
    elements = Elements(station_page)
    frames = [attrs for tag, attrs in elements.tags if tag == "iframe"]
    assert len(frames) == 1 and frames[0]["src"] == "http://127.0.0.1:5002/"
    assert frames[0]["title"] and frames[0]["referrerpolicy"] == "no-referrer"
    assert set(frames[0]["sandbox"].split()) == {"allow-scripts", "allow-same-origin"}
    ids = {attrs.get("id") for _, attrs in elements.tags}
    assert {"text", "font", "previewBtn", "drawBtn", "preview", "mode"} <= ids
    assert 'post("/api/text/preview")' in station_page and 'post("/api/text/draw")' in station_page
    camera_page = camera_app.test_client().get("/")
    assert camera_page.status_code == 200
    images = [attrs for tag, attrs in Elements(camera_page.get_data(as_text=True)).tags if tag == "img"]
    assert {image["src"] for image in images} == {"/stream/table.mjpg", "/stream/tool.mjpg"}
    assert all(image.get("alt") for image in images)
    status = camera_app.test_client().get("/api/cameras").get_json()
    assert status["scope"] == "local_station_only"
    assert set(status["cameras"]) == {"table", "tool"}
    assert all(item["available"] and item["configuration"]["synthetic"] for item in status["cameras"].values())
    assert not any("letter" in rule.rule or "text" in rule.rule for rule in camera_app.url_map.iter_rules())


def test_both_mock_snapshots_decode_as_distinct_real_jpeg_images(camera_app):
    pixels = []
    for name in ("table", "tool"):
        response = camera_app.test_client().get(f"/snapshot/{name}.jpg")
        assert response.status_code == 200 and response.mimetype == "image/jpeg"
        image = cv2.imdecode(np.frombuffer(response.data, dtype=np.uint8), cv2.IMREAD_COLOR)
        assert image is not None and image.shape == (2, 2, 3)
        assert f"MOCK {name.upper()}".encode() in response.data
        pixels.append(image)
    assert not np.array_equal(*pixels)


def test_table_and_tool_streams_can_be_consumed_simultaneously(camera_app):
    ready = threading.Barrier(3)
    release = threading.Event()
    errors, chunks = [], {}

    def consume(name):
        response = None
        try:
            response = camera_app.test_client().get(f"/stream/{name}.mjpg", buffered=False)
            assert response.status_code == 200
            chunks[name] = next(response.response)
            ready.wait(timeout=3)
            release.wait(timeout=3)
        except Exception as error:
            errors.append(error)
        finally:
            if response is not None:
                response.close()

    threads = [threading.Thread(target=consume, args=(name,)) for name in ("table", "tool")]
    try:
        for thread in threads:
            thread.start()
        ready.wait(timeout=3)
        assert set(chunks) == {"table", "tool"}
        for name, chunk in chunks.items():
            assert chunk.startswith(b"--frame\r\nContent-Type: image/jpeg\r\n")
            assert f"MOCK {name.upper()}".encode() in chunk
    finally:
        release.set()
        for thread in threads:
            thread.join(timeout=4)
    assert not errors and not any(thread.is_alive() for thread in threads)


@pytest.mark.parametrize("failed_name", ["table", "tool"])
def test_disconnected_camera_does_not_stop_other_camera_station_page_or_mock_jobs(station_page, tmp_path, failed_name):
    disconnected = threading.Event()

    class DisconnectableMock(MockCamera):
        def capture_frame(self, resource):
            if disconnected.is_set():
                raise RuntimeError("synthetic camera disconnected")
            return super().capture_frame(resource)

    sources = {name: (DisconnectableMock if name == failed_name else MockCamera)(name, target_fps=40)
               for name in ("table", "tool")}
    app = create_camera_app(sources)
    other = "tool" if failed_name == "table" else "table"
    try:
        wait_for(lambda: all(item["available"] for item in app.extensions["camera_registry"].status().values()))
        disconnected.set()
        wait_for(lambda: sources[failed_name].status()["state"] == "unavailable")
        assert app.test_client().get(f"/snapshot/{failed_name}.jpg").status_code == 503
        assert app.test_client().get(f"/stream/{failed_name}.mjpg").status_code == 503
        assert app.test_client().get(f"/snapshot/{other}.jpg").status_code == 200
        assert "Jaama kaamerad" in station_page and app.test_client().get("/").status_code == 200
        status = app.test_client().get("/api/cameras").get_json()["cameras"]
        assert not status[failed_name]["available"] and status[other]["available"]
        assert run_demo(tmp_path)["hardware_used"] is False
        disconnected.clear()
        wait_for(lambda: sources[failed_name].status()["available"])
        assert app.test_client().get(f"/snapshot/{failed_name}.jpg").status_code == 200
    finally:
        app.extensions["camera_registry"].stop_all()
