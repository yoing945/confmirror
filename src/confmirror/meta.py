from pathlib import Path


def write_meta(path: Path, mode: str, uid: int, gid: int, ftype: str):
    meta = path.with_suffix(path.suffix + ".meta")
    meta.parent.mkdir(parents=True, exist_ok=True)
    with open(meta, "w") as f:
        f.write(f"mode:{mode}\n")
        f.write(f"uid:{uid}\n")
        f.write(f"gid:{gid}\n")
        f.write(f"type:{ftype}\n")

def read_meta(path: Path):
    meta = path.with_suffix(path.suffix + ".meta")
    if not meta.exists():
        return None
    data = {}
    with open(meta) as f:
        for line in f:
            if ":" in line:
                k, v = line.strip().split(":", 1)
                data[k] = v
    return data