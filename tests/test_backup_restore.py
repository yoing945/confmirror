"""Tests for backup and restore core logic."""

import time
from pathlib import Path
from unittest.mock import patch

import pathspec
import pytest

from confmirror.backup import (
    _backup_directory,
    _backup_file,
    backup_module,
    backup_single_path,
)
from confmirror.config import Config, ModuleConfig, Settings
from confmirror.meta import read_meta, write_meta
from confmirror.restore import restore_file_or_dir, restore_module


@pytest.fixture
def settings(tmp_path):
    """提供通用的 Settings 配置"""
    return Settings(
        name="test",
        backup_root=tmp_path / "mirror",
        mirror_file_mode="0o644",
        mirror_dir_mode="0o755",
    )


class TestBackupFile:
    def test_backup_new_file(self, tmp_path, settings):
        src = tmp_path / "src" / "sshd_config"
        src.parent.mkdir(parents=True)
        src.write_text("PermitRootLogin no\n")

        dest = tmp_path / "mirror" / "sshd_config"
        _backup_file(src, dest, settings)

        assert dest.exists()
        assert dest.read_text() == "PermitRootLogin no\n"
        # 验证 meta 文件
        meta = read_meta(dest)
        assert meta is not None
        assert meta["type"] == "file"

    def test_backup_skip_unchanged(self, tmp_path, settings, caplog):
        src = tmp_path / "src" / "sshd_config"
        src.parent.mkdir(parents=True)
        src.write_text("hello\n")
        src.chmod(0o600)

        dest = tmp_path / "mirror" / "sshd_config"
        _backup_file(src, dest, settings)
        assert dest.exists()

        # 记录修改时间
        mtime_before = dest.stat().st_mtime
        time.sleep(0.01)

        # 差异备份应跳过
        with caplog.at_level("INFO", logger="confmirror.backup"):
            _backup_file(src, dest, settings, force=False)

        mtime_after = dest.stat().st_mtime
        assert mtime_after == mtime_before
        assert "文件信息无变化" in caplog.text

    def test_backup_force_overwrite(self, tmp_path, settings):
        src = tmp_path / "src" / "sshd_config"
        src.parent.mkdir(parents=True)
        src.write_text("original\n")

        dest = tmp_path / "mirror" / "sshd_config"
        _backup_file(src, dest, settings)

        # 修改源文件
        src.write_text("modified\n")

        # 差异模式不应跳过（内容已变更）
        _backup_file(src, dest, settings, force=False)
        assert dest.read_text() == "modified\n"


class TestBackupDirectory:
    def test_backup_directory(self, tmp_path, settings):
        src_dir = tmp_path / "src" / "ssh"
        src_dir.mkdir(parents=True)
        (src_dir / "sshd_config").write_text("PermitRootLogin no\n")
        subdir = src_dir / "ssh_config.d"
        subdir.mkdir()
        (subdir / "custom.conf").write_text("Host *\n")

        dest_dir = tmp_path / "mirror" / "ssh"
        _backup_directory(src_dir, dest_dir, settings)

        assert dest_dir.exists()
        assert dest_dir.is_dir()
        # 验证 meta 文件
        meta = read_meta(dest_dir)
        assert meta is not None
        assert meta["type"] == "dir"
        # 验证递归备份了子文件和子目录
        assert (dest_dir / "sshd_config").exists()
        assert (dest_dir / "sshd_config").read_text() == "PermitRootLogin no\n"
        assert (dest_dir / "ssh_config.d" / "custom.conf").exists()
        assert (dest_dir / "ssh_config.d" / "custom.conf").read_text() == "Host *\n"

    def test_backup_dir_recursive_with_excludes(self, tmp_path, settings, caplog):
        """目录递归备份应应用排除规则"""
        src_dir = tmp_path / "src" / "nginx"
        src_dir.mkdir(parents=True)
        (src_dir / "nginx.conf").write_text("conf\n")
        (src_dir / "nginx.conf.bak").write_text("bak\n")
        subdir = src_dir / "sites-available"
        subdir.mkdir()
        (subdir / "default").write_text("default\n")

        dest_dir = tmp_path / "mirror" / "nginx"
        spec = pathspec.GitIgnoreSpec.from_lines(["*.bak"])
        with caplog.at_level("INFO", logger="confmirror.backup"):
            _backup_directory(src_dir, dest_dir, settings, spec=spec)

        assert (dest_dir / "nginx.conf").exists()
        assert not (dest_dir / "nginx.conf.bak").exists()
        assert (dest_dir / "sites-available" / "default").exists()
        assert "被排除" in caplog.text


