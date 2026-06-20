"""初始化 ConfMirror 项目结构。"""

import logging
from pathlib import Path

from .config import CONFIG_FILENAME
from .logger import ModuleLog
from .output import ExitCode, emit_json

logger = logging.getLogger(__name__)
_log = ModuleLog("init", logger)

DEFAULT_DIRS = ("mirror", "script-hooks", "logs")

DEFAULT_CONFIG_TEMPLATE = """settings:
  name: "{name}"                      # 配置集名称，默认当前目录名
  backup_root: "./mirror"             # 镜像根目录
  script_hooks_dir: "./script-hooks"  # 脚本钩子目录
  log_dir: "./logs"                   # 日志目录
  log_max_lines: 1000                 # 日志最大保留行数
  git_auto_commit: false              # 是否自动提交到 Git
  git_auto_push: false                # 是否自动推送到远程

# 模块定义示例（取消注释后可用）：
# modules:
#   - name: "sshd"
#     paths:
#       - "/etc/ssh/sshd_config"
"""


def _get_existing_artifacts(path: Path) -> list[str]:
    """检查目标目录是否已存在 ConfMirror 产物。"""
    artifacts: list[str] = []
    config_file = path / CONFIG_FILENAME
    if config_file.exists():
        artifacts.append(str(config_file))
    for dirname in DEFAULT_DIRS:
        dirpath = path / dirname
        if dirpath.exists():
            artifacts.append(str(dirpath))
    return artifacts


def _create_project(path: Path) -> None:
    """在目标目录创建配置文件和推荐目录结构。"""
    path.mkdir(parents=True, exist_ok=True)
    config_path = path / CONFIG_FILENAME
    config_path.write_text(
        DEFAULT_CONFIG_TEMPLATE.format(name=path.name),
        encoding="utf-8",
    )
    for dirname in DEFAULT_DIRS:
        (path / dirname).mkdir(exist_ok=True)


def execute_init(
    path: Path,
    dry_run: bool = False,
    output_format: str = "human",
) -> int:
    """执行 init 命令的核心逻辑。

    Args:
        path: 目标目录
        dry_run: 是否为预览模式
        output_format: 输出格式，"human" 或 "json"

    Returns:
        退出码
    """
    existing = _get_existing_artifacts(path)
    if existing:
        if output_format == "json":
            emit_json(
                {
                    "status": "error",
                    "command": "init",
                    "error": "目标目录已存在 ConfMirror 产物，无法初始化",
                    "existing": existing,
                }
            )
        else:
            _log.error("目标目录已存在 ConfMirror 产物，无法初始化：")
            for item in existing:
                _log.error(f"  - {item}")
            _log.info("如需重新初始化，请先删除上述文件/目录。")
        return ExitCode.CONFIG_ERROR

    created = [str(path / CONFIG_FILENAME)] + [str(path / d) for d in DEFAULT_DIRS]

    if dry_run:
        if output_format == "json":
            emit_json(
                {
                    "status": "success",
                    "command": "init",
                    "dry_run": True,
                    "path": str(path),
                    "created": created,
                }
            )
        else:
            _log.info(f"[DRY-RUN] 将在 {path} 创建：")
            _log.info(f"  - {CONFIG_FILENAME}")
            for dirname in DEFAULT_DIRS:
                _log.info(f"  - {dirname}/")
        return ExitCode.SUCCESS

    try:
        _create_project(path)
    except PermissionError as e:
        if output_format == "json":
            emit_json({"status": "error", "command": "init", "error": f"权限不足: {e}"})
        else:
            _log.error(f"初始化失败：权限不足：{e}")
        return ExitCode.PERMISSION_ERROR
    except OSError as e:
        if output_format == "json":
            emit_json({"status": "error", "command": "init", "error": str(e)})
        else:
            _log.error(f"初始化失败：{e}")
        return ExitCode.PARTIAL_FAILURE

    if output_format == "json":
        emit_json(
            {
                "status": "success",
                "command": "init",
                "path": str(path),
                "created": created,
            }
        )
    else:
        _log.ok(f"已在 {path} 初始化 ConfMirror 项目")
        _log.info(f"  - {CONFIG_FILENAME}")
        for dirname in DEFAULT_DIRS:
            _log.info(f"  - {dirname}/")

    return ExitCode.SUCCESS
