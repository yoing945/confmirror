from pathlib import Path
from typing import Optional

from .backup import backup_module, backup_single_path
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
                if path == module_path:
                    return module
    return None

def backup(config: dict, logger, target_module_name: Optional[str] = None, target_path: Optional[str] = None, recursive: bool = False) -> None:
    """
    执行备份操作

    Args:
        config: 配置字典
        logger: 日志记录器
        target_module_name: 指定要备份的模块名称
        target_path: 指定要备份的路径
        recursive: 是否递归备份路径下的所有文件
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
        # 指定路径备份
        path = Path(target_path)
        logger.info(f"[路径备份] 正在备份路径: {path}")

        # 首先检查目标路径是否存在元数据文件，如果有则直接进行备份
        from .meta import meta_path_exists
        mirrored_path = backup_root / str(path).lstrip('/')

        if meta_path_exists(mirrored_path):
            # 存在对应的meta文件，进行备份
            backup_single_path(path, backup_root, logger, recursive=recursive)
        else:
            # 检查路径是否在配置的模块路径列表中
            modules = config.get(ConfigKeys.SECTION_MODULES, [])
            found_module = find_matching_module_with_path(modules, path)
            if found_module:
                if path.is_file() or path.is_dir():
                    backup_single_path(path, backup_root, logger, recursive=recursive)
                else:
                    logger.warning(f"路径不存在: {path}")
            else:
                logger.warning(f"路径 '{path}' 未在配置文件中定义")
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