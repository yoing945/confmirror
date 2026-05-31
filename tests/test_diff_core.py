"""Tests for diff core algorithms."""

import pytest
from pathlib import Path
from unittest.mock import patch

from confmirror.diff import compare_content, compare_meta, same_file, _compare_files_by_hash, diff_module, diff_paths
from confmirror.meta import write_meta
from confmirror.config import Config, ModuleConfig, Settings


class TestCompareContent:
    def test_same_file(self, tmp_path):
        a = tmp_path / "a.txt"
        a.write_text("hello world")
        b = tmp_path / "b.txt"
        b.write_text("hello world")
        assert compare_content(a, b) is True

    def test_different_content(self, tmp_path):
        a = tmp_path / "a.txt"
        a.write_text("hello")
        b = tmp_path / "b.txt"
        b.write_text("world")
        assert compare_content(a, b) is False

    def test_dest_missing(self, tmp_path):
        a = tmp_path / "a.txt"
        a.write_text("hello")
        b = tmp_path / "b.txt"
        assert compare_content(a, b) is False

    def test_dir_vs_file(self, tmp_path):
        a = tmp_path / "a"
        a.mkdir()
        b = tmp_path / "b.txt"
        b.write_text("hello")
        assert compare_content(a, b) is False

    def test_same_dir(self, tmp_path):
        a = tmp_path / "a"
        a.mkdir()
        b = tmp_path / "b"
        b.mkdir()
        assert compare_content(a, b) is True


