"""处理列出模块的功能"""

from typing import Dict

import click

from .config import ConfigKeys


def execute_list(config: Dict, module_name=None, detail=False):
    """
    列出所有可用模块

    Args:
        config: 配置字典
        logger: 日志记录器
        module_name: 指定要列出的模块名称，如果为None则列出所有模块
        detail: 是否输出详细信息
    """
    modules = config.get(ConfigKeys.SECTION_MODULES, [])

    if not modules:
        click.echo("⚠️  配置中没有定义任何模块")
        return

    if module_name:
        # 查找指定模块
        target_module = None
        for module in modules:
            if module.get(ConfigKeys.MOD_NAME) == module_name:
                target_module = module
                break

        if not target_module:
            click.echo(f"❌ 未找到模块: {module_name}")
            return

        if detail:
            click.echo("-" * 50)
            _print_module_details(target_module)
        else:
            click.echo(f"模块: {module_name}")
    else:
        # 列出所有模块
        click.echo(f"共 {len(modules)} 个模块:")
        if detail:
            click.echo("-" * 50)
            for i, module in enumerate(modules, 1):
                _print_module_details(module)
        else:
            for i, module in enumerate(modules, 1):
                module_name = module.get(ConfigKeys.MOD_NAME, f"未知模块_{i}")
                click.echo(f"  - {module_name}")


def _print_module_details(module):
    """打印模块详细信息"""
    module_name = module.get(ConfigKeys.MOD_NAME, f"未知模块")
    click.echo(f"模块: {module_name}")

    # 检查是否有脚本类型的模块
    script_path = module.get(ConfigKeys.MOD_SCRIPT)
    if script_path:
        click.echo(f"  类型: 脚本模块")
        click.echo(f"  脚本路径: {script_path}")
    else:
        # 输出路径相关配置
        parent_path = module.get(ConfigKeys.MOD_PARENT_PATH)
        if parent_path:
            click.echo(f"  父目录: {parent_path}")

        include_paths = module.get(ConfigKeys.MOD_INCLUDE_PATHS, [])
        if include_paths:
            click.echo(f"  包含路径: {include_paths}")

        exclude_paths = module.get(ConfigKeys.MOD_EXCLUDE_PATHS, [])
        if exclude_paths:
            click.echo(f"  排除路径: {exclude_paths}")

    click.echo("-" * 50)
