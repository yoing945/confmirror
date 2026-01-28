from pathlib import Path


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