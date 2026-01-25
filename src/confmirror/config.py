# src/confmirror/config.py

from pathlib import Path

import yaml

CONFIG_FILENAME = "confmirror.yaml"

def load_config() -> dict:
    config_path = Path.cwd() / CONFIG_FILENAME
    if not config_path.exists():
        raise FileNotFoundError(
            f"❌ 当前目录未找到 {CONFIG_FILENAME}。\n"
            "请确保在项目根目录运行命令，并创建该文件。"
        )

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"{CONFIG_FILENAME} 必须是一个 YAML 映射（dict）")

    meta = config.setdefault("metadata", {})
    # 必填：name
    if "name" not in meta:
        raise KeyError("metadata.name 是必填项（用于标识配置集）")

    # 默认值
    meta.setdefault("backup_root", "./mirror")
    meta.setdefault("script_hooks_dir", "./script-hooks")
    meta.setdefault("log_dir", "./logs")          # ← 新增日志目录配置
    meta.setdefault("git_auto_commit", True)
    meta.setdefault("git_auto_push", False)

    # 路径标准化（相对于当前工作目录）
    base = Path.cwd()
    meta["backup_root"] = (base / meta["backup_root"]).resolve()
    meta["script_hooks_dir"] = (base / meta["script_hooks_dir"]).resolve()
    meta["log_dir"] = (base / meta["log_dir"]).resolve()

    # 模块字段校验：modules[].name
    for i, mod in enumerate(config.get("modules", [])):
        if not isinstance(mod, dict):
            raise ValueError(f"modules[{i}] 必须是映射")
        if "name" not in mod:
            raise KeyError(f"modules[{i}].name 缺失")

    return config