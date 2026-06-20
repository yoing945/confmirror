"""Tests for logger, gitops, and global_config modules."""

import logging
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from confmirror.gitops import git_auto_commit_and_push
from confmirror.global_config import (
    get_global_config_value,
    load_global_config,
    remove_global_config_value,
    save_global_config,
    set_global_config_value,
)
from confmirror.logger import (
    ColoredFormatter,
    ModuleLog,
    resolve_log_path,
    rotate_log_file,
    setup_logger,
)


@pytest.fixture(autouse=True)
def reset_logger():
    """每个测试前清理 confmirror logger，避免 handler 缓存跨测试污染"""
    logger = logging.getLogger("confmirror")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)
    yield


@pytest.fixture
def isolated_global_config(monkeypatch, tmp_path):
    """隔离全局配置，避免污染用户真实配置"""
    from confmirror import global_config

    config_dir = tmp_path / ".config" / "confmirror"
    monkeypatch.setattr(global_config, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(global_config, "CONFIG_FILE", config_dir / "config.yaml")
    return tmp_path


class TestModuleLog:
    def test_ok_no_status(self, caplog):
        logger = logging.getLogger("test_ok")
        _log = ModuleLog("backup", logger)
        with caplog.at_level("INFO", logger="test_ok"):
            _log.ok("file saved")
        assert "[backup] file saved" in caplog.text

    def test_skip_with_status(self, caplog):
        logger = logging.getLogger("test_skip")
        _log = ModuleLog("backup", logger)
        with caplog.at_level("INFO", logger="test_skip"):
            _log.skip("unchanged")
        assert "[backup:skip] unchanged" in caplog.text

    def test_warn(self, caplog):
        logger = logging.getLogger("test_warn")
        _log = ModuleLog("backup", logger)
        with caplog.at_level("WARNING", logger="test_warn"):
            _log.warn("permission denied")
        assert "[backup] permission denied" in caplog.text

    def test_error(self, caplog):
        logger = logging.getLogger("test_error")
        _log = ModuleLog("backup", logger)
        with caplog.at_level("ERROR", logger="test_error"):
            _log.error("disk full")
        assert "[backup] disk full" in caplog.text

    def test_category_override(self, caplog):
        logger = logging.getLogger("test_override")
        _log = ModuleLog("backup", logger)
        with caplog.at_level("INFO", logger="test_override"):
            _log.info("msg", category="restore")
        assert "[restore] msg" in caplog.text


class TestSetupLogger:
    def test_creates_handlers(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger = setup_logger(log_file, max_lines=100)
        assert len(logger.handlers) == 2  # FileHandler + StreamHandler

    def test_handler_caching(self, tmp_path):
        log_file = tmp_path / "test.log"
        l1 = setup_logger(log_file, max_lines=100)
        handler_count = len(l1.handlers)

        l2 = setup_logger(log_file, max_lines=100)
        assert l2 is l1
        assert len(l2.handlers) == handler_count

    def test_logs_to_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        logger = setup_logger(log_file, max_lines=100)
        logger.info("hello file")

        content = log_file.read_text()
        assert "hello file" in content


class TestRotateLogFile:
    def test_rotate_keeps_recent(self, tmp_path):
        log_file = tmp_path / "test.log"
        log_file.write_text("\n".join(f"line {i}" for i in range(1, 11)) + "\n")

        rotate_log_file(log_file, max_lines=5)

        lines = log_file.read_text().strip().split("\n")
        assert len(lines) == 5
        assert lines[0] == "line 6"
        assert lines[-1] == "line 10"

    def test_rotate_empty_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        log_file.write_text("")
        rotate_log_file(log_file, max_lines=5)
        assert log_file.read_text() == ""

    def test_rotate_missing_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        rotate_log_file(log_file, max_lines=5)
        assert not log_file.exists()


class TestResolveLogPath:
    def test_dir_input(self, tmp_path):
        result = resolve_log_path(str(tmp_path / "logs"), "myapp")
        assert result == (tmp_path / "logs" / "myapp.log").resolve()

    def test_file_input(self, tmp_path):
        result = resolve_log_path(str(tmp_path / "myapp.log"))
        assert result == (tmp_path / "myapp.log").resolve()

    def test_path_input(self, tmp_path):
        """接受 Path 对象（修复 cli.py 的类型错误）"""
        result = resolve_log_path(tmp_path / "logs", "myapp")
        assert result == (tmp_path / "logs" / "myapp.log").resolve()


class TestColoredFormatter:
    def test_adds_ansi_color_to_levelname(self):
        formatter = ColoredFormatter("[%(levelname)s] %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        assert "\033[32m" in formatted  # INFO = green
        assert "\033[0m" in formatted  # reset

    def test_gray_for_skip_messages(self):
        formatter = ColoredFormatter("[%(levelname)s] %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="[backup:skip] unchanged",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        assert "\033[90m" in formatted  # SKIPPED_COLOR = gray
        assert "\033[0m" in formatted


class TestGitAutoCommitAndPush:
    def test_not_git_repo(self, tmp_path):
        success, error_msg = git_auto_commit_and_push(tmp_path, "test")
        assert success is False
        assert "不是Git仓库" in error_msg

    def test_no_changes(self, tmp_path):
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        success, error_msg = git_auto_commit_and_push(tmp_path, "test")
        assert success is True
        assert error_msg == ""

    def test_commit_success(self, tmp_path):
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        (tmp_path / "file.txt").write_text("hello\n")

        success, error_msg = git_auto_commit_and_push(tmp_path, "test commit")
        assert success is True
        assert error_msg == ""

    def test_push_no_remote(self, tmp_path):
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        (tmp_path / "file.txt").write_text("hello\n")

        success, error_msg = git_auto_commit_and_push(tmp_path, "test", auto_push=True)
        assert success is True  # 无远程仓库，warn 并返回 True
        assert error_msg == ""


class TestGitAutoCommitFailure:
    def test_commit_failure_returns_error(self, tmp_path):
        """git commit 失败时返回 (False, error_msg) 而非抛异常"""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "file.txt").write_text("hello\n")

        original_run = subprocess.run

        def patched_run(cmd, **kwargs):
            if cmd[0] == "git" and cmd[1] == "commit":
                raise subprocess.CalledProcessError(1, cmd, stderr="commit failed")
            return original_run(cmd, **kwargs)

        with patch("confmirror.gitops.subprocess.run", side_effect=patched_run):
            success, error_msg = git_auto_commit_and_push(tmp_path, "test commit")
            assert success is False
            assert "commit failed" in error_msg


class TestGlobalConfig:
    def test_load_missing(self, isolated_global_config):
        assert load_global_config() == {}

    def test_save_and_load(self, isolated_global_config):
        save_global_config({"key": "value"})
        assert load_global_config() == {"key": "value"}

    def test_get_set_remove(self, isolated_global_config):
        set_global_config_value("path", "/tmp/test")
        assert get_global_config_value("path") == "/tmp/test"

        remove_global_config_value("path")
        assert get_global_config_value("path") is None

    def test_remove_missing_key(self, isolated_global_config):
        assert remove_global_config_value("nonexistent") is True
