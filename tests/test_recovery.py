"""Tests for run state recovery and retry logic."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

def run_cli_base(args):
    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    cmd = [sys.executable, "-m", "pod2wiki.cli.main"] + args
    return subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")

def test_retry_failed_flow():
    """Verify that --retry-failed actually re-processes failed items."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        config_path = tmp_path / "config.yaml"
        # We need a config that will cause a failure or we mock it.
        # Here, we'll manually inject a failed item into the DB to test the CLI wiring.
        config = {"theme": "recovery-test"}
        config_path.write_text(yaml.dump(config))
        
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        
        # 1. Create a dummy run with a failed item manually
        from pod2wiki.persistence.state import RunStateManager
        from pod2wiki.models import FileItem
        state_mgr = RunStateManager(output_dir / "pod2wiki_v1.db")
        run_id = state_mgr.create_run({"test": "initial"})
        
        failed_item = FileItem(
            id="file:fail.md",
            title="Failed Item",
            channel="Test",
            date="2026-05-08",
            url="http://example.com",
            raw_text="Some content",
            file_path=tmp_path / "fail.md"
        )
        (tmp_path / "fail.md").write_text("content")
        state_mgr.log_item_stage(run_id, failed_item, "failed", "Simulated error")
        state_mgr.finish_run(run_id, "failed")
        
        # 2. Run pod2wiki runs to verify visibility
        res_list = run_cli_base(["runs", "--output-dir", str(output_dir)])
        assert res_list.returncode == 0
        assert run_id in res_list.stdout
        
        # 3. Run --retry-failed
        # We use --no-llm so it succeeds this time
        res_retry = run_cli_base([
            "scan",
            "--config", str(config_path),
            "--output-dir", str(output_dir),
            "--retry-failed", run_id,
            "--no-llm"
        ])
        
        assert res_retry.returncode == 0
        assert "Retrying 1 failed items" in res_retry.stdout
        
        # 4. Verify DB updated
        details = state_mgr.get_run_details(run_id)
        # Note: the orchestrator creates a NEW run for the retry, 
        # but the log_item_stage in my current impl uses the NEW run_id.
        # Let's check the latest run in DB.
        recent = state_mgr.get_recent_runs(1)
        new_run_id = recent[0]["id"]
        assert new_run_id != run_id
        
        new_details = state_mgr.get_run_details(new_run_id)
        assert len(new_details) == 1
        assert new_details[0]["stage"] == "written"
        
        # Release handles for Windows
        del state_mgr
        import gc
        gc.collect()
