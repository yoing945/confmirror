"""Tests for config module."""

import logging
from unittest.mock import MagicMock

import pytest

from confmirror.config import (
    CONFIG_FILENAME,
    Config,
    ConfigKeys,
    ModuleConfig,
    Settings,
    load_config,
    resolve_config_path,
    validate_config_structure,
    validate_yaml_syntax,
)


class TestValidateYamlSyntax:
    def test_valid_yaml(self, tmp_path):
        path = tmp_path / "confmirror.yaml"
        path.write_text("settings:\n  name: test\n")
        is_valid, error = validate_yaml_syntax(path)
        assert is_valid is True
        assert error == ""

    def test_invalid_yaml(self, tmp_path):
        path = tmp_path / "confmirror.yaml"
        path.write_text("settings:\n  name: [unclosed\n")
        is_valid, error = validate_yaml_syntax(path)
        assert is_valid is False
        assert "YAML" in error


class TestValidateConfigStructure:
    def test_valid_structure(self):
        config = {
            ConfigKeys.SECTION_SETTINGS: {"name": "test"},
            ConfigKeys.SECTION_MODULES: [{ConfigKeys.MOD_NAME: "ssh"}],
        }
        assert validate_config_structure(config) is True

    def test_settings_not_dict(self):
        config = {ConfigKeys.SECTION_SETTINGS: "bad"}
        assert validate_config_structure(config) is False

    def test_modules_not_list(self):
        config = {ConfigKeys.SECTION_MODULES: "bad"}
        assert validate_config_structure(config) is False

    def test_module_missing_name(self):
        config = {ConfigKeys.SECTION_MODULES: [{}]}
        assert validate_config_structure(config) is False


class TestResolveConfigPath:
    def test_default_returns_cwd_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        path = resolve_config_path()

        assert path == tmp_path / CONFIG_FILENAME

    def test_custom_file_path(self, tmp_path):
        config_file = tmp_path / "custom.yaml"
        config_file.write_text("settings:\n  name: test\n")

        path = resolve_config_path(str(config_file))

        assert path == config_file

    def test_custom_directory_path_appends_filename(self, tmp_path):
        config_dir = tmp_path / "config-dir"
        config_dir.mkdir()

        path = resolve_config_path(str(config_dir))

        assert path == config_dir / CONFIG_FILENAME

    def test_global_file_path(self, tmp_path, monkeypatch):
        config_file = tmp_path / "global.yaml"
        config_file.write_text("settings:\n  name: test\n")
        monkeypatch.setattr(
            "confmirror.config.get_global_config_value",
            lambda key: str(config_file),
        )

        path = resolve_config_path()

        assert path == config_file

    def test_global_directory_path_appends_filename(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "global-dir"
        config_dir.mkdir()
        monkeypatch.setattr(
            "confmirror.config.get_global_config_value",
            lambda key: str(config_dir),
        )

        path = resolve_config_path()

        assert path == config_dir / CONFIG_FILENAME


class TestLoadConfig:
    def test_loads_defaults(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "confmirror.yaml"
        config_file.write_text("modules:\n  - name: ssh\n")

        config = load_config(str(config_file))
        settings = config.settings

        assert settings.name == tmp_path.name
        assert str(settings.backup_root) == str((tmp_path / "mirror").resolve())
        assert str(settings.script_hooks_dir) == str(
            (tmp_path / "script-hooks").resolve()
        )
        assert str(settings.log_dir) == str((tmp_path / "logs").resolve())
        assert settings.git_auto_commit is False
        assert settings.git_auto_push is False
        assert settings.log_max_lines == 1000

    def test_missing_config_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = load_config()
        assert config is None

    def test_non_dict_top_level_returns_none(self, tmp_path, monkeypatch, caplog):
        """YAML 顶层不是 dict 时应返回 None"""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "confmirror.yaml"
        config_file.write_text("just_a_string\n")

        with caplog.at_level("ERROR", logger="confmirror.config"):
            config = load_config(str(config_file))
        assert config is None
        assert "必须是一个 YAML 映射" in caplog.text
