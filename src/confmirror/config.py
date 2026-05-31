import logging
import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
import yaml.parser
import yaml.scanner

from .global_config import GlobalConfigKeys, get_global_config_value
from .logger import ModuleLog

logger = logging.getLogger(__name__)
_log = ModuleLog("config", logger)

CONFIG_FILENAME = "confmirror.yaml"
APP_NAME = "confmirror"


class ConfigKeys:
    """配置键常量类（用于 YAML 解析层）"""
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
    BACKUP_FILE_MODE = "backup_file_mode"
    BACKUP_DIR_MODE = "backup_dir_mode"

    # 模块键
    MOD_NAME = "name"
    MOD_INCLUDE_PATHS = "include_paths"
    MOD_EXCLUDE_PATHS = "exclude_paths"
    MOD_SCRIPT = "script"
    MOD_PARENT_PATH = "parent_path"
    MOD_SCRIPT_LANG = "script_lang"


@dataclass
class Settings:
    """全局配置"""
    name: str
    backup_root: Path
    script_hooks_dir: Path = field(default_factory=lambda: Path("./script-hooks"))
    log_dir: Path = field(default_factory=lambda: Path("./logs"))
    log_max_lines: int = 1000
    git_auto_commit: bool = False
    git_auto_push: bool = False
    backup_file_mode: str = "0o644"
    backup_dir_mode: str = "0o755"


@dataclass
class ModuleConfig:
    """模块配置"""
    name: str
    include_paths: Optional[List[str]] = None
    exclude_paths: Optional[List[str]] = None
    script: Optional[str] = None
    parent_path: Optional[str] = None
    script_lang: str = "bash"


@dataclass
class Config:
    """根配置"""
    settings: Settings
    modules: List[ModuleConfig]


