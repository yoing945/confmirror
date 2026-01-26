import sys
from pathlib import Path

import click

from .config import load_config
from .core import backup, restore
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
        # 设置日志记录器
        logger = setup_logger(config["settings"]["log_dir"], config["settings"]["name"])
        logger.info("开始执行备份任务")

        backup(config, logger)

        if config["settings"].get("git_auto_commit"):
            msg = f"Backup by confmirror: {config['settings']['name']}"
            git_auto_commit_and_push(
                repo_path=Path.cwd(),
                message=msg,
                auto_push=config["settings"].get("git_auto_push", False)
            )
            logger.info("Git 提交完成")

        logger.info("✅ 备份成功完成")
    except Exception as e:
        click.echo(f"❌ 备份失败: {e}", err=True)
        sys.exit(1)

@main.command()
def restore():
    # 恢复
    try:
        config = load_config()
        logger = setup_logger(config["settings"]["log_dir"], config["settings"]["name"])
        logger.info("开始执行恢复任务")
        restore(config, logger)
        logger.info("✅ 恢复成功完成")
    except Exception as e:
        click.echo(f"❌ 恢复失败: {e}", err=True)
        sys.exit(1)