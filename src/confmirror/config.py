import logging
from pathlib import Path

import yaml

CONFIG_FILENAME = "confmirror.yaml"
APP_NAME = "confmirror"

class ConfigKeys:
    """配置键常量类"""
    # 配置节
    SECTION_SETTINGS = "settings"
    SECTION_MODULES = "modules"

    # 设置键
    NAME = "name"
    BACKUP_ROOT = "backup_root"
    SCRIPT_HOOKS_DIR = "script_hooks_dir"
    LOG_DIR = "log_dir"
    GIT_AUTO_COMMIT = "git_auto_commit"
    GIT_AUTO_PUSH = "git_auto_push"
    LOG_MAX_LINES = "log_max_lines"

    # 模块键
    MOD_NAME = "name"
    MOD_INCLUDE_PATHS = "include_paths"
    MOD_EXCLUDE_PATHS = "exclude_paths"
    MOD_SCRIPT = "script"
    MOD_PARENT_PATH = "parent_path"
    MOD_SCRIPT_LANG = "script_lang"


def load_config() -> dict:
    config_path = Path.cwd() / CONFIG_FILENAME
    logger = logging.getLogger(APP_NAME)

    if not config_path.exists():
        logger.error(
            f"❌ 当前目录未找到 {CONFIG_FILENAME}。\n"
            "请确保在项目根目录运行命令，并创建该文件。"
        )
        return {}

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"{CONFIG_FILENAME} 必须是一个 YAML 映射(dict)")


    settings_raw = config.get(ConfigKeys.SECTION_SETTINGS)
    if settings_raw is None:
        settings = {}
        config[ConfigKeys.SECTION_SETTINGS] = settings
    else:
        settings = settings_raw

    # 默认值
    settings.setdefault(ConfigKeys.NAME, Path.cwd().name)
    settings.setdefault(ConfigKeys.BACKUP_ROOT, "./mirror")
    settings.setdefault(ConfigKeys.SCRIPT_HOOKS_DIR, "./script-hooks")
    settings.setdefault(ConfigKeys.LOG_DIR, "./logs")
    settings.setdefault(ConfigKeys.GIT_AUTO_COMMIT, False)
    settings.setdefault(ConfigKeys.GIT_AUTO_PUSH, False)
    settings.setdefault(ConfigKeys.LOG_MAX_LINES, 1000)  # 默认1000行

    # 路径标准化（相对于当前工作目录）
    base = Path.cwd()
    settings[ConfigKeys.BACKUP_ROOT] = (base / settings[ConfigKeys.BACKUP_ROOT]).resolve()
    settings[ConfigKeys.SCRIPT_HOOKS_DIR] = (base / settings[ConfigKeys.SCRIPT_HOOKS_DIR]).resolve()
    settings[ConfigKeys.LOG_DIR] = (base / settings[ConfigKeys.LOG_DIR]).resolve()

    # 模块字段校验：modules[].name
    modules_raw = config.get(ConfigKeys.SECTION_MODULES)
    if modules_raw is None:
        modules = {}
        config[ConfigKeys.SECTION_MODULES] = modules
    else:
        modules = modules_raw

    # 标准化模块中的 parent_path 为绝对路径
    for i, mod in enumerate(modules):
        if not isinstance(mod, dict):
            logger.error(f"{ConfigKeys.SECTION_MODULES}[{i}] 必须是映射")
            return {}
        if ConfigKeys.MOD_NAME not in mod:
            logger.error(f"{ConfigKeys.SECTION_MODULES}[{i}].{ConfigKeys.MOD_NAME} 缺失")
            return {}

        # 如果模块中有 parent_path，则将其转换为绝对路径
        if ConfigKeys.MOD_PARENT_PATH in mod:
            parent_path = mod[ConfigKeys.MOD_PARENT_PATH]
            if parent_path:
                parent_path_path = Path(parent_path)
                # 如果是相对路径，则相对于当前工作目录转换为绝对路径
                if not parent_path_path.is_absolute():
                    parent_path_path = Path.cwd() / parent_path_path
                mod[ConfigKeys.MOD_PARENT_PATH] = str(parent_path_path.resolve())

        # 设置默认脚本语言
        if ConfigKeys.MOD_SCRIPT in mod:
            mod.setdefault(ConfigKeys.MOD_SCRIPT_LANG, "bash")

    return config