class TestBackupSinglePath:
    def test_backup_file(self, tmp_path, settings):
        src = tmp_path / "src" / "sshd_config"
        src.parent.mkdir(parents=True)
        src.write_text("hello\n")

        backup_single_path(src, settings.backup_root, settings)

        # 备份目录下应该能找到文件
        assert any(settings.backup_root.rglob("sshd_config"))

    def test_backup_directory(self, tmp_path, settings):
        src = tmp_path / "src" / "ssh"
        src.mkdir(parents=True)
        (src / "sshd_config").write_text("hello\n")
        subdir = src / "ssh_config.d"
        subdir.mkdir()
        (subdir / "custom.conf").write_text("custom\n")

        backup_single_path(src, settings.backup_root, settings)

        assert any(settings.backup_root.rglob("ssh"))
        # 备份路径基于 src 的绝对路径，在 mirror_root 下重建完整路径
        dest = settings.backup_root / str(src).lstrip("/")
        assert (dest / "sshd_config").exists()
        assert (dest / "sshd_config").read_text() == "hello\n"
        assert (dest / "ssh_config.d" / "custom.conf").exists()
        assert (dest / "ssh_config.d" / "custom.conf").read_text() == "custom\n"

    def test_backup_missing_path(self, tmp_path, settings, caplog):
        src = tmp_path / "src" / "missing"
        with caplog.at_level("INFO", logger="confmirror.backup"):
            backup_single_path(src, settings.backup_root, settings)
        assert "路径不存在" in caplog.text

    def test_backup_recursive_protection(self, tmp_path, settings, caplog):
        """不能备份备份目录自身或其子目录"""
        # 在备份根目录下创建一个文件
        src = settings.backup_root / "internal" / "file.txt"
        src.parent.mkdir(parents=True)
        src.write_text("hello\n")

        with caplog.at_level("INFO", logger="confmirror.backup"):
            backup_single_path(src, settings.backup_root, settings)

        assert "不能备份备份目录自身" in caplog.text


class TestRestoreFileOrDir:
    def test_restore_file(self, tmp_path, monkeypatch):
        """还原文件应恢复内容"""
        monkeypatch.setattr("os.chown", lambda p, u, g: None)

        backup_root = tmp_path / "mirror"
        original = tmp_path / "sshd_config"
        # backup 路径必须与 restore_file_or_dir 的构造逻辑一致
        backup = backup_root / str(original).lstrip("/")
        backup.parent.mkdir(parents=True)
        backup.write_text("backup content\n")
        write_meta(backup, "644", 1000, 1000, "file")

        original.write_text("original content\n")

        restore_file_or_dir(original, backup_root)

        assert original.read_text() == "backup content\n"

    def test_restore_skip_unchanged(self, tmp_path, monkeypatch, caplog):
        """差异还原：文件未变更时应跳过"""
        monkeypatch.setattr("os.chown", lambda p, u, g: None)

        backup_root = tmp_path / "mirror"
        original = tmp_path / "sshd_config"
        original.write_text("same content\n")
        stat = original.stat()

        backup = backup_root / str(original).lstrip("/")
        backup.parent.mkdir(parents=True)
        backup.write_text("same content\n")
        write_meta(backup, oct(stat.st_mode)[-3:], stat.st_uid, stat.st_gid, "file")

        with caplog.at_level("INFO", logger="confmirror.restore"):
            restore_file_or_dir(original, backup_root)

        assert "文件信息无变化" in caplog.text

    def test_restore_directory(self, tmp_path, monkeypatch):
        """还原目录应恢复目录及其内容"""
        monkeypatch.setattr("os.chown", lambda p, u, g: None)

        backup_root = tmp_path / "mirror"
        original = tmp_path / "ssh"
        backup = backup_root / str(original).lstrip("/")
        backup.mkdir(parents=True)
        (backup / "sshd_config").write_text("config\n")
        write_meta(backup, "755", 1000, 1000, "dir")

        original.mkdir(exist_ok=True)
        (original / "sshd_config").write_text("old\n")

        restore_file_or_dir(original, backup_root)

        assert (original / "sshd_config").read_text() == "config\n"

    def test_restore_directory_with_subdir_meta(self, tmp_path, monkeypatch):
        """还原目录应恢复子目录的权限和属主（.dir.meta）"""
        chown_calls = []

        def mock_chown(p, u, g):
            chown_calls.append((str(p), u, g))

        monkeypatch.setattr("os.chown", mock_chown)

        backup_root = tmp_path / "mirror"
        original = tmp_path / "nginx"
        backup = backup_root / str(original).lstrip("/")
        backup.mkdir(parents=True)

        # 创建子目录及其 .dir.meta
        subdir = backup / "sites-available"
        subdir.mkdir()
        (subdir / "default").write_text("server {}")
        write_meta(subdir, "750", 0, 0, "dir")

        # 顶层目录 meta
        write_meta(backup, "755", 1000, 1000, "dir")

        original.mkdir(exist_ok=True)
        (original / "sites-available").mkdir()
        (original / "sites-available" / "default").write_text("old")

        restore_file_or_dir(original, backup_root)

        # 验证子目录权限被还原
        assert (original / "sites-available").exists()
        # os.chmod 被调用，检查调用记录中是否包含子目录
        subdir_chown = [c for c in chown_calls if c[0].endswith("sites-available")]
        assert (
            subdir_chown
        ), f"子目录 sites-available 的权限/属主未被还原，chown 调用: {chown_calls}"

    def test_restore_missing_backup(self, tmp_path, caplog):
        """备份内容不存在时应跳过"""
        backup_root = tmp_path / "mirror"
        original = tmp_path / "sshd_config"
        # 创建空的 meta 但无备份文件
        backup = backup_root / str(original).lstrip("/")
        backup.parent.mkdir(parents=True)
        write_meta(backup, "644", 1000, 1000, "file")

        with caplog.at_level("INFO", logger="confmirror.restore"):
            restore_file_or_dir(original, backup_root)

        assert "备份内容不存在" in caplog.text

    def test_restore_missing_meta(self, tmp_path, caplog):
        """.meta 文件不存在时应跳过"""
        backup_root = tmp_path / "mirror"
        backup = backup_root / "sshd_config"
        backup.parent.mkdir(parents=True)
        backup.write_text("content\n")
        # 不写 meta

        original = tmp_path / "sshd_config"

        with caplog.at_level("INFO", logger="confmirror.restore"):
            restore_file_or_dir(original, backup_root)

        assert "缺少 .meta" in caplog.text


