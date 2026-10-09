import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"

STREETS = json.loads((FIXTURES / "get_streets.json").read_text())
SCHEDULE_JSON = (FIXTURES / "single_street.json").read_text()
SCHEDULE = json.loads(SCHEDULE_JSON)

UNKNOWN_STREET = "Nope Street 1"
NO_SCHEDULE_RESPONSE = "[]"


@pytest.fixture
def fake_built_frontend(tmp_path, monkeypatch):
    static = tmp_path / "app" / "frontend" / "static"
    static.mkdir(parents=True)
    (static / "hello.txt").write_text("static ok")
    (tmp_path / "app" / "frontend" / "index.html").write_text("<html>index</html>")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def fake_ead():
    state = SimpleNamespace(get_calls=[], post_calls=[], is_down=False)

    def fake_get(url, **kwargs):
        state.get_calls.append({"url": url, **kwargs})
        if state.is_down:
            raise requests.ConnectionError("down")
        return SimpleNamespace(text=json.dumps(STREETS))

    def fake_post(url, data=None, **kwargs):
        state.post_calls.append({"url": url, "data": data, **kwargs})
        if state.is_down:
            raise requests.ConnectionError("down")
        if data["street"] == UNKNOWN_STREET:
            return SimpleNamespace(text=NO_SCHEDULE_RESPONSE)
        return SimpleNamespace(text=SCHEDULE_JSON)

    state.get, state.post = fake_get, fake_post
    return state


@pytest.fixture
def app_module(fake_built_frontend, fake_ead, monkeypatch):
    sys.modules.pop("app.main", None)
    module = importlib.import_module("app.main")
    monkeypatch.setattr(module, "get", fake_ead.get)
    monkeypatch.setattr(module, "post", fake_ead.post)
    yield module
    sys.modules.pop("app.main", None)


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)
