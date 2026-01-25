#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git配置恢复工具 - 恢复脚本
功能: 从Git备份仓库恢复系统配置文件，支持模块化恢复和脚本化恢复
注意: 此脚本需要sudo权限运行，因为需要设置文件权限和用户组
"""

import os
import sys
import json
import shutil
import hashlib
import subprocess
import argparse
import pwd
import grp
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
import logging
from dataclasses import dataclass
import re


@dataclass
class RestoreConfig:
    """恢复配置类"""
    backup_config_file: str
    git_backup_root: str
    git_backup_script_root: str
    log_file: str
    log_keep_lines: int = 100
    git_branch: str = "main"
    verbose: bool = True
    enable_file_checksum: bool = False
    force_overwrite: bool = False


class RestoreLogger:
    """统一的日志管理类"""
    
    def __init__(self, log_file: str, keep_lines: int = 100, verbose: bool = True):
        self.log_file = Path(log_file)
        self.keep_lines = keep_lines
        self.verbose = verbose
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志配置"""
        # 确保日志目录存在
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 配置日志格式
        logging.basicConfig(
            level=logging.INFO if self.verbose else logging.WARNING,
            format='[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout) if self.verbose else logging.NullHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _rotate_log(self):
        """日志轮转"""
        if not self.log_file.exists():
            return
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if len(lines) > self.keep_lines:
                with open(self.log_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines[-self.keep_lines:])
        except Exception as e:
            self.logger.warning(f"日志轮转失败: {e}")
    
    def info(self, message: str):
        """信息日志"""
        self.logger.info(message)
        self._rotate_log()
    
    def warning(self, message: str):
        """警告日志"""
        self.logger.warning(message)
        self._rotate_log()
    
    def error(self, message: str):
        """错误日志"""
        self.logger.error(message)
        self._rotate_log()


class RestoreManager:
    """恢复管理器"""
    
    def __init__(self, config: RestoreConfig):
        self.config = config
        self.logger = RestoreLogger(
            config.log_file, 
            config.log_keep_lines, 
            config.verbose
        )
        
        # 确保备份根目录存在
        backup_root = Path(config.git_backup_root)
        if not backup_root.exists():
            self.logger.error(f"备份根目录不存在: {backup_root}")
            raise FileNotFoundError(f"备份根目录不存在: {backup_root}")
    
    def _get_user_id(self, username: str) -> int:
        """根据用户名获取UID"""
        try:
            return pwd.getpwnam(username).pw_uid
        except KeyError:
            self.logger.warning(f"用户不存在: {username}")
            return 0
    
    def _get_group_id(self, groupname: str) -> int:
        """根据组名获取GID"""
        try:
            return grp.getgrnam(groupname).gr_gid
        except KeyError:
            self.logger.warning(f"用户组不存在: {groupname}")
            return 0
    
    def _calculate_checksum(self, file_path: str) -> str:
        """计算文件校验和"""
        if not self.config.enable_file_checksum:
            return ""
        
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            self.logger.warning(f"计算文件校验和失败 {file_path}: {e}")
            return ""
    
    def _restore_file_permissions(self, file_path: str, metadata: Dict[str, Any]) -> bool:
        """恢复文件权限和所有者"""
        try:
            # 设置权限
            mode = metadata.get('mode', '644')
            if isinstance(mode, str) and mode.startswith('0'):
                mode = mode[1:]  # 移除开头的0
            
            try:
                os.chmod(file_path, int(mode, 8))
            except ValueError:
                self.logger.warning(f"无效的权限模式: {mode}")
                os.chmod(file_path, 0o644)
            
            # 设置所有者
            uid = metadata.get('uid', 0)
            gid = metadata.get('gid', 0)
            
            try:
                os.chown(file_path, int(uid), int(gid))
            except (ValueError, PermissionError) as e:
                self.logger.warning(f"设置文件所有者失败 {file_path}: {e}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"恢复文件权限失败 {file_path}: {e}")
            return False
    
    def _restore_single_file(self, original_path: str) -> bool:
        """恢复单个文件"""
        original_file = Path(original_path)
        
        # 构造备份路径
        relative_path = original_path.lstrip('/')
        backup_file = Path(self.config.git_backup_root) / relative_path
        meta_file = backup_file.with_suffix(backup_file.suffix + '.meta')
        
        # 检查备份文件和元数据是否存在
        if not backup_file.exists():
            self.logger.warning(f"[恢复跳过] 备份文件不存在: {backup_file}")
            return False
        
        if not meta_file.exists():
            self.logger.warning(f"[恢复跳过] 元数据文件不存在: {meta_file}")
            return False
        
        try:
            # 读取元数据
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            file_type = metadata.get('type', 'unknown')
            if file_type != 'file':
                self.logger.warning(f"[类型不匹配] 预期文件类型为file，实际为{file_type}: {original_path}")
                return False
            
            # 检查校验和（如果启用）
            if self.config.enable_file_checksum:
                backup_checksum = metadata.get('checksum', '')
                if backup_checksum:
                    current_checksum = self._calculate_checksum(str(backup_file))
                    if current_checksum != backup_checksum:
                        self.logger.warning(f"[校验和验证失败] 备份文件可能损坏: {backup_file}")
                        # 继续恢复，但记录警告
            
            # 确保目标目录存在
            original_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 检查是否需要覆盖
            if original_file.exists() and not self.config.force_overwrite:
                self.logger.warning(f"[恢复跳过] 目标文件已存在，使用--force强制覆盖: {original_path}")
                return False
            
            # 复制文件
            shutil.copy2(backup_file, original_file)
            
            # 恢复权限和所有者
            if not self._restore_file_permissions(str(original_file), metadata):
                self.logger.warning(f"权限恢复失败，但文件已复制: {original_path}")
            
            self.logger.info(
                f"[文件恢复成功] {original_path} "
                f"(权限:{metadata.get('mode','unknown')} "
                f"用户:{metadata.get('uid','unknown')}:{metadata.get('gid','unknown')})"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"[文件恢复失败] {original_path}: {e}")
            return False
    
    def _restore_directory(self, original_path: str) -> bool:
        """恢复目录"""
        original_dir = Path(original_path)
        
        # 构造备份路径
        relative_path = original_path.lstrip('/')
        backup_dir = Path(self.config.git_backup_root) / relative_path
        meta_file = backup_dir.with_suffix(backup_dir.suffix + '.meta')
        
        # 检查备份目录和元数据是否存在
        if not backup_dir.exists():
            self.logger.warning(f"[恢复跳过] 备份目录不存在: {backup_dir}")
            return False
        
        if not meta_file.exists():
            self.logger.warning(f"[恢复跳过] 元数据文件不存在: {meta_file}")
            return False
        
        try:
            # 读取元数据
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            dir_type = metadata.get('type', 'unknown')
            if dir_type != 'dir':
                self.logger.warning(f"[类型不匹配] 预期目录类型为dir，实际为{dir_type}: {original_path}")
                return False
            
            # 确保目标目录存在
            original_dir.mkdir(parents=True, exist_ok=True)
            
            # 同步目录内容（排除元数据文件）
            success = True
            for item in backup_dir.rglob('*'):
                if item.name.endswith('.meta'):
                    continue
                
                # 计算相对路径
                relative_item_path = item.relative_to(backup_dir)
                original_item_path = original_dir / relative_item_path
                
                if item.is_file():
                    if not self._restore_single_file(str(original_item_path)):
                        success = False
                elif item.is_dir():
                    original_item_path.mkdir(parents=True, exist_ok=True)
            
            # 恢复目录权限和所有者
            if not self._restore_file_permissions(str(original_dir), metadata):
                self.logger.warning(f"目录权限恢复失败: {original_path}")
            
            if success:
                self.logger.info(f"[目录恢复成功] {original_path}")
            else:
                self.logger.warning(f"[目录恢复部分失败] {original_path}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"[目录恢复失败] {original_path}: {e}")
            return False
    
    def _execute_script_restore(self, script_path: str, module_name: str) -> bool:
        """执行脚本恢复"""
        script_full_path = Path(self.config.git_backup_script_root) / script_path
        
        if not script_full_path.exists():
            self.logger.error(f"[脚本恢复失败] 模块{module_name} → 指定脚本不存在 {script_full_path}")
            return False
        
        try:
            # 确保脚本可执行
            os.chmod(script_full_path, 0o755)
            
            self.logger.info(f"[脚本恢复执行] 模块{module_name} → 运行脚本 {script_full_path}")
            
            # 执行脚本，传入restore参数
            result = subprocess.run(
                [str(script_full_path), 'restore'],
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                self.logger.info(f"[脚本恢复成功] 模块{module_name} → 脚本执行完成")
                if result.stdout.strip():
                    self.logger.info(f"脚本输出: {result.stdout.strip()}")
                return True
            else:
                self.logger.error(f"[脚本恢复失败] 模块{module_name} → 脚本执行返回非0状态码")
                if result.stderr.strip():
                    self.logger.error(f"错误信息: {result.stderr.strip()}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"[脚本恢复失败] 模块{module_name} → 脚本执行超时")
            return False
        except Exception as e:
            self.logger.error(f"[脚本恢复失败] 模块{module_name} → 执行异常: {e}")
            return False
    
    def load_config(self) -> List[Dict[str, Any]]:
        """加载恢复配置文件"""
        config_file = Path(self.config.backup_config_file)
        
        if not config_file.exists():
            self.logger.warning(f"配置文件不存在: {config_file}")
            return []
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 简单的JSON-like解析（兼容原bash脚本的格式）
            content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)  # 移除 // 注释
            content = re.sub(r'#.*$', '', content, flags=re.MULTILINE)    # 移除 # 注释
            content = re.sub(r'(\w+)\s*:', r'"\1":', content)            # 键名加引号
            
            # 修复单引号问题
            content = content.replace("'", '"')
            
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            self.logger.error(f"配置文件解析失败: {e}")
            return []
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            return []
    
    def restore_module(self, module_config: Dict[str, Any]) -> bool:
        """恢复单个模块"""
        module_name = module_config.get('mod', '')
        if not module_name:
            self.logger.warning("无效配置块，模块名为空")
            return False
        
        self.logger.info(f"开始恢复模块 → {module_name}")
        
        script_path = module_config.get('script-path', '')
        
        # 优先执行脚本恢复
        if script_path:
            return self._execute_script_restore(script_path, module_name)
        
        # 否则执行路径恢复
        paths = module_config.get('paths', [])
        parent_path = module_config.get('parent-path', '')
        
        if not paths:
            self.logger.warning(f"模块{module_name} 无script-path且paths为空")
            return False
        
        success = True
        for path in paths:
            if not path.strip():
                continue
            
            full_path = path
            if parent_path:
                full_path = parent_path + path
            
            # 检查备份是否存在
            relative_path = full_path.lstrip('/')
            backup_path = Path(self.config.git_backup_root) / relative_path
            
            if not backup_path.exists():
                self.logger.warning(f"[恢复跳过] 备份不存在: {full_path}")
                continue
            
            # 根据元数据判断是文件还是目录
            meta_file = backup_path.with_suffix(backup_path.suffix + '.meta') if backup_path.is_file() else backup_path.with_suffix('.meta')
            
            if meta_file.exists():
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    item_type = metadata.get('type', 'unknown')
                    
                    if item_type == 'file':
                        if not self._restore_single_file(full_path):
                            success = False
                    elif item_type == 'dir':
                        if not self._restore_directory(full_path):
                            success = False
                    else:
                        self.logger.warning(f"[恢复跳过] 未知类型: {item_type} → {full_path}")
                        
                except Exception as e:
                    self.logger.error(f"读取元数据失败 {meta_file}: {e}")
                    success = False
            else:
                self.logger.warning(f"[恢复跳过] 缺少元数据文件: {meta_file}")
                success = False
        
        return success
    
    def restore_all_modules(self) -> bool:
        """恢复所有模块"""
        modules = self.load_config()
        
        if not modules:
            self.logger.warning("未找到任何配置模块")
            return False
        
        self.logger.info(f"找到 {len(modules)} 个配置模块")
        
        success = True
        for module in modules:
            if not self.restore_module(module):
                success = False
        
        return success
    
    def restore_specific_module(self, module_name: str) -> bool:
        """恢复指定模块"""
        modules = self.load_config()
        
        target_module = None
        for module in modules:
            if module.get('mod') == module_name:
                target_module = module
                break
        
        if not target_module:
            self.logger.error(f"未找到模块名称为 '{module_name}' 的配置项")
            
            # 显示可用模块列表
            available_modules = [m.get('mod', '') for m in modules if m.get('mod')]
            if available_modules:
                self.logger.info("可用模块列表:")
                for mod in available_modules:
                    self.logger.info(f"  - {mod}")
            
            return False
        
        return self.restore_module(target_module)
    
    def restore_specific_path(self, path: str) -> bool:
        """恢复指定路径"""
        # 检查备份是否存在
        relative_path = path.lstrip('/')
        backup_path = Path(self.config.git_backup_root) / relative_path
        
        if not backup_path.exists():
            self.logger.error(f"[恢复失败] 备份不存在: {path}")
            return False
        
        # 检查元数据
        meta_file = backup_path.with_suffix('.meta') if backup_path.is_file() else backup_path.with_suffix('.meta')
        
        if not meta_file.exists():
            self.logger.warning(f"[恢复跳过] 缺少元数据文件: {meta_file}")
            return False
        
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            item_type = metadata.get('type', 'unknown')
            
            if item_type == 'file':
                return self._restore_single_file(path)
            elif item_type == 'dir':
                return self._restore_directory(path)
            else:
                self.logger.error(f"[恢复失败] 未知类型: {item_type} → {path}")
                return False
                
        except Exception as e:
            self.logger.error(f"读取元数据失败 {meta_file}: {e}")
            return False


def load_env_config() -> RestoreConfig:
    """从.env文件加载配置"""
    env_file = Path('.env')
    
    # 默认配置
    config = RestoreConfig(
        backup_config_file='./sync.conf',
        git_backup_root='./backup',
        git_backup_script_root='./backup-script',
        log_file='./log-backup.log'
    )
    
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # 移除引号
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        # 根据键设置配置
                        if key == 'BACKUP_CONFIG_FILE':
                            config.backup_config_file = value
                        elif key == 'GIT_BACKUP_ROOT':
                            config.git_backup_root = value
                        elif key == 'GIT_BACKUP_SCRIPT_ROOT':
                            config.git_backup_script_root = value
                        elif key == 'LOG_FILE':
                            config.log_file = value
                        elif key == 'LOG_KEEP_LINES':
                            config.log_keep_lines = int(value)
                        elif key == 'GIT_BRANCH':
                            config.git_branch = value
                        elif key == 'VERBOSE':
                            config.verbose = value.lower() in ('true', '1', 'yes')
                        elif key == 'ENABLE_FILE_CHECKSUM':
                            config.enable_file_checksum = value.lower() in ('true', '1', 'yes')
                        elif key == 'FORCE_OVERWRITE':
                            config.force_overwrite = value.lower() in ('true', '1', 'yes')
                            
        except Exception as e:
            print(f"加载.env文件失败: {e}")
    
    return config


def check_root_privileges():
    """检查是否具有root权限"""
    if os.geteuid() != 0:
        print("错误: 此脚本需要root权限运行，请使用sudo执行！")
        print("用法: sudo python3 restore.py [command] [args]")
        sys.exit(1)


def main():
    """主函数"""
    # 检查root权限
    check_root_privileges()
    
    parser = argparse.ArgumentParser(
        description='Git配置恢复工具 - 恢复脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s restore /etc/hosts              # 恢复指定文件
  %(prog)s restore-mod 模块名               # 恢复指定模块
  %(prog)s restore-all                     # 恢复所有配置
  %(prog)s --help                          # 显示帮助信息
        """
    )
    
    parser.add_argument(
        'command', 
        choices=['restore', 'restore-mod', 'restore-all'],
        help='执行的命令'
    )
    
    parser.add_argument(
        'target',
        nargs='?',
        help='目标路径或模块名称'
    )
    
    parser.add_argument(
        '--config',
        help='指定配置文件路径'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制覆盖已存在的文件'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='试运行模式，不实际执行恢复'
    )
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_env_config()
    if args.config:
        config.backup_config_file = args.config
    if args.force:
        config.force_overwrite = True
    
    # 创建恢复管理器
    restore_manager = RestoreManager(config)
    
    # 显示开始信息
    restore_manager.logger.info("=" * 50 + " 开始系统配置镜像恢复 " + "=" * 50)
    
    try:
        success = False
        
        if args.command == 'restore':
            if not args.target:
                restore_manager.logger.error("restore 命令需要指定路径")
                parser.print_help()
                return 1
            
            if args.dry_run:
                restore_manager.logger.info(f"[试运行模式] 将要恢复: {args.target}")
                success = True
            else:
                restore_manager.logger.info(f"开始恢复指定路径: {args.target}")
                success = restore_manager.restore_specific_path(args.target)
        
        elif args.command == 'restore-mod':
            if not args.target:
                restore_manager.logger.error("restore-mod 命令需要指定模块名")
                parser.print_help()
                return 1
            
            if args.dry_run:
                restore_manager.logger.info(f"[试运行模式] 将要恢复模块: {args.target}")
                success = True
            else:
                restore_manager.logger.info(f"开始恢复指定模块: {args.target}")
                success = restore_manager.restore_specific_module(args.target)
        
        elif args.command == 'restore-all':
            if args.dry_run:
                restore_manager.logger.info("[试运行模式] 将要恢复所有模块")
                success = True
            else:
                # 危险操作，需要确认
                print("⚠️  警告：即将执行【全量系统配置恢复】！此操作会覆盖当前系统中的配置文件。")
                print("⚠️  所有被备份的文件/目录将从 Git 备份仓库恢复至原始位置。")
                confirm = input("是否继续？(输入 YES 确认): ").strip()
                if confirm != "YES":
                    restore_manager.logger.info("用户取消全量恢复操作。")
                    return 0
                
                restore_manager.logger.info("开始全量恢复所有备份模块...")
                success = restore_manager.restore_all_modules()
        
        if success:
            restore_manager.logger.info("✅ 配置模块镜像恢复流程执行完成！")
            return 0
        else:
            restore_manager.logger.error("❌ 恢复过程中出现错误")
            return 1
            
    except KeyboardInterrupt:
        restore_manager.logger.info("用户中断操作")
        return 130
    except Exception as e:
        restore_manager.logger.error(f"未预期的错误: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())