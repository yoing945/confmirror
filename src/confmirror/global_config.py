"""全局配置管理模块"""

import logging
from pathlib import Path
from typing import Any, Dict

import yaml

# 全局配置文件路径，遵循 XDG Base Directory 规范
CONFIG_DIR = Path.home() / ".config" / "confmirror"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# 全局配置键
class GlobalConfigKeys:
    # 默认配置文件路径键
    DEFAULT_CONFIG_PATH = "default_config_path"


def ensure_config_dir():
    """确保全局配置目录存在"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_global_config() -> Dict[str, Any]:
    """加载全局配置"""
    if not CONFIG_FILE.exists():
        return {}

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        return config
    except Exception as e:
        logging.error(f"加载全局配置失败: {e}")
        return {}


def save_global_config(config: Dict[str, Any]) -> bool:
    """保存全局配置"""
    ensure_config_dir()
    
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        return True
    except Exception as e:
        logging.error(f"保存全局配置失败: {e}")
        return False


def get_global_config_value(key: str) -> Any:
    """获取全局配置值"""
    config = load_global_config()
    return config.get(key)


def set_global_config_value(key: str, value: Any) -> bool:
    """设置全局配置值"""
    config = load_global_config()
    config[key] = value
    return save_global_config(config)


def remove_global_config_value(key: str) -> bool:
    """移除全局配置值"""
    config = load_global_config()
    if key in config:
        del config[key]
        return save_global_config(config)
    return True  # 如果键不存在，也算成功移除