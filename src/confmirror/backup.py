import os
import shutil
import subprocess
from pathlib import Path

from .meta import write_meta


def should_exclude(name: str) -> bool:
    """
    检查文件名是否应该被排除

    Args:
        name: 文件或目录名称

    Returns:
        bool: 如果应该排除则返回True，否则返回False
    """
    # 默认不排除任何文件，让用户通过配置来决定哪些文件需要排除
    return False

def backup_path(src: Path, mirror_root: Path, module_name: str, logger):
    """
    备份单个路径（文件或目录）到镜像目录

    Args:
        src: 源路径
        mirror_root: 镜像根目录
        module_name: 模块名称
        logger: 日志记录器
    """
    if not src.exists():
        logger.warning(f"[路径不存在] 跳过备份: {src}")
        return

    # 检查是否为支持的文件类型
    if not (src.is_file() or src.is_dir()):
        logger.warning(f"[跳过] 不支持的文件类型: {src}")
        return

    # 直接使用源路径的绝对路径作为备份路径，不使用/mirror子目录
    # 这样可以保持与原始shell脚本一致的行为
    dest = mirror_root / str(src).lstrip('/')

    if src.is_file():
        _backup_file(src, dest, module_name, logger)
    elif src.is_dir():
        _backup_directory(src, dest, module_name, logger)

def _backup_directory(src_dir: Path, dest_dir: Path, module_name: str, logger):
    """
    备份目录及其内容

    Args:
        src_dir: 源目录
        dest_dir: 目标目录
        module_name: 模块名称
        logger: 日志记录器
    """
    logger.info(f"[进入目录] {src_dir}")

    # 创建目标目录
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 获取源目录的统计信息并写入目录的元数据
    src_stat = src_dir.stat()
    dir_mode = oct(src_stat.st_mode)[-3:]
    write_meta(dest_dir, dir_mode, src_stat.st_uid, src_stat.st_gid, "dir")

    # 获取目录中所有条目（包括隐藏文件）
    for item in src_dir.iterdir():
        if should_exclude(item.name):
            logger.info(f"[跳过排除项] {item}")
            continue

        dest_item = dest_dir / item.name
        if item.is_file():
            _backup_file(item, dest_item, module_name, logger)
        elif item.is_dir():
            _backup_directory(item, dest_item, module_name, logger)
        else:
            logger.warning(f"[跳过] 不支持的文件类型: {item}")

def _backup_file(src: Path, dest: Path, module_name: str, logger):
    """
    备份单个文件

    Args:
        src: 源文件路径
        dest: 目标文件路径
        module_name: 模块名称
        logger: 日志记录器
    """
    try:
        # 确保目标父目录存在
        dest.parent.mkdir(parents=True, exist_ok=True)

        # 复制文件
        shutil.copy2(src, dest)

        # 获取文件统计信息
        stat = src.stat()
        mode = oct(stat.st_mode)[-3:]  # 获取最后3位权限数字

        # 写入元数据
        write_meta(dest, mode, stat.st_uid, stat.st_gid, "file")

        logger.info(f"[文件备份成功] {module_name} → {src} (权限:{mode} 用户:{stat.st_uid}:{stat.st_gid})")
    except PermissionError:
        logger.error(f"[权限错误] 无法备份文件 {src}，可能需要更高权限")
    except Exception as e:
        logger.error(f"[备份失败] {src}: {str(e)}")

def backup_entire_dir(src_dir: Path, dest_dir: Path, module_name: str, logger):
    """
    递归备份整个目录树

    Args:
        src_dir: 源目录
        dest_dir: 目标目录
        module_name: 模块名称
        logger: 日志记录器
    """
    if not src_dir.is_dir():
        logger.error(f"[错误] 源路径不是目录: {src_dir}")
        return

    logger.info(f"[开始目录备份] {src_dir} -> {dest_dir}")

    # 创建目标目录
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 获取源目录的统计信息
    src_stat = src_dir.stat()
    dir_mode = oct(src_stat.st_mode)[-3:]

    # 写入目录的元数据
    write_meta(dest_dir, dir_mode, src_stat.st_uid, src_stat.st_gid, "dir")

    # 使用iterdir而不是rglob，这样可以更准确地控制递归行为
    # 并且与shell脚本中的find命令逻辑更接近
    for item in src_dir.rglob("*"):  # 递归获取所有子项
        # 检查是否应该排除
        if should_exclude(item.name):
            logger.info(f"[跳过排除项] {item}")
            continue

        # 计算相对路径并构建目标路径
        rel_path = item.relative_to(src_dir)
        dest_item = dest_dir / rel_path

        if item.is_file():
            _backup_file(item, dest_item, module_name, logger)
        elif item.is_dir():
            # 为子目录也创建相应的目标目录
            dest_item.mkdir(parents=True, exist_ok=True)
            # 写入子目录的元数据
            subdir_stat = item.stat()
            subdir_mode = oct(subdir_stat.st_mode)[-3:]
            write_meta(dest_item, subdir_mode, subdir_stat.st_uid, subdir_stat.st_gid, "dir")
        else:
            logger.warning(f"[跳过] 不支持的文件类型: {item}")

def run_backup_script(script_rel: str, mirror_root: Path, module_name: str, logger):
    """
    执行备份脚本

    Args:
        script_rel: 脚本相对路径
        mirror_root: 镜像根目录
        module_name: 模块名称
        logger: 日志记录器

    Returns:
        bool: 脚本执行成功返回True，否则返回False
    """
    script = mirror_root / "script-hooks" / script_rel
    if not script.exists():
        logger.error(f"[脚本备份失败] 模块{module_name} → 脚本不存在 {script}")
        return False

    try:
        # 确保脚本有执行权限
        script.chmod(0o755)
        logger.info(f"[脚本备份执行] 模块{module_name} → 运行脚本 {script}")

        # 执行脚本，传入"backup"参数
        result = subprocess.run(
            [str(script), "backup"],
            check=True,
            cwd=mirror_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        logger.info(f"[脚本备份成功] 模块{module_name} → 脚本执行完成")
        if result.stdout:
            logger.debug(f"[脚本输出] {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"[脚本备份失败] 模块{module_name} → 脚本执行异常: {e}")
        if e.stderr:
            logger.error(f"[脚本错误输出] {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"[脚本执行异常] 模块{module_name}: {str(e)}")
        return False