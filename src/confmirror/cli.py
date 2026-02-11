import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path

import click
from click import Context, Parameter

from .config import APP_NAME, ConfigKeys, load_config
from .backup import execute_backup
from .restore import execute_restore
from .perms import execute_perms
from .list import execute_list
from .diff import diff_paths, diff_module
from .gitops import git_auto_commit_and_push
from .logger import setup_logger
from . import __version__


def list_available_modules(ctx: Context, param: Parameter, incomplete: str):
    """自动补全模块名称"""
    try:
        config = load_config()
        if config and ConfigKeys.SECTION_MODULES in config:
            modules = config[ConfigKeys.SECTION_MODULES]
            # 返回匹配不完整输入的模块名称
            return [mod[ConfigKeys.NAME] for mod in modules if mod[ConfigKeys.NAME].startswith(incomplete)]
        return []
    except:
        # 如果配置加载失败，返回空列表
        return []


def gen_help_option():
    """创建一个自定义的帮助选项，支持 -h 和 --help"""
    def show_help(ctx, param, value):
        if value and not ctx.resilient_parsing:
            click.echo(ctx.get_help(), color=ctx.color)
            ctx.exit()
    
    return click.Option(
        ['-h', '--help'],
        is_flag=True,
        expose_value=False,
        callback=show_help,
        help="显示帮助信息"
    )

def gen_version_option():
    """创建一个自定义的版本选项，支持 -v 和 --version"""
    def show_version(ctx, param, value):
        if value and not ctx.resilient_parsing:
            click.echo(f'v{__version__}', color=ctx.color)
            ctx.exit()
    
    return click.Option(
        ['-v', '--version'],
        is_flag=True,
        expose_value=False,
        callback=show_version,
        help="显示版本信息"
    )

class CustomCommand(click.Command):
    """自定义命令类，支持-h简写显示帮助"""
    def get_help_option(self, ctx):
        return gen_help_option()

class CustomGroup(click.Group):
    """自定义命令组，支持-h简写显示帮助"""
    def get_help_option(self, ctx):
        return gen_help_option()


    def get_params(self, ctx):
        # 添加版本选项到顶级命令
        rv = super().get_params(ctx)
        # 仅在顶层命令添加版本选项，不在子命令中添加
        if ctx.parent is None:
            version_opt = gen_version_option()
            rv = [version_opt] + list(rv)
        return rv

    def command(self, *args, **kwargs):
        # 子命令使用 CustomCommand 类而非 CustomGroup，避免子命令被当作可分组命令
        kwargs.setdefault('cls', CustomCommand)
        return super().command(*args, **kwargs)

    def group(self, *args, **kwargs):
        # 子分组仍使用 CustomGroup
        kwargs.setdefault('cls', CustomGroup)
        return super().group(*args, **kwargs)


@click.group(cls=CustomGroup)
def main():
    pass

@main.command()
@click.option('-m', '--module', type=str, shell_complete=list_available_modules, help='指定要备份的模块名称')
@click.option('-f', '--force', is_flag=True, help='强制覆盖备份模式')
@click.argument('target_paths', nargs=-1, type=click.Path(exists=False))
def backup(module, force, target_paths):
    """执行备份操作"""
    try:
        # 加载配置文件
        config = load_config()

        # 检查配置是否加载成功
        if not config:
            click.echo("❌ 配置加载失败，无法执行备份任务", err=True)
            sys.exit(1)

        settings:dict = config[ConfigKeys.SECTION_SETTINGS]
        name = settings[ConfigKeys.NAME]

        logger = setup_logger(config)
        backup_root = Path(settings[ConfigKeys.BACKUP_ROOT])
        logger.info(f"开始执行备份，镜像目录: {backup_root}")

        if force:
            logger.info("⚠️  已启用强制覆盖备份模式")

        # 根据参数决定备份方式
        if module:
            execute_backup(config, logger, target_module_name=module, force=force)
        elif target_paths:
            # 如果target_paths长度>1，日志只输出前1个，后续用...代替
            log_str = target_paths[0]
            if len(target_paths) > 1:
                log_str += f", ..."
            logger.info(f"开始执行路径备份: {log_str}")
            # 指定路径备份 - 支持多个路径
            for target_path in target_paths:
                execute_backup(config, logger, target_path=target_path, force=force)
        else:
            confirm = click.prompt("正在进行全量备份, y/n?", type=str)
            confirm = confirm.strip().lower()
            if confirm != 'y' and confirm != 'yes':
                click.echo("全量备份已取消")
                return
            # 全量备份
            logger.info("开始执行全量备份")
            execute_backup(config, logger, force=force)

        if settings.get(ConfigKeys.GIT_AUTO_COMMIT):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg = f"[{timestamp}] 自动同步: {name}"
            success =git_auto_commit_and_push(
                repo_path=Path.cwd(),
                message=msg,
                auto_push=settings.get(ConfigKeys.GIT_AUTO_PUSH, False)
            )
            if success:
                logger.info("Git 提交完成")

        logger.info("✅ 备份完成")
    except Exception as e:
        logger = logging.getLogger(APP_NAME)
        logger.error(traceback.format_exc())
        sys.exit(1)

