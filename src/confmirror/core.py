# src/confmirror/core.py

import shutil
from pathlib import Path
from typing import Any, Dict

from .backup import backup_path, run_backup_script


def backup(config: Dict[str, Any], logger) -> None:
    settings = config["settings"]
    backup_root = Path(settings["backup_root"])
    backup_root.mkdir(parents=True, exist_ok=True)

    logger.info(f"开始备份，目标目录: {backup_root}")

    # 实现模块备份逻辑
    for module in config.get("modules", []):
        if "script" in module:
            # 使用脚本备份
            script_rel = module["script"]
            module_name = module["name"]
            run_backup_script(script_rel, backup_root, module_name, logger)
        elif "paths" in module:
            # 使用路径备份
            module_name = module["name"]
            parent_path = module.get("parent_path", "")

            for path_str in module["paths"]:
                path = Path(parent_path) / path_str
                backup_path(path, backup_root, module_name, logger)

    logger.info("备份完成")

def restore(config: Dict[str, Any], logger) -> None:
    settings = config["settings"]
    backup_root = Path(settings["backup_root"])
    logger.info(f"开始从 {backup_root} 恢复配置")

    # TODO: 实现恢复逻辑
    # for module in config.get("modules", []):
    #     # 处理模块恢复
    #     pass

    logger.info("恢复完成")