"""CLI smoke tests — 验证所有命令至少不因参数/接口错误崩溃"""

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

    # 创建源文件
    etc_ssh = tmp_path / "etc" / "ssh"
    etc_ssh.mkdir(parents=True)
    (etc_ssh / "sshd_config").write_text("PermitRootLogin no\n")

    # 创建配置文件
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
""")

    return tmp_path


class TestCliHelpAndVersion:
    def test_main_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "backup" in result.output
        assert "restore" in result.output

    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0


class TestCliLs:
    def test_ls_all_modules(self, runner, project):
        result = runner.invoke(main, ["-c", str(project / "confmirror.yaml"), "ls"])
        assert result.exit_code == 0
        assert "ssh" in result.output

    def test_ls_single_module(self, runner, project):
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "ls", "-m", "ssh"]
        )
        assert result.exit_code == 0  # 不崩溃即通过

    def test_ls_detail(self, runner, project):
        result = runner.invoke(
            main,
            ["-c", str(project / "confmirror.yaml"), "ls", "-m", "ssh", "--detail"],
        )
        assert result.exit_code == 0


class TestCliDiff:
    def test_diff_module_no_backup(self, runner, project):
        """无备份时 diff 模块应报告缺失，但不崩溃"""
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "diff", "-m", "ssh"]
        )
        assert result.exit_code == 0

    def test_diff_path_no_backup(self, runner, project):
        ssh_config = project / "etc" / "ssh" / "sshd_config"
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "diff", str(ssh_config)]
        )
        assert result.exit_code == 0

    def test_diff_module_with_backup(self, runner, project):
        """备份后 diff 应能正确比较"""
        runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", "-m", "ssh"]
        )
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "diff", "-m", "ssh"]
        )
        assert result.exit_code == 0


class TestCliPerms:
    def test_perms_module_no_backup(self, runner, project):
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "perms", "-m", "ssh"]
        )
        assert result.exit_code == 0

    def test_perms_module_with_backup(self, runner, project):
        runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", "-m", "ssh"]
        )
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "perms", "-m", "ssh"]
        )
        assert result.exit_code == 0


class TestCliBackup:
    def test_backup_module(self, runner, project):
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", "-m", "ssh"]
        )
        assert result.exit_code == 0
        # 验证备份目录下有文件产生（不验证具体路径结构）
        mirror = project / "mirror"
        assert any(mirror.rglob("sshd_config"))

    def test_backup_path(self, runner, project):
        ssh_config = project / "etc" / "ssh" / "sshd_config"
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", str(ssh_config)]
        )
        assert result.exit_code == 0
        mirror = project / "mirror"
        assert any(mirror.rglob("sshd_config"))

    def test_backup_force(self, runner, project):
        runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", "-m", "ssh"]
        )
        result = runner.invoke(
            main,
            ["-c", str(project / "confmirror.yaml"), "backup", "-m", "ssh", "--force"],
        )
        assert result.exit_code == 0


class TestCliRestore:
    def test_restore_module(self, runner, project):
        runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", "-m", "ssh"]
        )
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "restore", "-m", "ssh"]
        )
        assert result.exit_code == 0

    def test_restore_path(self, runner, project):
        ssh_config = project / "etc" / "ssh" / "sshd_config"
        runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "backup", str(ssh_config)]
        )
        result = runner.invoke(
            main, ["-c", str(project / "confmirror.yaml"), "restore", str(ssh_config)]
        )
        assert result.exit_code == 0


class TestCliSync:
    def test_sync_does_not_crash_with_typeerror(self, runner, project):
        """
        Regression test: 之前 cli.py:423 传了 logger=logger 给 git_auto_commit_and_push，
        导致 TypeError。修复后即使不是 git 仓库，也应受控退出（exit_code=1），而非崩溃。
        """
        result = runner.invoke(main, ["-c", str(project / "confmirror.yaml"), "sync"])
        assert result.exit_code == 1  # 不是 git 仓库
        if result.exception:
            assert not isinstance(result.exception, TypeError)

    def test_sync_in_git_repo(self, runner, project):
        """在 git 仓库中 sync 应该成功"""
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

        result = runner.invoke(main, ["-c", str(project / "confmirror.yaml"), "sync"])
        assert result.exit_code == 0


class TestCliGlobalConfigPath:
    def test_set_show_remove(self, runner, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_path = tmp_path / "myconfig.yaml"
        config_path.write_text("modules:\n  - name: test\n")

        # 使用隔离的全局配置文件，避免污染用户真实配置
        isolated_config = tmp_path / "global_config.yaml"
        with patch.object(global_config, "CONFIG_FILE", isolated_config):
            # set
            result = runner.invoke(
                main, ["global-config-path", "set", str(config_path)]
            )
            assert result.exit_code == 0

            # show
            result = runner.invoke(main, ["global-config-path", "show"])
            assert result.exit_code == 0
            assert str(config_path) in result.output

            # remove
            result = runner.invoke(main, ["global-config-path", "remove"])
            assert result.exit_code == 0
