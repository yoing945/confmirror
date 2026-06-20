# src/confmirror/gitops.py

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .logger import ModuleLog

logger = logging.getLogger(__name__)
_log = ModuleLog("git", logger)


def git_auto_commit_and_push(
    repo_path: Path,
    message: str,
    auto_push: bool = False,
    remote_name: str = "origin",
    branch: Optional[str] = None,
) -> tuple[bool, str]:
    """
    自动提交并可选推送到远程仓库

    Args:
        repo_path: 仓库路径
        message: 提交信息
        auto_push: 是否自动推送
        remote_name: 远程仓库名称，默认为origin
        branch: 指定分支，默认使用当前分支

    Returns:
        tuple[bool, str]: (是否成功, 错误信息)
    """
    try:
        # 检查是否为git仓库
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            _log.warn("当前目录不是Git仓库，跳过Git操作")
            return False, "当前目录不是Git仓库"
        _log.info(f"仓库路径: {repo_path}")

        # 检查 git 用户名/邮箱是否已配置
        for config_key in ["user.name", "user.email"]:
            config_result = subprocess.run(
                ["git", "config", config_key],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if config_result.returncode != 0 or not config_result.stdout.strip():
                error_msg = f"Git {config_key} 未配置，请先执行: git config --global {config_key} 'Your Name/Email'"
                _log.error(error_msg)
                return False, error_msg

        # 添加所有变更
        subprocess.run(
            ["git", "add", "."], cwd=repo_path, check=True, capture_output=True
        )

        # 检查是否有变更需要提交
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if not result.stdout.strip():
            _log.info("没有变更需要提交")
            return True, ""

        # 提交变更
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        _log.ok(f"已提交: {message}")

        # 推送到远程（如果启用）
        if auto_push:
            # 获取当前分支
            if branch is None:
                branch_result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                )
                branch = branch_result.stdout.strip()

            # 检查远程仓库是否存在
            remote_result = subprocess.run(
                ["git", "remote", "get-url", remote_name],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            if remote_result.returncode != 0:
                _log.warn(f"远程仓库 '{remote_name}' 未配置，跳过推送")
                return True, ""

            # 执行推送
            push_result = subprocess.run(
                ["git", "push", remote_name, branch],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )

            if push_result.returncode == 0:
                _log.ok(f"已推送到 {remote_name}/{branch}")
            else:
                _log.warn(f"推送失败: {push_result.stderr}")
                return False, f"推送失败: {push_result.stderr}"

        return True, ""

    except subprocess.CalledProcessError as e:
        error_msg = f"Git 操作失败: {e.stderr if hasattr(e, 'stderr') else str(e)}"
        _log.error(error_msg)
        return False, error_msg
