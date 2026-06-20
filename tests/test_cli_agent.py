"""CLI Agent 化测试 — 验证 --format json, --dry-run, --yes 等行为。"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from confmirror import global_config
from confmirror.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def project(tmp_path, monkeypatch):
    """创建临时项目目录（配置文件 + 源文件），并切换到该目录"""
    monkeypatch.chdir(tmp_path)

    etc_ssh = tmp_path / "etc" / "ssh"
    etc_ssh.mkdir(parents=True)
    (etc_ssh / "sshd_config").write_text("PermitRootLogin no\n")

    etc_nginx = tmp_path / "etc" / "nginx"
    etc_nginx.mkdir(parents=True)
    (etc_nginx / "nginx.conf").write_text("server {}\n")

    config = tmp_path / "confmirror.yaml"
    config.write_text(f"""
settings:
  name: test
  backup_root: ./mirror
  script_hooks_dir: ./script-hooks
  log_dir: ./logs
modules:
  - name: ssh
    base_path: {etc_ssh.parent}
    paths:
      - ssh/sshd_config
  - name: nginx
    base_path: {etc_nginx.parent}
    paths:
      - nginx/nginx.conf
""")
    return tmp_path


class TestFormatJson:
    """--format json 输出结构化数据"""

    def test_backup_json(self, runner, project):
        result = runner.invoke(
            main,
            [
                "-c",
                str(project / "confmirror.yaml"),
                "backup",
                "-m",
                "ssh",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "success"
        assert data["command"] == "backup"
        assert data["module"] == "ssh"

    def test_diff_json_no_backup(self, runner, project):
        result = runner.invoke(
            main,
            [
                "-c",
                str(project / "confmirror.yaml"),
                "diff",
                "-m",
                "ssh",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "success"
        assert data["command"] == "diff"
        assert "added" in data
        assert "deleted" in data

    def test_diff_json_with_backup(self, runner, project):
        runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", "-m", "ssh"]
        )
        result = runner.invoke(
            main,
            [
                "-c",
                str(project / "confmirror.yaml"),
                "diff",
                "-m",
                "ssh",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "success"
        assert "changed" in data

    def test_ls_json(self, runner, project):
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "ls", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "success"
        assert data["command"] == "ls"

    def test_perms_json(self, runner, project):
        runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", "-m", "ssh"]
        )
        result = runner.invoke(
            main,
            [
                "-c",
                str(project / "confmirror.yaml"),
                "perms",
                "-m",
                "ssh",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "success"
        assert data["command"] == "perms"

    def test_sync_json_in_git_repo(self, runner, project):
        mirror = project / "mirror"
        mirror.mkdir(exist_ok=True)
        subprocess.run(["git", "init"], cwd=mirror, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=mirror,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=mirror,
            check=True,
            capture_output=True,
        )
        runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", "-m", "ssh"]
        )
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "sync", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "success"
        assert data["command"] == "sync"

    def test_json_no_console_emoji(self, runner, project):
        """JSON 模式下不应有 emoji 或 ANSI 颜色污染 stdout"""
        result = runner.invoke(
            main,
            [
                "-c",
                str(project / "confmirror.yaml"),
                "backup",
                "-m",
                "ssh",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        # stdout 应该是纯 JSON，不包含 emoji
        assert "❌" not in result.output
        assert "✅" not in result.output
        assert "\033[" not in result.output


class TestDryRun:
    """--dry-run 预览模式不实际执行"""

    def test_backup_dry_run_no_files_created(self, runner, project):
        result = runner.invoke(
            main,
            [
                "-c",
                str(project / "confmirror.yaml"),
                "backup",
                "-m",
                "ssh",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        mirror = project / "mirror"
        # 预览模式下不应创建备份文件
        assert not any(mirror.rglob("sshd_config"))

    def test_backup_dry_run_json(self, runner, project):
        result = runner.invoke(
            main,
            [
                "-c",
                str(project / "confmirror.yaml"),
                "backup",
                "-m",
                "ssh",
                "--dry-run",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True

    def test_restore_dry_run_no_changes(self, runner, project):
        runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", "-m", "ssh"]
        )
        original = project / "etc" / "ssh" / "sshd_config"
        original.write_text("CHANGED\n")
        result = runner.invoke(
            main,
            [
                "-c",
                str(project / "confmirror.yaml"),
                "restore",
                "-m",
                "ssh",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        # 预览模式下不应还原文件
        assert original.read_text() == "CHANGED\n"

    def test_sync_dry_run_no_git_commit(self, runner, project):
        mirror = project / "mirror"
        mirror.mkdir(exist_ok=True)
        subprocess.run(["git", "init"], cwd=mirror, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=mirror,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=mirror,
            check=True,
            capture_output=True,
        )
        runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", "-m", "ssh"]
        )
        result = runner.invoke(
            main,
            [
                "-c",
                str(project / "confmirror.yaml"),
                "sync",
                "--dry-run",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["dry_run"] is True


class TestNonInteractive:
    """--yes 跳过交互式确认"""

    def test_backup_full_yes(self, runner, project):
        """全量备份时 --yes 跳过 y/n 提示"""
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", "--yes"]
        )
        assert result.exit_code == 0
        mirror = project / "mirror"
        assert any(mirror.rglob("sshd_config"))

    def test_restore_full_yes(self, runner, project):
        """全量还原时 --yes 跳过 YES 提示"""
        runner.invoke(main, ["-c", str(project / "confmirror.yaml"), "backup", "--yes"])
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "restore", "--yes"]
        )
        assert result.exit_code == 0


class TestExitCode:
    """标准化退出码"""

    def test_config_error_exit_code(self, runner, tmp_path):
        """配置不存在时应返回非 0 退出码（click.Path(exists=True) 验证失败 → 2）"""
        fake_config = tmp_path / "nonexistent.yaml"
        result = runner.invoke(main, ["-c", str(fake_config), "backup"])
        assert result.exit_code == 2  # click.BadParameter / UsageError

    def test_success_exit_code(self, runner, project):
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", "-m", "ssh"]
        )
        assert result.exit_code == 0
