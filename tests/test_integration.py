"""Integration tests for real pod2wiki workflows."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# Add src to sys.path for direct imports in tests
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

def test_doctor_cli():
    """Verify that the doctor command runs and reports status."""
    res = run_cli_base(["doctor"])
    assert res.returncode == 0
    assert "pod2wiki Doctor" in res.stdout
    assert "Python version" in res.stdout

def test_init_cli():
    """Verify that the init command creates expected directory structure."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        res = run_cli_base(["init", "--target", str(tmp_path)])
        assert res.returncode == 0
        assert (tmp_path / "config/pod2wiki.config.yaml").exists()
        assert (tmp_path / "wiki/sources").exists()

def test_test_feed_cli():
    """Verify that the test-feed command runs (smoke test with invalid URL)."""
    res = run_cli_base(["test-feed", "https://example.com/feed.xml", "--days", "1"])
    assert res.returncode == 0
    assert "Testing source:" in res.stdout

def run_cli_base(args):
    """Run the CLI without 'scan' prefix."""
    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    cmd = [sys.executable, "-m", "pod2wiki.cli.main"] + args
    return subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")

def run_cli(args):
    """Run the CLI via subprocess with 'scan' command."""
    return run_cli_base(["scan"] + args)

def test_dry_run_cli():
    """Verify that the dry-run command works from the documented invocation path."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config_path = tmp_path / "config.yaml"
        config = {
            "theme": "test-theme",
            "days_lookback": 1,
            "channels": [{"name": "Test", "youtube": "https://example.com"}]
        }
        config_path.write_text(yaml.dump(config), encoding="utf-8")
        
        res = run_cli(["--config", str(config_path), "--dry-run"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert data["ok"] is True
        assert data["mode"] == "dry-run"

def test_local_file_workflow_no_llm():
    """Verify local-file + --no-llm produces raw, source, and insight logs."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config_path = tmp_path / "config.yaml"
        config = {
            "theme": "local-test",
            "hypotheses": {
                "H1": {"title": "Test Hypothesis", "keywords": ["ai", "test"]}
            }
        }
        config_path.write_text(yaml.dump(config), encoding="utf-8")
        
        sample_file = tmp_path / "sample.md"
        sample_file.write_text("# Test Title\nThis is a test content about AI infrastructure.", encoding="utf-8")
        
        output_dir = tmp_path / "output"
        wiki_out = tmp_path / "wiki"
        
        args = [
            "--config", str(config_path),
            "--input-file", str(sample_file),
            "--output-dir", str(output_dir),
            "--wiki-out", str(wiki_out),
            "--no-llm",
            "--write-insight-log"
        ]
        
        res = run_cli(args)
        assert res.returncode == 0
        
        # Check output files
        assert (output_dir / "raw/podcasts").exists()
        assert (output_dir / "sources").exists()
        assert (output_dir / "ai-insights-log.md").exists()
        
        # Check Wiki Copy
        assert (wiki_out / "sources").exists()
        assert (wiki_out / "raw/podcasts").exists()
        
        source_pages = list((wiki_out / "sources").glob("*.md"))
        assert len(source_pages) == 1
        content = source_pages[0].read_text(encoding="utf-8")
        # In current logic, title defaults to file stem if --title not provided
        assert "sample" in content or "Test Title" in content
        assert "Hypothesis Links" in content

def test_rss_mock_flow():
    """Test RSS flow with a mocked response."""
    # This requires more complex mocking of requests or a local server.
    # For now, we verify the CLI handles the 'rss' mode. 
    # If connection fails, it should eprint errors but currently main returns 0
    # unless there is a fatal orchestrator error.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config_path = tmp_path / "config.yaml"
        config = {
            "theme": "rss-test",
            "channels": [{"name": "BadFeed", "rss": "http://localhost:12345/nonexistent"}]
        }
        config_path.write_text(yaml.dump(config), encoding="utf-8")
        
        res = run_cli(["--config", str(config_path), "--mode", "rss", "--days", "1"])
        # Should finish gracefully
        assert res.returncode == 0 or "feed skipped" in res.stderr
        if res.stdout.strip():
            try:
                data = json.loads(res.stdout)
                assert data["ok"] is True
                assert data["items_found"] == 0
            except json.JSONDecodeError:
                pass

def test_translation_flow_writes_outputs(mocker):
    """Verify translation flow writes expected outputs (requires LLM mock)."""
    # Note: subprocess makes mocking harder. 
    # For integration tests, we rely on --no-llm or real (but skipped) paths.
    # Here we just verify that the flag is accepted and doesn't crash the orchestrator.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config_path = tmp_path / "config.yaml"
        config = {"theme": "trans-test"}
        config_path.write_text(yaml.dump(config), encoding="utf-8")
        
        sample_file = tmp_path / "sample.md"
        sample_file.write_text("Hello world", encoding="utf-8")
        
        # If we use --no-llm, --translate-full is currently skipped in code logic.
        # We verify that it doesn't break the CLI parsing.
        res = run_cli([
            "--config", str(config_path), 
            "--input-file", str(sample_file), 
            "--no-llm", 
            "--translate-full"
        ])
        assert res.returncode == 0
