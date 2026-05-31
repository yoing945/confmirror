"""Tests for meta module."""

from pathlib import Path

from confmirror.meta import meta_path_exists, read_meta, write_meta


class TestWriteAndReadMeta:
    def test_file_meta(self, tmp_path):
        target = tmp_path / "sshd_config"
        write_meta(target, "644", 0, 0, "file")

        meta_file = tmp_path / "sshd_config.meta"
        assert meta_file.exists()

        data = read_meta(target)
        assert data == {"mode": "644", "uid": "0", "gid": "0", "type": "file"}

    def test_dir_meta(self, tmp_path):
        target = tmp_path / "ssh"
        write_meta(target, "755", 1000, 1000, "dir")

        meta_file = tmp_path / "ssh.dir.meta"
        assert meta_file.exists()

        data = read_meta(target)
        assert data == {"mode": "755", "uid": "1000", "gid": "1000", "type": "dir"}

    def test_read_missing_meta(self, tmp_path):
        target = tmp_path / "missing"
        assert read_meta(target) is None


class TestMetaPathExists:
    def test_exists_for_file(self, tmp_path):
        target = tmp_path / "file.txt"
        write_meta(target, "644", 0, 0, "file")
        assert meta_path_exists(target) is True

    def test_exists_for_dir(self, tmp_path):
        target = tmp_path / "mydir"
        write_meta(target, "755", 0, 0, "dir")
        assert meta_path_exists(target) is True

    def test_not_exists(self, tmp_path):
        target = tmp_path / "ghost"
        assert meta_path_exists(target) is False
