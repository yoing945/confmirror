import functools
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from click import Context, Parameter

from . import __version__
from .backup import execute_backup
from .config import APP_NAME, Config, load_config, resolve_config_path
from .diff import diff_module, diff_paths
from .gitops import git_auto_commit_and_push
from .global_config import (
    GlobalConfigKeys,
    get_global_config_value,
    remove_global_config_value,
    set_global_config_value,
)
from .init import execute_init
from .list import display_modules, execute_list, get_modules_data
from .logger import (
    ColoredFormatter,
    ModuleLog,
    resolve_log_path,
    rotate_log_file,
    setup_logger,
)
from .output import ExitCode, emit_json, suppress_console_log
from .perms import display_perms_info, execute_perms, get_perms_data
from .restore import execute_restore
from .system_install import install_system_entry, uninstall_system_entry

logger = logging.getLogger(__name__)


def _require_config(ctx: Context, task_name: str = "") -> tuple[Config, logging.Logger]:
    """从 Click 上下文加载配置并返回 (config, logger)。

    配置加载失败时输出错误信息并直接 sys.exit(1)。
    """
    conf_ctx = ctx.find_object(ConfMirrorContext)
    config_path = conf_ctx.config_path if conf_ctx else None
    config = load_config(config_path)
    if config is None:
        if conf_ctx and conf_ctx.output_format == "json":
            emit_json({"status": "error", "error": "配置加载失败", "task": task_name})
        else:
            msg = "❌ 配置加载失败"
            if task_name:
                msg += f"，无法执行{task_name}任务"
            click.echo(msg, err=True)
        sys.exit(ExitCode.CONFIG_ERROR)
    return config, _get_logger_from_config(config)


