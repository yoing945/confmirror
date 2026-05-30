import logging
from pathlib import Path
from typing import Dict, Any


def write_meta(path: Path, mode: str, uid: int, gid: int, ftype: str):
    # 根据文件类型选择元数据文件后缀
    if ftype == "dir":
        # 目录使用 .dir.meta 后缀以避免与同名文件冲突
        meta = path.with_name(path.name + '.dir.meta')
    else:
        # 文件使用 .meta 后缀
        meta = path.with_suffix(path.suffix + ".meta")
    meta.parent.mkdir(parents=True, exist_ok=True)
    with open(meta, "w") as f:
        f.write(f"mode:{mode}\n")
        f.write(f"uid:{uid}\n")
        f.write(f"gid:{gid}\n")
        f.write(f"type:{ftype}\n")


def read_meta(path: Path):
    # 首先尝试读取普通文件的元数据(.meta)
    meta = path.with_suffix(path.suffix + ".meta")
    if not meta.exists():
        # 如果普通.meta文件不存在，尝试.dir.meta文件（目录）
        meta = path.with_name(path.name + '.dir.meta')
        if not meta.exists():
            return None
    data = {}
    with open(meta) as f:
        for line in f:
            if ":" in line:
                k, v = line.strip().split(":", 1)
                data[k] = v
    return data


def meta_path_exists(path: Path) -> bool:
    """
    检查给定路径是否存在对应的元数据文件

    Args:
        path: 需要检查的路径

    Returns:
        bool: 如果存在对应的元数据文件则返回True，否则返回False
    """
    # 尝试普通文件的元数据文件
    meta_file = path.with_suffix(path.suffix + ".meta")
    if meta_file.exists():
        return True

    # 尝试目录的元数据文件
    meta_dir = path.with_name(path.name + '.dir.meta')
    if meta_dir.exists():
        return True

    return False