class TestCompareMeta:
    def test_same_meta(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("hello")
        stat = src.stat()

        dest = tmp_path / "mirror" / "src.txt"
        dest.parent.mkdir(parents=True)
        dest.write_text("hello")
        write_meta(dest, oct(stat.st_mode)[-3:], stat.st_uid, stat.st_gid, "file")

        assert compare_meta(src, dest) is True

    def test_different_mode(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("hello")
        src.chmod(0o600)

        dest = tmp_path / "mirror" / "src.txt"
        dest.parent.mkdir(parents=True)
        dest.write_text("hello")
        write_meta(dest, "644", 0, 0, "file")

        assert compare_meta(src, dest) is False

    def test_different_uid(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("hello")
        stat = src.stat()

        dest = tmp_path / "mirror" / "src.txt"
        dest.parent.mkdir(parents=True)
        dest.write_text("hello")
        write_meta(dest, oct(stat.st_mode)[-3:], 9999, stat.st_gid, "file")

        assert compare_meta(src, dest) is False

    def test_missing_meta(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("hello")

        dest = tmp_path / "mirror" / "src.txt"
        dest.parent.mkdir(parents=True)
        dest.write_text("hello")
        # 不写 meta

        assert compare_meta(src, dest) is False


class TestSameFile:
    def test_identical(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("hello")
        stat = src.stat()

        dest = tmp_path / "dest.txt"
        dest.write_text("hello")
        write_meta(dest, oct(stat.st_mode)[-3:], stat.st_uid, stat.st_gid, "file")

        assert same_file(src, dest) is True

    def test_different_content(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("hello")
        stat = src.stat()

        dest = tmp_path / "dest.txt"
        dest.write_text("world")
        write_meta(dest, oct(stat.st_mode)[-3:], stat.st_uid, stat.st_gid, "file")

        assert same_file(src, dest) is False

    def test_different_meta(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("hello")
        src.chmod(0o600)
        stat = src.stat()

        dest = tmp_path / "dest.txt"
        dest.write_text("hello")
        write_meta(dest, "644", stat.st_uid, stat.st_gid, "file")

        assert same_file(src, dest) is False

    def test_missing_dest(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("hello")
        dest = tmp_path / "dest.txt"
        assert same_file(src, dest) is False


class TestCompareFilesByHash:
    def test_same_hash(self, tmp_path):
        a = tmp_path / "a.txt"
        a.write_text("hello")
        b = tmp_path / "b.txt"
        b.write_text("hello")
        assert _compare_files_by_hash(a, b) is True

    def test_different_hash(self, tmp_path):
        a = tmp_path / "a.txt"
        a.write_text("hello")
        b = tmp_path / "b.txt"
        b.write_text("world")
        assert _compare_files_by_hash(a, b) is False


class TestDiffModule:
    """回归测试：diff_module 路径构造与排除模式"""

    def test_module_not_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = Config(
            settings=Settings(name="test", backup_root=tmp_path / "mirror"),
            modules=[]
        )
        with patch("confmirror.diff.compare_files_set") as mock_cmp:
            diff_module(config, "nonexistent")
            mock_cmp.assert_not_called()

    def test_script_module_skipped(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = Config(
            settings=Settings(name="test", backup_root=tmp_path / "mirror"),
            modules=[ModuleConfig(name="ufw", hook="ufw/script.sh")]
        )
        with patch("confmirror.diff.compare_files_set") as mock_cmp:
            diff_module(config, "ufw")
            mock_cmp.assert_not_called()

    def test_collects_source_and_backup_files(self, tmp_path, monkeypatch):
        """回归测试：diff_module 正确基于 backup_root 构造备份路径"""
        monkeypatch.chdir(tmp_path)
        backup_root = tmp_path / "mirror"
        (backup_root / "etc" / "ssh").mkdir(parents=True)
        (backup_root / "etc" / "ssh" / "sshd_config").write_text("hello")
        write_meta(backup_root / "etc" / "ssh" / "sshd_config", "644", 0, 0, "file")

        config = Config(
            settings=Settings(name="test", backup_root=backup_root),
            modules=[ModuleConfig(name="ssh", base_path="/etc", paths=["ssh/sshd_config"])]
        )

        src_pattern = str(Path("/etc") / "ssh/sshd_config")
        bak_pattern = str(backup_root / "etc" / "ssh" / "sshd_config")

        def fake_glob(pattern, recursive=False):
            if pattern == src_pattern:
                return ["/etc/ssh/sshd_config"]
            if pattern == bak_pattern:
                return [str(backup_root / "etc" / "ssh" / "sshd_config")]
            return []

        # patch Path.exists 让假路径通过存在性检查
        with patch("confmirror.diff.Path.exists", return_value=True):
            with patch("confmirror.diff.glob.glob", fake_glob):
                with patch("confmirror.diff.compare_files_set") as mock_cmp:
                    diff_module(config, "ssh")
                    assert mock_cmp.called
                    source_set, backup_set, br, _ = mock_cmp.call_args[0]
                    assert len(source_set) > 0
                    assert len(backup_set) > 0

    def test_respects_exclude_paths(self, tmp_path, monkeypatch):
        """验证排除模式在 diff_module 中生效"""
        monkeypatch.chdir(tmp_path)
        backup_root = tmp_path / "mirror"
        (backup_root / "etc" / "nginx").mkdir(parents=True)
        (backup_root / "etc" / "nginx" / "nginx.conf").write_text("conf")
        write_meta(backup_root / "etc" / "nginx" / "nginx.conf", "644", 0, 0, "file")
        (backup_root / "etc" / "nginx" / "nginx.conf.bak").write_text("bak")
        write_meta(backup_root / "etc" / "nginx" / "nginx.conf.bak", "644", 0, 0, "file")

        config = Config(
            settings=Settings(name="test", backup_root=backup_root),
            modules=[ModuleConfig(
                name="nginx",
                base_path="/etc/nginx",
                paths=["*"],
                exclude_paths=["*.bak"]
            )]
        )

        src_pattern = str(Path("/etc/nginx") / "*")
        bak_pattern = str(backup_root / "etc" / "nginx" / "*")

        def fake_glob(pattern, recursive=False):
            if pattern == src_pattern:
                return ["/etc/nginx/nginx.conf", "/etc/nginx/nginx.conf.bak"]
            if pattern == bak_pattern:
                return [
                    str(backup_root / "etc" / "nginx" / "nginx.conf"),
                    str(backup_root / "etc" / "nginx" / "nginx.conf.bak"),
                ]
            return []

        with patch("confmirror.diff.Path.exists", return_value=True):
            with patch("confmirror.diff.glob.glob", fake_glob):
                with patch("confmirror.diff.compare_files_set") as mock_cmp:
                    diff_module(config, "nginx")
                    source_set, backup_set, br, _ = mock_cmp.call_args[0]
                    assert Path("/etc/nginx/nginx.conf") in source_set
                    assert Path("/etc/nginx/nginx.conf.bak") not in source_set


class TestDiffPaths:
    """回归测试：diff_paths 路径构造"""

    def test_path_not_in_any_module(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config = Config(
            settings=Settings(name="test", backup_root=tmp_path / "mirror"),
            modules=[ModuleConfig(name="ssh", paths=["/etc/ssh/sshd_config"])]
        )
        with patch("confmirror.diff.compare_files_set") as mock_cmp:
            diff_paths(config, ["/etc/nginx/nginx.conf"])
            mock_cmp.assert_not_called()

    def test_collects_files_correctly(self, tmp_path, monkeypatch):
        """回归测试：diff_paths 正确构造备份路径"""
        monkeypatch.chdir(tmp_path)
        backup_root = tmp_path / "mirror"
        (backup_root / "etc" / "ssh").mkdir(parents=True)
        (backup_root / "etc" / "ssh" / "sshd_config").write_text("hello")
        write_meta(backup_root / "etc" / "ssh" / "sshd_config", "644", 0, 0, "file")

        config = Config(
            settings=Settings(name="test", backup_root=backup_root),
            modules=[ModuleConfig(name="ssh", paths=["/etc/ssh/sshd_config"])]
        )

        def fake_glob(pattern, recursive=False):
            if "sshd_config" in pattern:
                if "mirror" in pattern:
                    return [str(backup_root / "etc" / "ssh" / "sshd_config")]
                return ["/etc/ssh/sshd_config"]
            return []

        with patch("confmirror.diff.Path.exists", return_value=True):
            with patch("confmirror.diff.glob.glob", fake_glob):
                with patch("confmirror.diff.compare_files_set") as mock_cmp:
                    diff_paths(config, ["/etc/ssh/sshd_config"])
                    assert mock_cmp.called
                    source_set, backup_set, br, _ = mock_cmp.call_args[0]
                    assert len(source_set) > 0
                    assert len(backup_set) > 0