class TestBackupModuleWithScript:
    def test_backup_script_module(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        script_hooks_dir = tmp_path / "script-hooks"
        script_hooks_dir.mkdir()
        (script_hooks_dir / "test.sh").write_text("#!/bin/bash\necho backup\n")

        settings = Settings(
            name="test",
            backup_root=tmp_path / "mirror",
            script_hooks_dir=script_hooks_dir,
        )
        module = ModuleConfig(name="test", hook="test.sh", hook_lang="bash")

        with patch("confmirror.backup.run_script") as mock_run:
            backup_module(module, settings.backup_root, settings)
            mock_run.assert_called_once_with("test.sh", settings, "backup", "bash")


class TestBackupModuleWithExcludes:
    def test_exclude_patterns_filter_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "etc" / "nginx"
        src.mkdir(parents=True)
        (src / "nginx.conf").write_text("conf")
        (src / "nginx.conf.bak").write_text("bak")

        settings = Settings(
            name="test",
            backup_root=tmp_path / "mirror",
        )
        module = ModuleConfig(
            name="nginx",
            base_path=str(src),
            paths=["*"],
            exclude_paths=["*.bak"],
        )

        backup_module(module, settings.backup_root, settings)

        mirror = settings.backup_root
        assert any(mirror.rglob("nginx.conf"))
        assert not any(mirror.rglob("nginx.conf.bak"))


class TestRestoreModuleWithScript:
    def test_restore_script_module(self, tmp_path, monkeypatch):
        monkeypatch.setattr("os.chown", lambda p, u, g: None)
        monkeypatch.chdir(tmp_path)
        script_hooks_dir = tmp_path / "script-hooks"
        script_hooks_dir.mkdir()
        (script_hooks_dir / "test.sh").write_text("#!/bin/bash\necho restore\n")

        settings = Settings(
            name="test",
            backup_root=tmp_path / "mirror",
            script_hooks_dir=script_hooks_dir,
        )
        module = ModuleConfig(name="test", hook="test.sh", hook_lang="bash")

        with patch("confmirror.restore.run_script") as mock_run:
            config = Config(settings=settings, modules=[module])
            restore_module(module, config)
            mock_run.assert_called_once_with("test.sh", settings, "restore", "bash")
