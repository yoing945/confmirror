from pathlib import Path

from .backup import backup_path, run_backup_script, backup_entire_dir
from .config import ConfigKeys


def backup(config: dict, logger) -> None:
    """
    执行备份操作

    Args:
        config: 配置字典
        logger: 日志记录器
    """
    settings = config[ConfigKeys.SECTION_SETTINGS]
    backup_root = Path(settings[ConfigKeys.BACKUP_ROOT])

    # 确保备份根目录存在
    backup_root.mkdir(parents=True, exist_ok=True)

    logger.info(f"开始备份，镜像目录: {backup_root}")

    # 实现模块备份逻辑
    for module in config.get(ConfigKeys.SECTION_MODULES, []):
        module_name = module[ConfigKeys.MOD_NAME]

        if ConfigKeys.MOD_SCRIPT in module:
            # 使用脚本备份
            script_rel = module[ConfigKeys.MOD_SCRIPT]
            logger.info(f"[模块备份] 正在使用脚本备份模块: {module_name}")
            success = run_backup_script(script_rel, backup_root, module_name, logger)
            if not success:
                logger.error(f"[模块备份失败] 模块: {module_name}")
        elif ConfigKeys.MOD_PATHS in module:
            # 使用路径备份
            parent_path = module.get(ConfigKeys.MOD_PARENT_PATH, "")

            logger.info(f"[模块备份] 正在备份模块: {module_name}")

            for path_str in module[ConfigKeys.MOD_PATHS]:
                # 如果指定了parent_path，则将其与路径拼接
                if parent_path:
                    path = Path(parent_path) / path_str
                else:
                    path = Path(path_str)

                logger.info(f"[路径备份] 正在备份路径: {path}")
                backup_path(path, backup_root, module_name, logger)
        else:
            logger.warning(f"[模块配置错误] 模块 {module_name} 既没有配置路径也没有配置脚本")

    logger.info("备份完成")


def restore(config: dict, logger) -> None:
    """
    执行恢复操作

    Args:
        config: 配置字典
        logger: 日志记录器
    """
    settings = config[ConfigKeys.SECTION_SETTINGS]
    backup_root = Path(settings[ConfigKeys.BACKUP_ROOT])
    logger.info(f"开始从 {backup_root} 恢复配置")

    # TODO: 实现恢复逻辑
    # for module in config.get(ConfigKeys.SECTION_MODULES, []):
    #     # 处理模块恢复
    #     pass

    logger.info("恢复完成")