def _with_error_handling(command_name: str):
    """装饰器：统一处理 CLI 命令的异常、JSON 错误输出和退出码。

    消除每个子命令重复的 `try/except → traceback → emit_json → sys.exit` 模板。
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(ctx, *args, **kwargs):
            conf_ctx = ctx.find_object(ConfMirrorContext)
            is_json = conf_ctx.output_format == "json" if conf_ctx else False
            try:
                return func(ctx, *args, **kwargs)
            except SystemExit:
                raise  # 让 sys.exit 直接透传
            except Exception as e:
                logging.getLogger(APP_NAME).error(traceback.format_exc())
                if is_json:
                    emit_json(
                        {"status": "error", "command": command_name, "error": str(e)}
                    )
                sys.exit(ExitCode.PARTIAL_FAILURE)

        return wrapper

    return decorator


def list_available_modules(ctx: Context, param: Parameter, incomplete: str):
    """自动补全模块名称"""
    try:
        # 从上下文中获取配置路径参数
        conf_ctx = ctx.find_object(ConfMirrorContext)
        if conf_ctx:
            config_path = conf_ctx.config_path
        else:
            config_path = None
        config = load_config(config_path)
        if config is not None:
            modules = config.modules
            # 返回匹配不完整输入的模块名称
            return [mod.name for mod in modules if mod.name.startswith(incomplete)]
        return []
    except Exception:
        # 如果配置加载失败，返回空列表
        return []


def _preconfigure_logger(
    config_path: Optional[str], use_file_handler: bool = True
) -> None:
    """在 load_config 之前预读配置中的日志设置，提前配置 logger

    确保 load_config 阶段的错误日志也能写入文件，而不是走 stderr 兜底。
    当 use_file_handler 为 False 时仅配置控制台 handler，避免提前创建日志目录
    （用于 init 命令）。
    """
    log_dir = "./logs"
    log_max_lines = 1000
    config_name = "confmirror"

    path = resolve_config_path(config_path)
    if path.exists():
        try:
            import yaml

            with open(path, encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            if isinstance(raw, dict) and isinstance(raw.get("settings"), dict):
                settings = raw["settings"]
                log_dir = settings.get("log_dir", log_dir)
                log_max_lines = settings.get("log_max_lines", log_max_lines)
                config_name = settings.get("name", path.parent.name)
        except Exception:
            pass  # YAML 损坏或读取失败时回退到默认值

    logger = logging.getLogger(APP_NAME)
    if logger.handlers and use_file_handler:
        return

    # init 命令不创建日志目录，但需要刷新控制台 handler 以确保输出到当前 stderr
    if not use_file_handler:
        for handler in list(logger.handlers):
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                logger.removeHandler(handler)

    logger.setLevel(logging.DEBUG)

    if use_file_handler:
        log_file = resolve_log_path(log_dir, config_name)
        rotate_log_file(log_file, log_max_lines)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console_formatter = ColoredFormatter("[%(levelname)s] %(message)s")
    console.setFormatter(console_formatter)
    logger.addHandler(console)


def _get_logger_from_config(config: Config) -> logging.Logger:
    """根据配置获取日志记录器（此时 logger 已预配置，只需确保参数一致）"""
    log_file = resolve_log_path(config.settings.log_dir, config.settings.name)
    max_lines = config.settings.log_max_lines
    return setup_logger(log_file, max_lines)


class ConfMirrorContext:
    """用于在命令之间传递全局上下文的类"""

    def __init__(
        self,
        config_path=None,
        output_format="human",
        dry_run=False,
        non_interactive=False,
    ):
        self.config_path = config_path
        self.output_format = output_format
        self.dry_run = dry_run
        self.non_interactive = non_interactive


def gen_help_option():
    """创建一个自定义的帮助选项，支持 -h 和 --help"""

    def show_help(ctx, param, value):
        if value and not ctx.resilient_parsing:
            click.echo(ctx.get_help(), color=ctx.color)
            ctx.exit()

    return click.Option(
        ["-h", "--help"],
        is_flag=True,
        expose_value=False,
        callback=show_help,
        help="显示帮助信息",
    )


def gen_version_option():
    """创建一个自定义的版本选项，支持 -v 和 --version"""

    def show_version(ctx, param, value):
        if value and not ctx.resilient_parsing:
            click.echo(f"v{__version__}", color=ctx.color)
            ctx.exit()

    return click.Option(
        ["-v", "--version"],
        is_flag=True,
        expose_value=False,
        callback=show_version,
        help="显示版本信息",
    )


def gen_config_option():
    """创建一个自定义的配置选项，支持 -c 和 --config"""

    def set_config(ctx, param, value):
        if value and not ctx.resilient_parsing:
            ctx.ensure_object(ConfMirrorContext).config_path = value

    return click.Option(
        ["-c", "--config"],
        type=click.Path(exists=True),
        expose_value=False,
        callback=set_config,
        help="指定配置文件路径",
    )


def _get_group_ctx(ctx):
    """获取 Group 级别的 context（用于在子命令选项 callback 中写入全局上下文）。"""
    return ctx.parent if ctx.parent else ctx


def gen_format_option():
    """创建 --format 全局选项"""

    def set_format(ctx, param, value):
        if not ctx.resilient_parsing:
            group_ctx = _get_group_ctx(ctx)
            group_ctx.ensure_object(ConfMirrorContext).output_format = value
            if value == "json":
                from confmirror.output import suppress_console_log

                suppress_console_log()

    return click.Option(
        ["--format"],
        type=click.Choice(["human", "json"]),
        default="human",
        expose_value=False,
        callback=set_format,
        help="输出格式：human（人类可读）或 json（结构化）",
    )


def gen_dry_run_option():
    """创建 --dry-run 全局选项"""

    def set_dry_run(ctx, param, value):
        if not ctx.resilient_parsing:
            _get_group_ctx(ctx).ensure_object(ConfMirrorContext).dry_run = value

    return click.Option(
        ["--dry-run"],
        is_flag=True,
        default=False,
        expose_value=False,
        callback=set_dry_run,
        help="预览操作，不实际执行",
    )


def gen_yes_option():
    """创建 --yes 全局选项（非交互模式）"""

    def set_yes(ctx, param, value):
        if not ctx.resilient_parsing:
            _get_group_ctx(ctx).ensure_object(ConfMirrorContext).non_interactive = value

    return click.Option(
        ["--yes"],
        is_flag=True,
        default=False,
        expose_value=False,
        callback=set_yes,
        help="非交互模式，跳过所有确认提示",
    )


class CustomCommand(click.Command):
    """自定义命令类，支持-h简写显示帮助和全局选项注入"""

    def get_help_option(self, ctx):
        return gen_help_option()

    def get_params(self, ctx):
        rv = super().get_params(ctx)
        # 为所有子命令注入 Agent 友好全局选项
        rv = [gen_format_option(), gen_dry_run_option(), gen_yes_option()] + list(rv)
        return rv


class CustomGroup(click.Group):
    """自定义命令组，支持-h简写显示帮助"""

    def get_help_option(self, ctx):
        return gen_help_option()

    def get_params(self, ctx):
        rv = super().get_params(ctx)
        # 仅在顶层命令添加版本和配置选项
        if ctx.parent is None:
            version_opt = gen_version_option()
            config_opt = gen_config_option()
            rv = [version_opt, config_opt] + list(rv)
        return rv

    def command(self, *args, **kwargs):
        # 子命令使用 CustomCommand 类而非 CustomGroup，避免子命令被当作可分组命令
        kwargs.setdefault("cls", CustomCommand)
        return super().command(*args, **kwargs)

    def group(self, *args, **kwargs):
        # 子分组仍使用 CustomGroup
        kwargs.setdefault("cls", CustomGroup)
        return super().group(*args, **kwargs)


@click.group(cls=CustomGroup)
@click.pass_context
def main(ctx):
    ctx.ensure_object(ConfMirrorContext)

    # 预配置 logger，确保 load_config 及后续所有日志统一输出到文件
    # init 命令会自行创建日志目录，此处仅配置控制台 handler 避免提前创建目录
    conf_ctx = ctx.find_object(ConfMirrorContext)
    _preconfigure_logger(
        conf_ctx.config_path if conf_ctx else None,
        use_file_handler=(ctx.invoked_subcommand != "init"),
    )

    # 注意：suppress_console_log 已在 --format json 选项的 callback 中触发，
    # 不需要在 main() 中重复处理（Click 的 Group callback 在子命令选项 callback 之前执行）


@main.command()
@click.option(
    "-m",
    "--module",
    type=str,
    shell_complete=list_available_modules,
    help="指定要备份的模块名称",
)
@click.option("-f", "--force", is_flag=True, help="强制覆盖备份模式")
@click.argument("target_paths", nargs=-1, type=str)
@click.pass_context
@_with_error_handling("backup")
def backup(ctx, module, force, target_paths):
    """执行备份操作"""
    conf_ctx = ctx.find_object(ConfMirrorContext)
    is_json = conf_ctx.output_format == "json" if conf_ctx else False
    dry_run = conf_ctx.dry_run if conf_ctx else False
    non_interactive = conf_ctx.non_interactive if conf_ctx else False

    config, logger = _require_config(ctx, task_name="备份")
    log = ModuleLog("cli", logger)
    settings = config.settings
    name = settings.name
    backup_root = settings.backup_root
    config_path = conf_ctx.config_path if conf_ctx else None

    if dry_run:
        if not is_json:
            log.info("[DRY-RUN] 预览模式，不实际执行备份")

    if force:
        log.warn("已启用强制覆盖备份模式")

    # 根据参数决定备份方式
    if module:
        execute_backup(config, target_module_name=module, force=force, dry_run=dry_run)
    elif target_paths:
        log_str = target_paths[0]
        if len(target_paths) > 1:
            log_str += f", ..."
        log.info(f"开始执行路径备份: {log_str}")
        for target_path in target_paths:
            execute_backup(
                config, target_path=target_path, force=force, dry_run=dry_run
            )
    else:
        if not non_interactive:
            confirm = click.prompt("正在进行全量备份, y/n?", type=str)
            confirm = confirm.strip().lower()
            if confirm != "y" and confirm != "yes":
                if is_json:
                    emit_json(
                        {
                            "status": "cancelled",
                            "command": "backup",
                            "reason": "用户取消",
                        }
                    )
                else:
                    click.echo("全量备份已取消")
                return
        log.info("开始执行全量备份")
        execute_backup(config, force=force, dry_run=dry_run)

    if not dry_run and settings.git_auto_commit:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{timestamp}] 自动同步: {name}"
        success, _ = git_auto_commit_and_push(
            repo_path=Path(config_path).parent if config_path else Path.cwd(),
            message=msg,
            auto_push=settings.git_auto_push,
        )
        if success:
            log.ok("Git 提交完成")

    if is_json:
        emit_json(
            {
                "status": "success",
                "command": "backup",
                "module": module,
                "dry_run": dry_run,
                "paths": list(target_paths) if target_paths else [],
            }
        )
    else:
        if dry_run:
            log.ok("[DRY-RUN] 备份预览完成")
        else:
            log.ok("备份完成")


@main.command()
@click.option(
    "-m",
    "--module",
    type=str,
    shell_complete=list_available_modules,
    help="指定要还原的模块名称",
)
@click.option("-f", "--force", is_flag=True, help="强制覆盖还原模式（默认为差异还原）")
@click.argument("target_paths", nargs=-1, type=str)
@click.pass_context
@_with_error_handling("restore")
def restore(ctx, module, force, target_paths):
    """执行还原操作"""
    conf_ctx = ctx.find_object(ConfMirrorContext)
    is_json = conf_ctx.output_format == "json" if conf_ctx else False
    dry_run = conf_ctx.dry_run if conf_ctx else False
    non_interactive = conf_ctx.non_interactive if conf_ctx else False

    config, logger = _require_config(ctx, task_name="还原")
    log = ModuleLog("cli", logger)

    if dry_run and not is_json:
        log.info("[DRY-RUN] 预览模式，不实际执行还原")

    if force:
        log.warn("已启用强制覆盖还原模式")

    # 根据参数决定还原方式
    if module:
        execute_restore(config, target_module_name=module, force=force, dry_run=dry_run)
    elif target_paths:
        log_str = target_paths[0]
        if len(target_paths) > 1:
            log_str += f", ..."
        log.info(f"开始执行路径还原: {log_str}")
        for target_path in target_paths:
            execute_restore(
                config, target_path=target_path, force=force, dry_run=dry_run
            )
    else:
        # 全量还原需要二次确认
        if not non_interactive:
            confirm = click.prompt(
                "⚠️  正在进行全量还原操作，这会覆盖所有备份关联的系统配置文件。\n输入 'YES' 确认继续",
                type=str,
            )
            if confirm != "YES":
                if is_json:
                    emit_json(
                        {
                            "status": "cancelled",
                            "command": "restore",
                            "reason": "用户取消",
                        }
                    )
                else:
                    click.echo("全量还原已取消")
                return
        log.info("开始执行全量还原")
        execute_restore(config, force=force, dry_run=dry_run)

    if is_json:
        emit_json(
            {
                "status": "success",
                "command": "restore",
                "module": module,
                "dry_run": dry_run,
                "paths": list(target_paths) if target_paths else [],
            }
        )
    else:
        if dry_run:
            log.ok("[DRY-RUN] 还原预览完成")
        else:
            log.ok("还原完成")


@main.command()
@click.option(
    "-m",
    "--module",
    type=str,
    shell_complete=list_available_modules,
    help="查看指定模块的权限信息",
)
@click.argument("target_paths", nargs=-1, type=str)
@click.pass_context
@_with_error_handling("perms")
def perms(ctx, module, target_paths):
    """查看备份文件的权限信息"""
    conf_ctx = ctx.find_object(ConfMirrorContext)
    is_json = conf_ctx.output_format == "json" if conf_ctx else False

    config, logger = _require_config(ctx, task_name="权限查看")

    # 根据参数决定权限查看方式
    entries = []
    if module:
        entries = get_perms_data(config, target_module_name=module)
    elif target_paths:
        for target_path in target_paths:
            entries.extend(get_perms_data(config, target_path=target_path))
    else:
        if is_json:
            emit_json(
                {"status": "error", "command": "perms", "error": "需要指定模块或路径"}
            )
        else:
            click.echo("⚠️  需要指定模块或路径。")
        sys.exit(ExitCode.CONFIG_ERROR)

    if is_json:
        emit_json(
            {
                "status": "success",
                "command": "perms",
                "module": module,
                "paths": list(target_paths) if target_paths else [],
                "data": entries,
            }
        )
    else:
        display_perms_info(entries)


@main.command()
@click.option(
    "-m",
    "--module",
    type=str,
    shell_complete=list_available_modules,
    help="列出指定模块的信息",
)
@click.option("-d", "--detail", is_flag=True, help="输出模块的详细信息")
@click.pass_context
@_with_error_handling("ls")
def ls(ctx, module, detail):
    """列出所有可用模块"""
    conf_ctx = ctx.find_object(ConfMirrorContext)
    is_json = conf_ctx.output_format == "json" if conf_ctx else False

    config, logger = _require_config(ctx, task_name="模块列出")
    entries = get_modules_data(config, module_name=module, detail=detail)

    if entries is None:
        if is_json:
            emit_json(
                {"status": "error", "command": "ls", "error": f"未找到模块: {module}"}
            )
        else:
            click.echo(f"❌ 未找到模块: {module}", err=True)
        sys.exit(ExitCode.CONFIG_ERROR)

    if is_json:
        emit_json(
            {
                "status": "success",
                "command": "ls",
                "module": module,
                "detail": detail,
                "data": entries,
            }
        )
    else:
        display_modules(entries, detail=detail)


@main.command()
@click.option(
    "-m",
    "--module",
    type=str,
    shell_complete=list_available_modules,
    help="对比整个模块的所有文件",
)
@click.option("-d", "--detail", is_flag=True, help="输出详细的文件内容差异")
@click.argument("target_paths", nargs=-1, type=click.Path(exists=False))
@click.pass_context
@_with_error_handling("diff")
def diff(ctx, module, detail, target_paths):
    """对比源文件与备份文件的差异"""
    conf_ctx = ctx.find_object(ConfMirrorContext)
    is_json = conf_ctx.output_format == "json" if conf_ctx else False

    config, logger = _require_config(ctx, task_name="差异对比")

    if module:
        diff_module(
            config,
            module,
            detail,
            output_format=conf_ctx.output_format if conf_ctx else "human",
        )
    elif target_paths:
        diff_paths(
            config,
            target_paths,
            detail,
            output_format=conf_ctx.output_format if conf_ctx else "human",
        )
    else:
        if is_json:
            emit_json(
                {"status": "error", "command": "diff", "error": "需要指定模块或路径"}
            )
        else:
            click.echo("⚠️  需要指定模块或路径。")
        sys.exit(ExitCode.CONFIG_ERROR)

    if is_json:
        # diff_module / diff_paths 内部已处理 JSON 输出
        pass


@main.command()
@click.option("-m", "--message", type=str, help="自定义提交信息")
@click.pass_context
def sync(ctx, message):
    """手动触发快速同步到远端仓库"""
    conf_ctx = ctx.find_object(ConfMirrorContext)
    is_json = conf_ctx.output_format == "json" if conf_ctx else False
    dry_run = conf_ctx.dry_run if conf_ctx else False

    try:
        config, logger = _require_config(ctx, task_name="同步")
        log = ModuleLog("cli", logger)
        settings = config.settings
        name = settings.name
        backup_root = settings.backup_root

        if dry_run and not is_json:
            log.info("[DRY-RUN] 预览模式，不实际执行同步")

        if message:
            msg = message
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg = f"[{timestamp}] 手动同步: {name}"

        if dry_run:
            if is_json:
                emit_json(
                    {
                        "status": "success",
                        "command": "sync",
                        "dry_run": True,
                        "message": msg,
                        "repo_path": str(backup_root),
                    }
                )
            else:
                log.ok(f"[DRY-RUN] 将执行: git commit -m '{msg}' && git push")
            return

        success, error_msg = git_auto_commit_and_push(
            repo_path=backup_root,
            message=msg,
            auto_push=True,
        )

        if success:
            if is_json:
                emit_json({"status": "success", "command": "sync", "message": msg})
            else:
                log.ok("手动同步完成")
        else:
            if is_json:
                emit_json({"status": "error", "command": "sync", "error": error_msg})
            else:
                log.error(f"手动同步失败: {error_msg}")
            sys.exit(ExitCode.PARTIAL_FAILURE)

    except Exception as e:
        logger = logging.getLogger(APP_NAME)
        logger.error(traceback.format_exc())
        if is_json:
            emit_json({"status": "error", "command": "sync", "error": str(e)})
        sys.exit(ExitCode.CONFIG_ERROR)


@main.group()
def global_config_path():
    """管理全局配置路径"""
    pass


_log_global = ModuleLog("cli", logging.getLogger(APP_NAME))


@global_config_path.command()
@click.argument("path", type=click.Path(exists=True))
def set(path):
    """设置全局配置文件路径"""
    success = set_global_config_value(GlobalConfigKeys.DEFAULT_CONFIG_PATH, path)
    if success:
        _log_global.ok(f"全局配置路径已设置为 {path}")
    else:
        _log_global.error("设置全局配置路径失败")


@global_config_path.command()
def remove():
    """移除全局配置文件路径"""
    success = remove_global_config_value(GlobalConfigKeys.DEFAULT_CONFIG_PATH)
    if success:
        _log_global.ok("全局配置路径已移除")
    else:
        _log_global.error("移除全局配置路径失败")


@global_config_path.command()
def show():
    """显示当前全局配置文件路径"""
    path = get_global_config_value(GlobalConfigKeys.DEFAULT_CONFIG_PATH)
    if path:
        click.echo(path)
    else:
        click.echo("未设置全局配置路径")


@main.command()
@click.option(
    "--source-path",
    type=click.Path(exists=True),
    help="confmirror 可执行文件的完整路径（通常自动检测）",
)
@click.pass_context
@_with_error_handling("install-system")
def install_system(ctx, source_path):
    """创建系统级入口，使 sudo confmirror 可用"""
    log = ModuleLog("cli", logging.getLogger(APP_NAME))

    try:
        install_system_entry(Path(source_path) if source_path else None)
        log.ok("系统级入口已创建：/usr/local/bin/confmirror")
        log.info("现在可以直接使用：sudo confmirror restore ...")
    except PermissionError as e:
        click.echo(f"权限不足: {e}", err=True)
        sys.exit(ExitCode.PERMISSION_ERROR)
    except RuntimeError as e:
        click.echo(f"安装失败: {e}", err=True)
        sys.exit(ExitCode.PARTIAL_FAILURE)


@main.command()
@click.pass_context
@_with_error_handling("uninstall-system")
def uninstall_system(ctx):
    """移除系统级入口"""
    log = ModuleLog("cli", logging.getLogger(APP_NAME))

    try:
        removed = uninstall_system_entry()
        if removed:
            log.ok("系统级入口已移除：/usr/local/bin/confmirror")
        else:
            log.info("系统级入口不存在，无需卸载")
    except PermissionError as e:
        click.echo(f"权限不足: {e}", err=True)
        sys.exit(ExitCode.PERMISSION_ERROR)
    except RuntimeError as e:
        click.echo(f"卸载失败: {e}", err=True)
        sys.exit(ExitCode.PARTIAL_FAILURE)


@main.command()
@click.argument("path", required=False, type=click.Path(path_type=Path))
@click.pass_context
@_with_error_handling("init")
def init(ctx, path):
    """初始化 ConfMirror 项目结构"""
    conf_ctx = ctx.find_object(ConfMirrorContext)
    output_format = conf_ctx.output_format if conf_ctx else "human"
    dry_run = conf_ctx.dry_run if conf_ctx else False

    target = path if path else Path.cwd()
    exit_code = execute_init(target, dry_run=dry_run, output_format=output_format)
    if exit_code != ExitCode.SUCCESS:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