def validate_yaml_syntax(file_path: Path) -> tuple[bool, str]:
    """
    验证YAML文件的语法

    Args:
        file_path: YAML文件路径

    Returns:
        tuple[bool, str]: (是否有效, 错误信息)
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            yaml.safe_load(f)
        return True, ""
    except yaml.parser.ParserError as e:
        return False, f"YAML 解析错误: {e}"
    except yaml.scanner.ScannerError as e:
        return False, f"YAML 扫描错误: {e}"
    except UnicodeDecodeError as e:
        return False, f"文件编码错误: {e}"
    except Exception as e:
        return False, f"读取文件时发生未知错误: {e}"


def validate_config_structure(config: dict) -> bool:
    """
    验证配置文件的结构是否符合要求

    Args:
        config: 配置字典

    Returns:
        bool: 结构是否有效
    """
    # 验证 settings 部分
    if ConfigKeys.SECTION_SETTINGS in config:
        settings = config[ConfigKeys.SECTION_SETTINGS]
        if settings is not None and not isinstance(settings, dict):
            _log.error(f"'{ConfigKeys.SECTION_SETTINGS}' 必须是一个字典")
            return False

    # 验证 modules 部分
    if ConfigKeys.SECTION_MODULES in config:
        modules = config[ConfigKeys.SECTION_MODULES]
        if modules is not None:
            if not isinstance(modules, list):
                _log.error(f"'{ConfigKeys.SECTION_MODULES}' 必须是一个列表")
                return False

            for i, module in enumerate(modules):
                if not isinstance(module, dict):
                    _log.error(f"{ConfigKeys.SECTION_MODULES}[{i}] 必须是字典")
                    return False

                if ConfigKeys.MOD_NAME not in module:
                    _log.error(f"{ConfigKeys.SECTION_MODULES}[{i}] 缺少必需字段 '{ConfigKeys.MOD_NAME}'")
                    return False

                module_name = module[ConfigKeys.MOD_NAME]
                if not isinstance(module_name, str):
                    _log.error(f"{ConfigKeys.SECTION_MODULES}[{i}].{ConfigKeys.MOD_NAME} 必须是字符串")
                    return False

    return True


def resolve_config_path(custom_config_path: Optional[str] = None) -> Path:
    """解析配置文件路径（不读取内容）

    优先级：
    1. 传入的自定义配置路径
    2. 全局配置中设置的默认路径
    3. 当前目录下的 confmirror.yaml
    """
    if custom_config_path:
        return Path(custom_config_path).expanduser()

    global_config_path = get_global_config_value(GlobalConfigKeys.DEFAULT_CONFIG_PATH)
    if global_config_path:
        return Path(global_config_path).expanduser()

    return Path.cwd() / CONFIG_FILENAME


def _build_settings(settings_dict: dict) -> Settings:
    """通过 dataclass fields 反射自动映射，减少硬编码。"""
    path_fields = {"backup_root", "script_hooks_dir", "log_dir"}
    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(Settings):
        key = getattr(ConfigKeys, f.name.upper())
        value = settings_dict[key]
        if f.name in path_fields:
            value = Path(value)
        kwargs[f.name] = value
    return Settings(**kwargs)


def _build_module(module_dict: dict) -> ModuleConfig:
    """通过 dataclass fields 反射自动映射，减少硬编码。"""
    kwargs: dict[str, Any] = {}
    for f in dataclasses.fields(ModuleConfig):
        key = getattr(ConfigKeys, f"MOD_{f.name.upper()}")
        if f.name == "script_lang":
            value = module_dict.get(key, "bash")
        else:
            value = module_dict.get(key)
        kwargs[f.name] = value
    return ModuleConfig(**kwargs)


def _dict_to_config(config_dict: dict) -> Config:
    """将处理后的字典转换为 Config dataclass"""
    settings_dict = config_dict[ConfigKeys.SECTION_SETTINGS]
    modules_dict = config_dict[ConfigKeys.SECTION_MODULES]

    settings = _build_settings(settings_dict)
    modules = [_build_module(m) for m in modules_dict]

    return Config(settings=settings, modules=modules)


def _load_yaml(config_path: Path) -> Optional[dict]:
    """加载并解析 YAML 配置文件"""
    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        _log.error(f"读取配置文件时发生错误: {e}")
        return None

    if not isinstance(data, dict):
        _log.error(f"{config_path} 必须是一个 YAML 映射(dict)")
        return None

    return data


def _apply_defaults(config: dict, config_path: Path) -> None:
    """填充 settings 和 modules 的默认值（原地修改）"""
    settings = config.setdefault(ConfigKeys.SECTION_SETTINGS, {})
    settings.setdefault(ConfigKeys.NAME, config_path.parent.name)
    settings.setdefault(ConfigKeys.BACKUP_ROOT, "./mirror")
    settings.setdefault(ConfigKeys.SCRIPT_HOOKS_DIR, "./script-hooks")
    settings.setdefault(ConfigKeys.LOG_DIR, "./logs")
    settings.setdefault(ConfigKeys.GIT_AUTO_COMMIT, False)
    settings.setdefault(ConfigKeys.GIT_AUTO_PUSH, False)
    settings.setdefault(ConfigKeys.LOG_MAX_LINES, 1000)
    settings.setdefault(ConfigKeys.BACKUP_FILE_MODE, "0o644")
    settings.setdefault(ConfigKeys.BACKUP_DIR_MODE, "0o755")
    config.setdefault(ConfigKeys.SECTION_MODULES, [])


def _normalize_paths(config: dict, config_path: Path) -> bool:
    """将 settings 中的相对路径转换为绝对路径（原地修改）。

    Returns:
        bool: 路径解析成功返回 True，否则返回 False
    """
    base = config_path.parent
    settings = config[ConfigKeys.SECTION_SETTINGS]
    for key in (ConfigKeys.BACKUP_ROOT, ConfigKeys.SCRIPT_HOOKS_DIR, ConfigKeys.LOG_DIR):
        try:
            settings[key] = (base / settings[key]).resolve()
        except (OSError, RuntimeError) as e:
            _log.error(f"路径解析失败: {base / settings[key]} ({e})")
            return False
    return True


def _normalize_modules(config: dict, config_path: Path) -> bool:
    """标准化模块字段，返回是否成功"""
    modules = config[ConfigKeys.SECTION_MODULES]
    for i, mod in enumerate(modules):
        if not isinstance(mod, dict):
            _log.error(f"{ConfigKeys.SECTION_MODULES}[{i}] 必须是映射")
            return False
        if ConfigKeys.MOD_NAME not in mod:
            _log.error(f"{ConfigKeys.SECTION_MODULES}[{i}].{ConfigKeys.MOD_NAME} 缺失")
            return False

        # 如果模块中有 parent_path，则将其转换为绝对路径
        if ConfigKeys.MOD_PARENT_PATH in mod:
            parent_path = mod[ConfigKeys.MOD_PARENT_PATH]
            if parent_path:
                parent_path_path = Path(parent_path)
                if not parent_path_path.is_absolute():
                    parent_path_path = config_path.parent / parent_path_path
                mod[ConfigKeys.MOD_PARENT_PATH] = str(parent_path_path.resolve())

        # 设置默认脚本语言
        if ConfigKeys.MOD_SCRIPT in mod:
            mod.setdefault(ConfigKeys.MOD_SCRIPT_LANG, "bash")

    return True


def load_config(custom_config_path: Optional[str] = None) -> Optional[Config]:
    config_path = resolve_config_path(custom_config_path)

    if not config_path.exists():
        _log.error(
            f"未找到配置文件: {config_path}。\n"
            f"请确保配置文件存在，或使用 -c/--config 指定配置文件路径，或通过 `confmirror global_config_path set <path>` 设置全局配置路径。"
        )
        return None

    # 首先验证YAML语法
    is_valid, error_msg = validate_yaml_syntax(config_path)
    if not is_valid:
        _log.error(f"配置文件格式错误: {error_msg}")
        _log.error(f"请检查 {config_path} 文件格式是否正确")
        return None

    config = _load_yaml(config_path)
    if config is None:
        return None

    # 验证配置结构
    if not validate_config_structure(config):
        _log.error(f"请修正 {config_path} 文件中的配置结构问题")
        return None

    _apply_defaults(config, config_path)
    if not _normalize_paths(config, config_path):
        _log.error(f"请修正 {config_path} 文件中的路径配置")
        return None
    if not _normalize_modules(config, config_path):
        _log.error(f"请修正 {config_path} 文件中的配置结构问题")
        return None

    return _dict_to_config(config)
