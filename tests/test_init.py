"""Tests for init command."""

from pathlib import Path

import pytest

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


from click.testing import CliRunner

from confmirror.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestCliInit:
    def test_cli_init_defaults_to_cwd(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(main, ["init"])

        assert result.exit_code == 0
        assert (tmp_path / CONFIG_FILENAME).exists()
        assert (tmp_path / "mirror").is_dir()

    def test_cli_init_with_path(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "nested-project"

        result = runner.invoke(main, ["init", str(target)])

        assert result.exit_code == 0
        assert (target / CONFIG_FILENAME).exists()
        assert (target / "mirror").is_dir()

    def test_cli_init_refuses_existing_config(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / CONFIG_FILENAME).write_text("settings:\n  name: existing\n")

        result = runner.invoke(main, ["init"])

        assert result.exit_code == 1
        assert "已存在" in result.output

    def test_cli_init_dry_run(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        result = runner.invoke(main, ["init", "--dry-run"])

        assert result.exit_code == 0
        assert not (tmp_path / CONFIG_FILENAME).exists()

    def test_cli_init_json_success(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "json-project"

        result = runner.invoke(main, ["init", str(target), "--format", "json"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert data["status"] == "success"
        assert data["command"] == "init"
        assert str(target / CONFIG_FILENAME) in data["created"]

    def test_cli_init_json_error(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / CONFIG_FILENAME).write_text("settings:\n  name: existing\n")

        result = runner.invoke(main, ["init", "--format", "json"])

        assert result.exit_code == 1
        import json

        data = json.loads(result.output)
        assert data["status"] == "error"
        assert data["command"] == "init"
        assert CONFIG_FILENAME in data["existing"][0]
