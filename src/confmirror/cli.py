import sys
import traceback
from pathlib import Path

import click

from .config import ConfigKeys, load_config
from .core import backup as core_backup, restore as core_restore
from .gitops import git_auto_commit_and_push
from .logger import setup_logger


@click.group()
def main():
    pass

@main.command()
def backup():
    # 备份
    try:
        # 加载配置文件
        config = load_config()
        settings:dict = config[ConfigKeys.SECTION_SETTINGS]
        # 设置日志记录器
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
        # 记录详细的错误信息和堆栈跟踪到日志（始终记录）
        logger.error(f"❌ 备份失败: {e}")
        logger.error(f"详细错误信息:\n{traceback.format_exc()}")

        # 在控制台输出基本信息
        click.echo(f"❌ 备份失败: {e}", err=True)

        # 如果设置了调试模式，则在控制台也显示堆栈跟踪
        if settings.get(ConfigKeys.DEBUG_MODE, False):
            click.echo(f"详细错误信息:\n{traceback.format_exc()}", err=True)
        else:
            # 在生产环境中提示用户查看日志文件获取更多信息
            click.echo(f"请查看日志文件 '{log_dir}/{name}.log' 获取更多详细信息", err=True)

        sys.exit(1)

@main.command()
def restore():
    # 恢复
    try:
        config = load_config()
        settings:dict = config[ConfigKeys.SECTION_SETTINGS]
        log_dir = settings[ConfigKeys.LOG_DIR]
        name = settings[ConfigKeys.NAME]
        logger = setup_logger(log_dir, name)
        logger.info("开始执行恢复任务")
        core_restore(config, logger)
        logger.info("✅ 恢复成功完成")
    except Exception as e:
        # 记录详细的错误信息和堆栈跟踪到日志（始终记录）
        logger.error(f"❌ 恢复失败: {e}")
        logger.error(f"详细错误信息:\n{traceback.format_exc()}")

        # 在控制台输出基本信息
        click.echo(f"❌ 恢复失败: {e}", err=True)

        # 如果设置了调试模式，则在控制台也显示堆栈跟踪
        if settings.get(ConfigKeys.DEBUG_MODE, False):
            click.echo(f"详细错误信息:\n{traceback.format_exc()}", err=True)
        else:
            # 在生产环境中提示用户查看日志文件获取更多信息
            click.echo(f"请查看日志文件 '{log_dir}/{name}.log' 获取更多详细信息", err=True)

        sys.exit(1)