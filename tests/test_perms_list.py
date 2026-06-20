"""Tests for perms and list modules."""

from pathlib import Path

import pytest

from confmirror.config import Config, ModuleConfig, Settings
from confmirror.list import execute_list
from confmirror.perms import (
    get_perms_for_module,
    get_perms_for_path,
    matched_paths_to_perms_info,
)


class TestGetPermsForModule:
    def test_script_module_returns_empty(self, tmp_path, caplog):
        settings = Settings(name="test", backup_root=tmp_path / "mirror")
        config = Config(
            settings=settings, modules=[ModuleConfig(name="ufw", hook="ufw/script.sh")]
        )
        with caplog.at_level("ERROR", logger="confmirror.perms"):
            result = get_perms_for_module("ufw", config)
        assert result == []
        assert "脚本钩子模块" in caplog.text

    def test_module_not_found_returns_empty(self, tmp_path, caplog):
        settings = Settings(name="test", backup_root=tmp_path / "mirror")
        config = Config(settings=settings, modules=[])
        with caplog.at_level("ERROR", logger="confmirror.perms"):
            result = get_perms_for_module("nonexistent", config)
        assert result == []
        assert "配置中不存在模块" in caplog.text

    def test_path_module_returns_perms(self, tmp_path):
        from unittest.mock import patch

        src = tmp_path / "etc" / "ssh"
        src.mkdir(parents=True)
        (src / "sshd_config").write_text("conf")
        from confmirror.meta import write_meta

        write_meta(src / "sshd_config", "644", 0, 0, "file")

        settings = Settings(name="test", backup_root=tmp_path / "mirror")
        config = Config(
            settings=settings,
            modules=[
                ModuleConfig(name="ssh", paths=["sshd_config"], base_path=str(src))
            ],
        )
        with patch(
            "confmirror.perms.glob.glob", return_value=[str(src / "sshd_config")]
        ):
            result = get_perms_for_module("ssh", config)
        assert len(result) == 1
        assert result[0]["meta"]["mode"] == "644"


class TestMatchedPathsToPermsInfo:
    def test_skips_meta_files(self, tmp_path):
        backup_root = tmp_path / "mirror"
        (backup_root / "etc" / "ssh").mkdir(parents=True)
        (backup_root / "etc" / "ssh" / "sshd_config").write_text("conf")
        from confmirror.meta import write_meta

        write_meta(backup_root / "etc" / "ssh" / "sshd_config", "644", 0, 0, "file")

        paths = [
            str(backup_root / "etc" / "ssh" / "sshd_config"),
            str(backup_root / "etc" / "ssh" / "sshd_config.meta"),
        ]
        result = matched_paths_to_perms_info(paths)
        assert len(result) == 1
        assert "sshd_config.meta" not in result[0]["path"]


class TestExecuteList:
    def test_empty_modules(self, caplog):
        config = Config(
            settings=Settings(name="test", backup_root=Path("/tmp")), modules=[]
        )
        with caplog.at_level("WARNING", logger="confmirror.list"):
            execute_list(config)
        assert "没有定义任何模块" in caplog.text

    def test_list_all_modules(self, caplog):
        config = Config(
            settings=Settings(name="test", backup_root=Path("/tmp")),
            modules=[
                ModuleConfig(name="ssh"),
                ModuleConfig(name="nginx"),
            ],
        )
        with caplog.at_level("INFO", logger="confmirror.list"):
            execute_list(config)
        assert "ssh" in caplog.text
        assert "nginx" in caplog.text

    def test_list_single_module(self, caplog):
        config = Config(
            settings=Settings(name="test", backup_root=Path("/tmp")),
            modules=[
                ModuleConfig(name="ssh", paths=["/etc/ssh/sshd_config"]),
            ],
        )
        with caplog.at_level("INFO", logger="confmirror.list"):
            execute_list(config, module_name="ssh", detail=True)
        assert "ssh" in caplog.text
        assert "/etc/ssh/sshd_config" in caplog.text

    def test_module_not_found(self, caplog):
        config = Config(
            settings=Settings(name="test", backup_root=Path("/tmp")),
            modules=[
                ModuleConfig(name="ssh"),
            ],
        )
        with caplog.at_level("ERROR", logger="confmirror.list"):
            execute_list(config, module_name="nonexistent")
        assert "未找到模块" in caplog.text
