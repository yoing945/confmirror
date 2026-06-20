"""测试 system_install 模块。"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from confmirror.system_install import (
    WRAPPER_MARKER,
    _detect_source_path,
    install_system_entry,
    uninstall_system_entry,
)


class TestDetectSourcePath:
    def test_from_absolute_argv0(self, tmp_path, monkeypatch):
        """sys.argv[0] 为绝对路径时直接使用"""
        fake_bin = tmp_path / "confmirror"
        fake_bin.write_text("#!/bin/sh\n")
        monkeypatch.setattr(sys, "argv", [str(fake_bin), "install-system"])
        assert _detect_source_path() == fake_bin.resolve()

    def test_fallback_to_shutil_which(self, tmp_path, monkeypatch):
        """sys.argv[0] 不是绝对路径时回退到 shutil.which"""
        fake_bin = tmp_path / "confmirror"
        fake_bin.write_text("#!/bin/sh\n")
        monkeypatch.setattr(sys, "argv", ["confmirror", "install-system"])
        with patch("shutil.which", return_value=str(fake_bin)):
            assert _detect_source_path() == fake_bin.resolve()

    def test_raise_when_not_found(self, monkeypatch):
        """找不到时抛出 RuntimeError"""
        monkeypatch.setattr(sys, "argv", ["confmirror", "install-system"])
        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="无法自动检测"):
                _detect_source_path()


class TestInstallSystemEntry:
    def test_success(self, tmp_path, monkeypatch):
        """正常创建 wrapper 脚本"""
        system_bin = tmp_path / "bin"
        system_bin.mkdir()
        fake_source = tmp_path / "confmirror"
        fake_source.write_text("fake")

        monkeypatch.setattr("confmirror.system_install.SYSTEM_BIN_DIR", system_bin)
        monkeypatch.setattr(os, "getuid", lambda: 0)

        result = install_system_entry(fake_source)
        assert result is True

        wrapper = system_bin / "confmirror"
        assert wrapper.exists()
        content = wrapper.read_text()
        assert WRAPPER_MARKER in content
        assert str(fake_source.resolve()) in content
        assert os.access(wrapper, os.X_OK)

    def test_permission_error(self, monkeypatch):
        """非 root 运行时抛出 PermissionError"""
        monkeypatch.setattr(os, "getuid", lambda: 1000)
        with pytest.raises(PermissionError, match="需要 root 权限"):
            install_system_entry(Path("/fake/confmirror"))

    def test_source_not_found(self, tmp_path, monkeypatch):
        """源路径不存在时抛出 FileNotFoundError"""
        monkeypatch.setattr(os, "getuid", lambda: 0)
        with pytest.raises(FileNotFoundError, match="源路径不存在"):
            install_system_entry(tmp_path / "nonexistent")

    def test_refuse_overwrite_non_wrapper(self, tmp_path, monkeypatch):
        """已存在非 wrapper 文件时拒绝覆盖"""
        system_bin = tmp_path / "bin"
        system_bin.mkdir()
        existing = system_bin / "confmirror"
        existing.write_text("#!/bin/sh\necho other\n")

        fake_source = tmp_path / "confmirror"
        fake_source.write_text("fake")

        monkeypatch.setattr("confmirror.system_install.SYSTEM_BIN_DIR", system_bin)
        monkeypatch.setattr(os, "getuid", lambda: 0)

        with pytest.raises(RuntimeError, match="不是 ConfMirror 创建的"):
            install_system_entry(fake_source)

    def test_overwrite_own_wrapper(self, tmp_path, monkeypatch):
        """覆盖自己之前创建的 wrapper 应成功"""
        system_bin = tmp_path / "bin"
        system_bin.mkdir()
        fake_source = tmp_path / "confmirror"
        fake_source.write_text("fake")

        monkeypatch.setattr("confmirror.system_install.SYSTEM_BIN_DIR", system_bin)
        monkeypatch.setattr(os, "getuid", lambda: 0)

        # 第一次安装
        install_system_entry(fake_source)
        # 第二次安装（覆盖）
        install_system_entry(fake_source)
        assert (system_bin / "confmirror").exists()


class TestUninstallSystemEntry:
    def test_success(self, tmp_path, monkeypatch):
        """正常删除 wrapper"""
        system_bin = tmp_path / "bin"
        system_bin.mkdir()
        wrapper = system_bin / "confmirror"
        wrapper.write_text(f"#!/bin/sh\n{WRAPPER_MARKER}\nexec /fake\n")

        monkeypatch.setattr("confmirror.system_install.SYSTEM_BIN_DIR", system_bin)
        monkeypatch.setattr(os, "getuid", lambda: 0)

        result = uninstall_system_entry()
        assert result is True
        assert not wrapper.exists()

    def test_not_found(self, tmp_path, monkeypatch):
        """wrapper 不存在时返回 False"""
        system_bin = tmp_path / "bin"
        system_bin.mkdir()

        monkeypatch.setattr("confmirror.system_install.SYSTEM_BIN_DIR", system_bin)
        monkeypatch.setattr(os, "getuid", lambda: 0)

        result = uninstall_system_entry()
        assert result is False

    def test_permission_error(self, monkeypatch):
        """非 root 运行时抛出 PermissionError"""
        monkeypatch.setattr(os, "getuid", lambda: 1000)
        with pytest.raises(PermissionError, match="需要 root 权限"):
            uninstall_system_entry()

    def test_refuse_delete_non_wrapper(self, tmp_path, monkeypatch):
        """非 wrapper 文件时拒绝删除"""
        system_bin = tmp_path / "bin"
        system_bin.mkdir()
        other = system_bin / "confmirror"
        other.write_text("#!/bin/sh\necho other\n")

        monkeypatch.setattr("confmirror.system_install.SYSTEM_BIN_DIR", system_bin)
        monkeypatch.setattr(os, "getuid", lambda: 0)

        with pytest.raises(RuntimeError, match="不是 ConfMirror 创建的"):
            uninstall_system_entry()
