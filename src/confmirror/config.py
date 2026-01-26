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

    settings = config.setdefault("settings", {})

    # 如果没有设置 name，则使用当前目录名
    if "name" not in settings:
        settings["name"] = Path.cwd().name

    # 默认值
    settings.setdefault("backup_root", "./mirror")
    settings.setdefault("script_hooks_dir", "./script-hooks")
    settings.setdefault("log_dir", "./logs")          # ← 新增日志目录配置
    settings.setdefault("git_auto_commit", True)
    settings.setdefault("git_auto_push", False)

    # 路径标准化（相对于当前工作目录）
    base = Path.cwd()
    settings["backup_root"] = (base / settings["backup_root"]).resolve()
    settings["script_hooks_dir"] = (base / settings["script_hooks_dir"]).resolve()
    settings["log_dir"] = (base / settings["log_dir"]).resolve()

    # 模块字段校验：modules[].name
    for i, mod in enumerate(config.get("modules", [])):
        if not isinstance(mod, dict):
            raise ValueError(f"modules[{i}] 必须是映射")
        if "name" not in mod:
            raise KeyError(f"modules[{i}].name 缺失")

    return config