"""Integration tests for the pod2wiki web console with authentication."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import os
import shutil
import yaml

from pod2wiki.web.app import app

# We'll use a session-scoped root for tests to avoid constant deletions failing on Win
TEST_ROOT = Path("output/test_web_run")

@pytest.fixture(scope="function")
def client(monkeypatch):
    """Provide a fresh TestClient and isolated environment for each test."""
    # Create a unique subdir for this test function to avoid collisions
    import uuid
    test_dir = TEST_ROOT / uuid.uuid4().hex
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "sources").mkdir(exist_ok=True)
    (test_dir / "raw/podcasts").mkdir(parents=True, exist_ok=True)
    
    monkeypatch.setenv("POD2WIKI_OUTPUT", str(test_dir))
    
    # Also set a default config path that exists
    cfg_path = test_dir / "config.yaml"
    cfg_path.write_text("theme: test\nllm:\n  provider: p\n  model: m\nhypotheses: {}\npresets: {}")
    monkeypatch.setenv("POD2WIKI_CONFIG", str(cfg_path))

    with TestClient(app) as c:
        yield c
    
    # Cleanup (best effort)
    try: shutil.rmtree(test_dir, ignore_errors=True)
    except: pass

def get_auth_cookie(client):
    """Helper to perform first-time admin setup and get cookie."""
    resp = client.post("/login", data={"username": "testadmin", "password": "password"}, follow_redirects=False)
    return resp.cookies.get("pod2wiki_session")

def test_web_auth_redirection(client):
    """Verify that protected routes redirect to login when not authenticated."""
    response = client.get("/runs", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

def test_web_first_time_setup(client):
    """Verify that the first login creates an admin account."""
    response = client.get("/login")
    assert response.status_code == 200
    assert "First Time Setup" in response.text
    
    resp = client.post("/login", data={"username": "admin", "password": "pw"}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.cookies.get("pod2wiki_session") == "admin"

def test_web_dashboard_authenticated(client):
    cookie = get_auth_cookie(client)
    response = client.get("/", cookies={"pod2wiki_session": cookie})
    assert response.status_code == 200
    # Use a more flexible check for title or body content
    assert "Execution History" in response.text
    assert "testadmin" in response.text

def test_web_sources_management(client):
    cookie = get_auth_cookie(client)
    cfg_path = Path(os.environ["POD2WIKI_CONFIG"])
    
    # 1. Add
    data = {"name": "NewYT", "url": "url1", "kind": "youtube"}
    resp = client.post("/sources/add", data=data, cookies={"pod2wiki_session": cookie}, follow_redirects=False)
    assert resp.status_code == 303
    
    # 2. Verify
    cfg = yaml.safe_load(cfg_path.read_text())
    assert len(cfg["channels"]) == 1
    
    # 3. Delete
    client.post("/sources/delete", data={"index": 0, "kind": "youtube"}, cookies={"pod2wiki_session": cookie})
    cfg = yaml.safe_load(cfg_path.read_text())
    assert len(cfg["channels"]) == 0

def test_web_settings_update(client):
    cookie = get_auth_cookie(client)
    cfg_path = Path(os.environ["POD2WIKI_CONFIG"])
    
    data = {
        "provider": "new_p", "model": "new_m", "max_tokens": "500", "wiki_out": "new_w",
        "whisper_model": "small", "whisper_clip": "100", "whisper_threshold": "500"
    }
    resp = client.post("/settings/update", data=data, cookies={"pod2wiki_session": cookie}, follow_redirects=False)
    assert resp.status_code == 303
    
    cfg = yaml.safe_load(cfg_path.read_text())
    assert cfg["llm"]["provider"] == "new_p"
    assert cfg["wiki_root"] == "new_w"

def test_web_scan_estimate_authenticated(client):
    cookie = get_auth_cookie(client)
    data = {"mode": "all", "days": "7", "no_llm": "true", "config_path": os.environ["POD2WIKI_CONFIG"]}
    response = client.post("/api/scan/estimate", data=data, cookies={"pod2wiki_session": cookie})
    assert response.status_code == 200
    assert "Pre-run Workload & Cost Estimate" in response.text

def test_web_save_preset_workflow(client):
    cookie = get_auth_cookie(client)
    cfg_path = Path(os.environ["POD2WIKI_CONFIG"])
    
    data = {
        "name": "MyPreset", "mode": "rss", "days": "3", "no_llm": "true",
        "config_path": str(cfg_path), "wiki_out": "wiki_p"
    }
    resp = client.post("/scan/presets/save", data=data, cookies={"pod2wiki_session": cookie}, follow_redirects=False)
    assert resp.status_code == 303
    
    cfg = yaml.safe_load(cfg_path.read_text())
    assert "MyPreset" in cfg["presets"]

def test_web_replay_workflow_auth(client):
    """Verify that replay access requires authentication."""
    response = client.get("/runs/some-id", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