@main.command()
@click.option('-m', '--module', type=str, shell_complete=list_available_modules, help='指定要还原的模块名称')
@click.option('-f', '--force', is_flag=True, help='强制覆盖还原模式（默认为差异还原）')
@click.argument('target_paths', nargs=-1, type=click.Path(exists=False))
def restore(module, force, target_paths):
    """执行还原操作"""
    try:
        config = load_config()

        # 检查配置是否加载成功
        if not config:
            click.echo("❌ 配置加载失败，无法执行还原任务", err=True)
            sys.exit(1)

        logger = setup_logger(config)

        if force:
            logger.info("⚠️  已启用强制覆盖还原模式")

        # 根据参数决定还原方式
        if module:
            execute_restore(config, logger, target_module_name=module, force=force)
        elif target_paths:
            log_str = target_paths[0]
            if len(target_paths) > 1:
                log_str += f", ..."
            logger.info(f"开始执行路径还原: {log_str}")
            for target_path in target_paths:
                execute_restore(config, logger, target_path=target_path, force=force)
        else:
            # 全量还原需要二次确认
            confirm = click.prompt("⚠️  正在进行全量还原操作，这会覆盖所有备份关联的系统配置文件。\n输入 'YES' 确认继续", type=str)
            if confirm != 'YES':
                click.echo("全量还原已取消")
                return
            logger.info("开始执行全量还原")
            execute_restore(config, logger, force=force)

        logger.info("✅ 还原完成")
    except Exception as e:
        logger = logging.getLogger(APP_NAME)
        logger.error(traceback.format_exc())
        sys.exit(1)

@main.command()
@click.option('-m', '--module', type=str, shell_complete=list_available_modules, help='查看指定模块的权限信息')
@click.argument('target_paths', nargs=-1, type=click.Path(exists=False))
def perms(module, target_paths):
    """查看备份文件的权限信息"""
    try:
        config = load_config()

        # 检查配置是否加载成功
        if not config:
            click.echo("❌ 配置加载失败，无法查看权限信息", err=True)
            sys.exit(1)

        logger = setup_logger(config)

        # 根据参数决定权限查看方式
        if module:
            # 分模块查看权限
            execute_perms(config, logger, target_module_name=module)
        elif target_paths:
            # 指定路径查看权限 - 支持多个路径
            for target_path in target_paths:
                execute_perms(config, logger, target_path=target_path)
        else:
            # 没有参数，列出所有模块
            click.echo("⚠️  需要指定模块或路径。")

    except Exception as e:
        logger = logging.getLogger(APP_NAME)
        logger.error(traceback.format_exc())
        click.echo(f"❌ 查看权限信息失败: {e}", err=True)
        sys.exit(1)

@main.command()
@click.option('-m', '--module', type=str, shell_complete=list_available_modules, help='列出指定模块的信息')
@click.option('-d', '--detail', is_flag=True, help='输出模块的详细信息')
def ls(module, detail):
    """列出所有可用模块"""
    try:
        config = load_config()

        # 检查配置是否加载成功
        if not config:
            click.echo("❌ 配置加载失败，无法列出模块", err=True)
            sys.exit(1)

        logger = setup_logger(config)

        # 列出所有模块或指定模块
        execute_list(config, module_name=module, detail=detail)

    except Exception as e:
        logger = logging.getLogger(APP_NAME)
        logger.error(traceback.format_exc())
        click.echo(f"❌ 列出模块失败: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('-m', '--module', type=str, shell_complete=list_available_modules, help='对比整个模块的所有文件')
@click.option('-d', '--detail', is_flag=True, help='输出详细的文件内容差异')
@click.argument('target_paths', nargs=-1, type=click.Path(exists=False))
def diff(module, detail, target_paths):
    """对比源文件与备份文件的差异"""
    try:
        config = load_config()

        if not config:
            click.echo("❌ 配置加载失败", err=True)
            sys.exit(1)

        logger = setup_logger(config)

        # 根据参数决定差异对比方式
        if module:
            # 对比整个模块
            diff_module(config, module, detail)
        elif target_paths:
            diff_paths(config, target_paths, detail)
        else:
            click.echo("⚠️  需要指定模块或路径。")

    except Exception as e:
        logger = logging.getLogger(APP_NAME)
        logger.error(traceback.format_exc())
        click.echo(f"❌ 差异对比失败: {e}", err=True)
        sys.exit(1)

@main.command()
@click.option('-m', '--message', type=str, help='自定义提交信息')
def sync(message):
    """手动触发快速同步到远端仓库"""
    try:
        config = load_config()

        if not config:
            click.echo("❌ 配置加载失败，无法执行同步任务", err=True)
            sys.exit(1)

        settings: dict = config[ConfigKeys.SECTION_SETTINGS]
        name = settings[ConfigKeys.NAME]

        logger = setup_logger(config)
        logger.info("开始执行手动同步到远端仓库")

        # 执行 Git 提交和推送
        if message:
            msg = message
        else:
            # 使用默认消息格式
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg = f"[{timestamp}] 手动同步: {name}"
        success = git_auto_commit_and_push(
            repo_path=Path.cwd(),
            message=msg,
            auto_push=True  # 手动同步总是推送
        )

        if success:
            logger.info("✅ 手动同步完成")
        else:
            logger.error("❌ 手动同步失败")
            sys.exit(1)

    except Exception as e:
        logger = logging.getLogger(APP_NAME)
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()