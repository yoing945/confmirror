import os
import shutil
import subprocess
from pathlib import Path

from .meta import write_meta


EXCLUDE_PATTERNS = {".git", "*.log", "*.tmp", "cache", "temp", "*.pid", "*.bak", "downloads"}

def should_exclude(name: str) -> bool:
    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith("*."):
            if name.endswith(pattern[1:]):
                return True
        elif pattern == name:
            return True
    return False

def backup_path(src: Path, mirror_root: Path, module_name: str, logger):
    if not src.exists():
        return
    dest = mirror_root / "mirror" / str(src).lstrip("/")
    if src.is_file():
        _backup_file(src, dest, module_name, logger)
    elif src.is_dir():
        logger.info(f"[进入目录] {src}")
        for item in src.rglob("*"):
            if should_exclude(item.name):
                logger.info(f"[跳过排除项] {item}")
                continue
            backup_path(item, mirror_root, module_name, logger)

def _backup_file(src: Path, dest: Path, module_name: str, logger):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    stat = src.stat()
    mode = oct(stat.st_mode)[-3:]
    write_meta(dest, mode, stat.st_uid, stat.st_gid, "file")
    logger.info(f"[文件备份成功] {module_name} → {src} (权限:{mode} 用户:{stat.st_uid}:{stat.st_gid})")

def run_backup_script(script_rel: str, mirror_root: Path, module_name: str, logger):
    script = mirror_root / "script-hooks" / script_rel
    if not script.exists():
        logger.error(f"[脚本备份失败] 模块{module_name} → 脚本不存在 {script}")
        return False
    script.chmod(0o755)
    logger.info(f"[脚本备份执行] 模块{module_name} → 运行脚本 {script}")
    try:
        subprocess.run([str(script), "backup"], check=True, cwd=mirror_root)
        logger.info(f"[脚本备份成功] 模块{module_name}")
        return True
    except subprocess.CalledProcessError:
        logger.error(f"[脚本备份失败] 模块{module_name} → 脚本执行异常")
        return False