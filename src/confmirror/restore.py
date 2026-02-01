import os
import shutil
import subprocess
from pathlib import Path

from .config import ConfigKeys
from .meta import read_meta


def execute_restore(config: dict, logger) -> None:
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


def restore_path(original: Path, mirror_root: Path, logger):
    backup = mirror_root / "mirror" / str(original).lstrip("/")
    meta = read_meta(backup)
    if not meta:
        logger.warning(f"[还原跳过] 缺少 .meta → {original}")
        return
    if not backup.exists():
        logger.warning(f"[还原跳过] 备份内容不存在 → {original}")
        return

    original.parent.mkdir(parents=True, exist_ok=True)
    mode = meta["mode"]
    uid = int(meta["uid"])
    gid = int(meta["gid"])
    ftype = meta["type"]

    if ftype == "file":
        shutil.copy2(backup, original)
        os.chmod(original, int(mode, 8))
        os.chown(original, uid, gid)
        logger.info(f"[文件还原成功] {original}")
    elif ftype == "dir":
        original.mkdir(exist_ok=True)
        # rsync-like copy (shutil.copytree 不覆盖，用 walk)
        for src_dir, dirs, files in os.walk(backup):
            dst_dir = original / Path(src_dir).relative_to(backup)
            dst_dir.mkdir(exist_ok=True)
            for file_ in files:
                if not file_.endswith(".meta"):
                    src_file = Path(src_dir) / file_
                    dst_file = dst_dir / file_
                    shutil.copy2(src_file, dst_file)
        os.chmod(original, int(mode, 8))
        os.chown(original, uid, gid)
        logger.info(f"[目录还原成功] {original}")