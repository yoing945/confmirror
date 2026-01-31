from pathlib import Path
from typing import Optional

from .backup import backup_module, backup_single_path, expand_path_patterns
from .config import ConfigKeys

def find_matching_module_with_path(modules: list, path: Path) -> Optional[dict]:
    """
    查找包含指定路径的模块

    Args:
        modules: 模块配置列表
        path: 要查找的路径

    Returns:
        包含该路径的模块配置字典，如果未找到则返回None
    """
    for module in modules:
        if ConfigKeys.MOD_PATHS in module:
            parent_path = module.get(ConfigKeys.MOD_PARENT_PATH, "")
            for path_str in module[ConfigKeys.MOD_PATHS]:
                if parent_path:
                    module_path = Path(parent_path) / path_str
                else:
                    module_path = Path(path_str)
                if path.is_relative_to(module_path):
                    return module
    return None

def backup(config: dict, logger, target_module_name: Optional[str] = None, target_path: Optional[str] = None) -> None:
    """
    执行备份操作

    Args:
        config: 配置字典
        logger: 日志记录器
        target_module_name: 指定要备份的模块名称
        target_path: 指定要备份的路径
    """
    settings = config[ConfigKeys.SECTION_SETTINGS]
    backup_root = Path(settings[ConfigKeys.BACKUP_ROOT])

    # 确保备份根目录存在
    backup_root.mkdir(parents=True, exist_ok=True)

    if target_module_name:
        # 分模块备份
        modules = config.get(ConfigKeys.SECTION_MODULES, [])
        found_module = next((mod for mod in modules if mod[ConfigKeys.MOD_NAME] == target_module_name), None)
        if not found_module:
            logger.error(f"找不到模块: '{target_module_name}' ")
            return
        backup_module(found_module, backup_root, logger)

    elif target_path:
        if not find_matching_module_with_path(config.get(ConfigKeys.SECTION_MODULES, []), Path(target_path)):
            logger.error(f"路径 '{target_path}' 不属于任何模块，无法备份")
            return
        # 指定路径备份 - 处理通配符路径
        # 展开可能的通配符路径
        expanded_paths = expand_path_patterns(target_path)

        if not expanded_paths:
            logger.warning(f"路径模式未匹配到任何文件: {target_path}")
            return

        # 对每个匹配的路径进行备份
        for path in expanded_paths:
            backup_single_path(path, backup_root, logger)
    else:
        # 全量备份
        for module in config.get(ConfigKeys.SECTION_MODULES, []):
            backup_module(module, backup_root, logger)



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