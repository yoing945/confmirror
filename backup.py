#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git配置备份工具 - 备份脚本
功能: 将系统配置文件备份到Git仓库，支持模块化配置和脚本化备份
"""

import os
import sys
import json
import shutil
import hashlib
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
import logging
from dataclasses import dataclass
import re


@dataclass
class BackupConfig:
    """备份配置类"""
    backup_config_file: str
    git_backup_root: str
    git_backup_script_root: str
    log_file: str
    log_keep_lines: int = 100
    git_remote_url: str = ""
    git_branch: str = "main"
    auto_git_commit: bool = False
    auto_git_push: bool = False
    verbose: bool = True
    exclude_patterns: Union[List[str], None] = None
    enable_file_checksum: bool = False

    def __post_init__(self):
        if self.exclude_patterns is None:
            self.exclude_patterns = [
                ".git", "*.log", "*.tmp", "cache", "temp", 
                "*.pid", "*.bak", "downloads", "__pycache__", "node_modules"
            ]


class BackupLogger:
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


class BackupManager:
    """备份管理器"""
    
    def __init__(self, config: BackupConfig):
        self.config = config
        self.logger = BackupLogger(
            config.log_file, 
            config.log_keep_lines, 
            config.verbose
        )
        
        # 确保必要目录存在
        Path(config.git_backup_root).mkdir(parents=True, exist_ok=True)
        Path(config.git_backup_script_root).mkdir(parents=True, exist_ok=True)
    
    def _should_exclude(self, path: str) -> bool:
        """检查路径是否应该被排除"""
        path_name = os.path.basename(path)
        
        for pattern in self.config.exclude_patterns or []:
            if pattern.startswith('*'):
                # 通配符匹配
                if path_name.endswith(pattern[1:]):
                    return True
            else:
                # 精确匹配
                if path_name == pattern:
                    return True
        
        return False
    
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
    
    def _get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """获取文件元数据"""
        try:
            stat = os.stat(file_path)
            return {
                'mode': oct(stat.st_mode)[-3:],
                'uid': stat.st_uid,
                'gid': stat.st_gid,
                'size': stat.st_size,
                'mtime': stat.st_mtime,
                'type': 'file' if os.path.isfile(file_path) else 'dir',
                'checksum': self._calculate_checksum(file_path) if os.path.isfile(file_path) else ""
            }
        except Exception as e:
            self.logger.error(f"获取文件元数据失败 {file_path}: {e}")
            return {}
    
    def _backup_single_file(self, src_path: str, module_name: str) -> bool:
        """备份单个文件"""
        src_file = Path(src_path)
        if not src_file.exists():
            self.logger.warning(f"源文件不存在: {src_path}")
            return False
        
        # 构造目标路径
        relative_path = src_path.lstrip('/')
        dest_file = Path(self.config.git_backup_root) / relative_path
        meta_file = dest_file.with_suffix(dest_file.suffix + '.meta')
        
        try:
            # 确保目标目录存在
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 复制文件
            shutil.copy2(src_path, dest_file)
            
            # 写入元数据
            metadata = self._get_file_metadata(src_path)
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            self.logger.info(
                f"[文件备份成功] {module_name} → {src_path} "
                f"(权限:{metadata.get('mode','unknown')} "
                f"用户:{metadata.get('uid','unknown')}:{metadata.get('gid','unknown')})"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"[文件备份失败] {src_path}: {e}")
            return False
    
    def _backup_directory(self, dir_path: str, module_name: str) -> bool:
        """备份目录"""
        dir_path_obj = Path(dir_path)
        if not dir_path_obj.exists() or not dir_path_obj.is_dir():
            self.logger.warning(f"目录不存在或不是目录: {dir_path}")
            return False
        
        self.logger.info(f"[进入目录] {dir_path}")
        success = True
        
        try:
            for item in dir_path_obj.rglob('*'):
                if self._should_exclude(str(item)):
                    self.logger.info(f"[跳过排除项] {item}")
                    continue
                
                if item.is_file():
                    if not self._backup_single_file(str(item), module_name):
                        success = False
                # 目录通过文件的备份自动创建结构
                
        except Exception as e:
            self.logger.error(f"[目录备份失败] {dir_path}: {e}")
            success = False
        
        return success
    
    def _execute_script_backup(self, script_path: str, module_name: str) -> bool:
        """执行脚本备份"""
        script_full_path = Path(self.config.git_backup_script_root) / script_path
        
        if not script_full_path.exists():
            self.logger.error(f"[脚本备份失败] 模块{module_name} → 指定脚本不存在 {script_full_path}")
            return False
        
        try:
            # 确保脚本可执行
            os.chmod(script_full_path, 0o755)
            
            self.logger.info(f"[脚本备份执行] 模块{module_name} → 运行脚本 {script_full_path}")
            
            # 执行脚本，传入backup参数
            result = subprocess.run(
                [str(script_full_path), 'backup'],
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                self.logger.info(f"[脚本备份成功] 模块{module_name} → 脚本执行完成")
                if result.stdout.strip():
                    self.logger.info(f"脚本输出: {result.stdout.strip()}")
                return True
            else:
                self.logger.error(f"[脚本备份失败] 模块{module_name} → 脚本执行返回非0状态码")
                if result.stderr.strip():
                    self.logger.error(f"错误信息: {result.stderr.strip()}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"[脚本备份失败] 模块{module_name} → 脚本执行超时")
            return False
        except Exception as e:
            self.logger.error(f"[脚本备份失败] 模块{module_name} → 执行异常: {e}")
            return False
    
    def load_config(self) -> List[Dict[str, Any]]:
        """加载备份配置文件"""
        config_file = Path(self.config.backup_config_file)
        
        if not config_file.exists():
            self.logger.warning(f"配置文件不存在: {config_file}")
            return []
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 简单的JSON-like解析（兼容原bash脚本的格式）
            # 将配置转换为标准JSON格式
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
    
    def backup_module(self, module_config: Dict[str, Any]) -> bool:
        """备份单个模块"""
        module_name = module_config.get('mod', '')
        if not module_name:
            self.logger.warning("无效配置块，模块名为空")
            return False
        
        self.logger.info(f"开始备份模块 → {module_name}")
        
        script_path = module_config.get('script-path', '')
        
        # 优先执行脚本备份
        if script_path:
            return self._execute_script_backup(script_path, module_name)
        
        # 否则执行路径备份
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
            
            if os.path.isfile(full_path):
                if not self._backup_single_file(full_path, module_name):
                    success = False
            elif os.path.isdir(full_path):
                if not self._backup_directory(full_path, module_name):
                    success = False
            else:
                self.logger.warning(f"[跳过] 路径不存在: {full_path}")
        
        return success
    
    def backup_all_modules(self) -> bool:
        """备份所有模块"""
        modules = self.load_config()
        
        if not modules:
            self.logger.warning("未找到任何配置模块")
            return False
        
        self.logger.info(f"找到 {len(modules)} 个配置模块")
        
        success = True
        for module in modules:
            if not self.backup_module(module):
                success = False
        
        return success
    
    def backup_specific_module(self, module_name: str) -> bool:
        """备份指定模块"""
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
        
        return self.backup_module(target_module)
    
    def git_commit_and_push(self) -> bool:
        """Git提交和推送"""
        if not self.config.auto_git_commit:
            return True
        
        git_root = Path(self.config.git_backup_root)
        
        try:
            # 切换到Git仓库目录
            os.chdir(git_root)
            
            # 添加所有文件
            subprocess.run(['git', 'add', '.'], check=True, capture_output=True)
            
            # 提交
            commit_message = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 自动备份服务配置文件"
            subprocess.run(['git', 'commit', '-m', commit_message], check=True, capture_output=True)
            
            self.logger.info("Git仓库已自动提交")
            
            # 推送
            if self.config.auto_git_push and self.config.git_remote_url:
                subprocess.run(['git', 'push', 'origin', self.config.git_branch], check=True, capture_output=True)
                self.logger.info("Git仓库已自动推送至远端")
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Git操作完成/无变更，无需重复推送")
            return True
        except Exception as e:
            self.logger.error(f"Git操作失败: {e}")
            return False


def load_env_config() -> BackupConfig:
    """从.env文件加载配置"""
    env_file = Path('.env')
    
    # 默认配置
    config = BackupConfig(
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
                        elif key == 'GIT_REMOTE_URL':
                            config.git_remote_url = value
                        elif key == 'GIT_BRANCH':
                            config.git_branch = value
                        elif key == 'AUTO_GIT_COMMIT':
                            config.auto_git_commit = value.lower() in ('true', '1', 'yes')
                        elif key == 'AUTO_GIT_PUSH':
                            config.auto_git_push = value.lower() in ('true', '1', 'yes')
                        elif key == 'VERBOSE':
                            config.verbose = value.lower() in ('true', '1', 'yes')
                        elif key == 'EXCLUDE_PATTERNS':
                            config.exclude_patterns = [p.strip() for p in value.split(',')]
                        elif key == 'ENABLE_FILE_CHECKSUM':
                            config.enable_file_checksum = value.lower() in ('true', '1', 'yes')
                            
        except Exception as e:
            print(f"加载.env文件失败: {e}")
    
    return config


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Git配置备份工具 - 备份脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s                    # 备份所有配置
  %(prog)s mod 模块名          # 备份指定模块
  %(prog)s --help             # 显示帮助信息
        """
    )
    
    parser.add_argument(
        'command', 
        nargs='?', 
        default='backup',
        choices=['backup', 'mod'],
        help='执行的命令 (默认: backup)'
    )
    
    parser.add_argument(
        'module_name',
        nargs='?',
        help='模块名称 (当使用mod命令时需要)'
    )
    
    parser.add_argument(
        '--config',
        help='指定配置文件路径'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='试运行模式，不实际执行备份'
    )
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_env_config()
    if args.config:
        config.backup_config_file = args.config
    
    # 创建备份管理器
    backup_manager = BackupManager(config)
    
    # 显示开始信息
    backup_manager.logger.info("=" * 50 + " 开始系统配置镜像备份 " + "=" * 50)
    
    try:
        success = False
        
        if args.command == 'backup':
            if args.dry_run:
                backup_manager.logger.info("[试运行模式] 不会实际执行备份操作")
                # 这里可以添加试运行逻辑
                success = True
            else:
                # 确认备份操作
                confirm = input("即将执行【全量配置备份】，是否继续？(Y/n，默认 Y): ").strip().lower()
                if confirm in ('n', 'no'):
                    backup_manager.logger.info("用户取消全量备份操作。")
                    return 0
                
                success = backup_manager.backup_all_modules()
        
        elif args.command == 'mod':
            if not args.module_name:
                backup_manager.logger.error("mod 命令需要指定模块名")
                parser.print_help()
                return 1
            
            backup_manager.logger.info(f"开始备份指定模块: {args.module_name}")
            success = backup_manager.backup_specific_module(args.module_name)
        
        if success:
            backup_manager.logger.info("✅ 配置模块镜像备份流程执行完成！")
            backup_manager.git_commit_and_push()
            return 0
        else:
            backup_manager.logger.error("❌ 备份过程中出现错误")
            return 1
            
    except KeyboardInterrupt:
        backup_manager.logger.info("用户中断操作")
        return 130
    except Exception as e:
        backup_manager.logger.error(f"未预期的错误: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())