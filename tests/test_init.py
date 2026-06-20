"""Tests for init command."""

from pathlib import Path

from confmirror.config import CONFIG_FILENAME
from confmirror.init import execute_init
from confmirror.output import ExitCode


class TestExecuteInit:
    def test_execute_init_creates_config_and_dirs(self, tmp_path):
        target = tmp_path / "new-project"

        exit_code = execute_init(target)

        assert exit_code == ExitCode.SUCCESS
        assert (target / CONFIG_FILENAME).exists()
        assert (target / "mirror").is_dir()
        assert (target / "script-hooks").is_dir()
        assert (target / "logs").is_dir()
        config_text = (target / CONFIG_FILENAME).read_text(encoding="utf-8")
        assert f'name: "new-project"' in config_text

    def test_execute_init_refuses_existing_config(self, tmp_path):
        target = tmp_path / "existing-project"
        target.mkdir()
        (target / CONFIG_FILENAME).write_text("settings:\n  name: existing\n")

        exit_code = execute_init(target)

        assert exit_code == ExitCode.CONFIG_ERROR

    def test_execute_init_refuses_existing_mirror_dir(self, tmp_path):
        target = tmp_path / "existing-project"
        target.mkdir()
        (target / "mirror").mkdir()

        exit_code = execute_init(target)

        assert exit_code == ExitCode.CONFIG_ERROR

    def test_execute_init_dry_run_does_not_create(self, tmp_path):
        target = tmp_path / "dry-project"

        exit_code = execute_init(target, dry_run=True)

        assert exit_code == ExitCode.SUCCESS
        assert not (target / CONFIG_FILENAME).exists()

    def test_execute_init_json_success(self, tmp_path):
        target = tmp_path / "json-project"

        exit_code = execute_init(target, output_format="json")

        assert exit_code == ExitCode.SUCCESS
