"""全局配置管理模块"""

import os
from pathlib import Path
import yaml
import logging
from typing import Dict, Any, Optional


# 全局配置文件路径 (参考 Git 的 ~.gitconfig 命名方式)
GLOBAL_CONFIG_PATH = Path.home() / ".confmirror"
GLOBAL_CONFIG_DIR = Path.home() / ".config" / "confmirror"
# 备用路径，如果主路径不存在则使用此路径
ALTERNATIVE_GLOBAL_CONFIG_PATH = GLOBAL_CONFIG_DIR / "config.yaml"

# 全局配置键
class GlobalConfigKeys:
    DEFAULT_CONFIG_PATH = "default_config_path"


def ensure_global_config_dir():
    """确保全局配置目录存在"""
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_global_config() -> Dict[str, Any]:
    """加载全局配置"""
    # 首先尝试从主路径加载
    config_path = GLOBAL_CONFIG_PATH
    
    # 如果主路径不存在，尝试备用路径
    if not config_path.exists():
        ensure_global_config_dir()
        config_path = ALTERNATIVE_GLOBAL_CONFIG_PATH
        
        # 如果备用路径也不存在，返回空配置
        if not config_path.exists():
            return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        return config
    except Exception as e:
        logging.error(f"加载全局配置失败: {e}")
        return {}


def save_global_config(config: Dict[str, Any], use_alt_path: bool = False) -> bool:
    """保存全局配置"""
    config_path = ALTERNATIVE_GLOBAL_CONFIG_PATH if use_alt_path else GLOBAL_CONFIG_PATH
    
    # 如果使用备用路径，确保目录存在
    if use_alt_path:
        ensure_global_config_dir()
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
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
    # 默认使用备用路径存储，因为主路径可能不是 YAML 格式
    return save_global_config(config, use_alt_path=True)


def remove_global_config_value(key: str) -> bool:
    """移除全局配置值"""
    config = load_global_config()
    if key in config:
        del config[key]
        # 默认使用备用路径存储
        return save_global_config(config, use_alt_path=True)
    return True  # 如果键不存在，也算成功移除