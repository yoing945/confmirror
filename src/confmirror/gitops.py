# src/confmirror/gitops.py

import subprocess
from pathlib import Path


def git_auto_commit_and_push(repo_path: Path, message: str, auto_push: bool = False):
    try:
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path, capture_output=True, text=True
        )
        if not result.stdout.strip():
            return  # 无变更，不提交

        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_path, check=True, capture_output=True
        )
        if auto_push:
            subprocess.run(["git", "push"], cwd=repo_path, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git 操作失败: {e.stderr.decode()}")