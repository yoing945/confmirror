#!/bin/bash
# 示例备份脚本
# 用法: 
#   ./example_backup_script.sh backup  # 执行备份
#   ./example_backup_script.sh restore  # 执行恢复

# 获取操作类型
OPERATION=$1

# 配置
BACKUP_ROOT="./backup"
MODULE_NAME="脚本化备份示例"

case "$OPERATION" in
    "backup")
        echo "[$MODULE_NAME] 开始执行自定义备份逻辑..."
        
        # 示例：备份特定配置信息
        echo "[$MODULE_NAME] 备份系统信息..."
        uname -a > "$BACKUP_ROOT/system-info.txt"
        date >> "$BACKUP_ROOT/system-info.txt"
        
        # 示例：备份当前运行的进程列表
        echo "[$MODULE_NAME] 备份进程列表..."
        ps aux > "$BACKUP_ROOT/process-list.txt"
        
        # 示例：备份已安装的软件包列表（Ubuntu/Debian）
        if command -v dpkg >/dev/null 2>&1; then
            echo "[$MODULE_NAME] 备份已安装软件包..."
            dpkg --get-selections > "$BACKUP_ROOT/installed-packages.txt"
        fi
        
        echo "[$MODULE_NAME] 自定义备份完成"
        exit 0
        ;;
        
    "restore")
        echo "[$MODULE_NAME] 开始执行自定义恢复逻辑..."
        
        # 注意：这里的恢复逻辑需要根据实际需求编写
        # 大多数情况下，脚本化备份主要用于备份特殊信息
        # 恢复时可能只需要参考这些信息，而不是直接恢复
        
        echo "[$MODULE_NAME] 自定义恢复完成"
        exit 0
        ;;
        
    *)
        echo "错误: 未知的操作类型 '$OPERATION'"
        echo "支持的类型: backup, restore"
        exit 1
        ;;
esac