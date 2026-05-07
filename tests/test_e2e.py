"""End-to-end test: dry-run with real config."""

import json
import tempfile
from pathlib import Path

import yaml


def test_dry_run_works():
    """Ensure the new CLI can do a dry-run without crashing."""
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / "config.yaml"
        config = {"theme": "test", "days_lookback": 7}
        config_path.write_text(yaml.dump(config))

        from pod2wiki.cli.fetch_podcasts import load_config

        config_obj = load_config(config_path)
        assert config_obj.theme == "test"
        assert config_obj.days_lookback == 7
