import os
import shutil
import subprocess
from pathlib import Path

from confmirror.config import ConfigKeys

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

def backup_path(src: Path, mirror_root: Path, logger):
    """
    备份单个路径（文件或目录）到镜像目录

    Args:
        src: 源路径
        mirror_root: 镜像根目录
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
        _backup_file(src, dest, logger)
    elif src.is_dir():
        _backup_directory(src, dest, logger)

def _backup_directory(src_dir: Path, dest_dir: Path, logger, recursive: bool = True):
    """
    备份目录及其内容

    Args:
        src_dir: 源目录
        dest_dir: 目标目录
        logger: 日志记录器
        recursive: 是否递归处理子目录 (True: 深度递归, False: 只处理直接子项)
    """
    # 创建目标目录
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 获取源目录的统计信息并写入目录的元数据
    src_stat = src_dir.stat()
    dir_mode = oct(src_stat.st_mode)[-3:]
    write_meta(dest_dir, dir_mode, src_stat.st_uid, src_stat.st_gid, "dir")

    # 记录目录元数据写入成功的日志
    logger.info(f"[目录信息备份成功] → {src_dir} (权限:{dir_mode} 用户:{src_stat.st_uid}:{src_stat.st_gid})")

    # 遍历源目录中的所有项目
    for item in src_dir.iterdir():
        if should_exclude(item.name):
            continue

        dest_item = dest_dir / item.name

        if item.is_file():
            _backup_file(item, dest_item, logger)
        elif item.is_dir():
            if recursive:
                # 递归处理子目录
                _backup_directory(item, dest_item, logger, recursive=True)
        else:
            logger.warning(f"[跳过] 不支持的文件类型: {item}")

def _backup_file(src: Path, dest: Path, logger):
    """
    备份单个文件

    Args:
        src: 源文件路径
        dest: 目标文件路径
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

        logger.info(f"[文件备份成功] → {src} (权限:{mode} 用户:{stat.st_uid}:{stat.st_gid})")
    except PermissionError:
        logger.error(f"[权限错误] 无法备份文件 {src}，可能需要更高权限")
    except Exception as e:
        logger.error(f"[备份失败] {src}: {str(e)}")


def backup_single_path(src: Path, mirror_root: Path, logger, recursive: bool = False):
    """
    备份单个路径（文件或目录）到镜像目录，支持递归选项

    Args:
        src: 源路径
        mirror_root: 镜像根目录
        logger: 日志记录器
        recursive: 是否递归备份目录内容
    """
    if not src.exists():
        logger.warning(f"[路径不存在] 跳过备份: {src}")
        return

    # 检查是否为支持的文件类型
    if not (src.is_file() or src.is_dir()):
        logger.warning(f"[跳过] 不支持的文件类型: {src}")
        return

    # 直接使用源路径的绝对路径作为备份路径
    dest = mirror_root / str(src).lstrip('/')

    if src.is_file():
        _backup_file(src, dest, logger)
    elif src.is_dir():
        _backup_directory(src, dest, logger, recursive=recursive)

def run_backup_script(script_rel: str, mirror_root: Path, logger):
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
        logger.error(f"[脚本备份失败] → 脚本不存在 {script}")
        return False

    try:
        # 确保脚本有执行权限
        script.chmod(0o755)
        logger.info(f"[脚本备份执行] → 运行脚本 {script}")

        # 执行脚本，传入"backup"参数
        result = subprocess.run(
            [str(script), "backup"],
            check=True,
            cwd=mirror_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        logger.info(f"[脚本备份成功] → 脚本执行完成")
        if result.stdout:
            logger.debug(f"[脚本输出] {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"[脚本备份失败] → 脚本执行异常: {e}")
        if e.stderr:
            logger.error(f"[脚本错误输出] {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"[脚本执行异常] → : {str(e)}")
        return False

def backup_module(module: dict, backup_root: Path, logger):
    """
    备份模块配置中指定的路径或脚本

    Args:
        module: 模块配置字典
        backup_root: 镜像根目录
        logger: 日志记录器
    """
    module_name = module[ConfigKeys.MOD_NAME]

    if ConfigKeys.MOD_SCRIPT in module:
        # 使用脚本备份
        script_rel = module[ConfigKeys.MOD_SCRIPT]
        logger.info(f"[模块备份] 正在使用脚本备份模块: {module_name}")
        success = run_backup_script(script_rel, backup_root, logger)
        if not success:
            logger.error(f"[模块备份失败] 模块: {module_name}")
    elif ConfigKeys.MOD_PATHS in module:
        # 使用路径备份
        parent_path = module.get(ConfigKeys.MOD_PARENT_PATH, "")

        for path_str in module[ConfigKeys.MOD_PATHS]:
            if parent_path:
                path = Path(parent_path) / path_str
            else:
                path = Path(path_str)

            backup_path(path, backup_root, logger)
    else:
        logger.warning(f"模块 {module_name} 既没有配置路径也没有配置脚本")