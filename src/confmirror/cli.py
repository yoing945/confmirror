import logging
import sys
import traceback
from pathlib import Path

import click

from .config import APP_NAME, ConfigKeys, load_config
from .core import backup as core_backup, restore as core_restore
from .gitops import git_auto_commit_and_push
from .logger import setup_logger
from .perms import get_perms_for_module, get_perms_for_path, display_perms_info


@click.group()
def main():
    pass

@main.command()
def backup():
    # 备份
    try:
        # 加载配置文件
        config = load_config()

        # 检查配置是否加载成功
        if not config:
            click.echo("❌ 配置加载失败，无法执行备份任务", err=True)
            sys.exit(1)

        settings:dict = config[ConfigKeys.SECTION_SETTINGS]
        log_dir = settings[ConfigKeys.LOG_DIR]
        name = settings[ConfigKeys.NAME]
        logger = setup_logger(log_dir, name)
        logger.info("开始执行备份任务")

        core_backup(config, logger)

        if settings.get(ConfigKeys.GIT_AUTO_COMMIT):
            msg = f"confmirror 备份: {name}"
            git_auto_commit_and_push(
                repo_path=Path.cwd(),
                message=msg,
                auto_push=settings.get(ConfigKeys.GIT_AUTO_PUSH, False)
            )
            logger.info("Git 提交完成")

        logger.info("✅ 备份成功完成")
    except Exception as e:
        logger = logging.getLogger(APP_NAME)
        logger.error(traceback.format_exc())

        sys.exit(1)

@main.command()
def restore():
    # 恢复
    try:
        config = load_config()

        # 检查配置是否加载成功
        if not config:
            click.echo("❌ 配置加载失败，无法执行恢复任务", err=True)
            sys.exit(1)

        settings:dict = config[ConfigKeys.SECTION_SETTINGS]
        log_dir = settings[ConfigKeys.LOG_DIR]
        name = settings[ConfigKeys.NAME]
        logger = setup_logger(log_dir, name)
        logger.info("开始执行恢复任务")
        core_restore(config, logger)
        logger.info("✅ 恢复成功完成")
    except Exception as e:
        # 记录详细的错误信息和堆栈跟踪到日志（始终记录）
        logger = logging.getLogger("confmirror")
        logger.error(f"❌ 恢复失败: {e}")
        logger.error(f"详细错误信息:\n{traceback.format_exc()}")

        # 在控制台输出基本信息
        click.echo(f"❌ 恢复失败: {e}", err=True)

        sys.exit(1)

@main.command()
@click.option('--module', '-m', type=str, help='查看指定模块的权限信息')
@click.argument('target_path', required=False, type=str)
@click.option('-r', '--recursive', is_flag=True, help='递归查看路径下的所有文件权限')
def perms(module, target_path, recursive):
    """查看备份文件的权限信息"""
    try:
        config = load_config()

        # 检查配置是否加载成功
        if not config:
            click.echo("❌ 配置加载失败，无法查看权限信息", err=True)
            sys.exit(1)

        if module:
            # 查看指定模块的权限信息
            perms_info = get_perms_for_module(module, config)
            display_perms_info(perms_info, config)
        elif target_path:
            # 查看指定路径的权限信息
            perms_info = get_perms_for_path(config, target_path, recursive)
            display_perms_info(perms_info, config)
        else:
            # 没有参数，列出所有模块
            modules = config.get(ConfigKeys.SECTION_MODULES, [])
            if modules:
                print("可用的模块:")
                for mod in modules:
                    print(f"  - {mod[ConfigKeys.MOD_NAME]}")
            else:
                print("没有找到任何模块")

    except Exception as e:
        click.echo(f"❌ 查看权限信息失败: {e}", err=True)
        sys.exit(1)