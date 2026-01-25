# Git配置备份工具

一个基于Python的系统配置备份与恢复工具，支持模块化配置、Git版本控制和脚本化备份。

## 功能特性

- 🚀 **模块化管理**: 通过配置文件定义备份模块，灵活配置需要备份的路径
- 📦 **Git版本控制**: 备份内容存储在Git仓库中，支持版本追踪和历史回退
- 🔧 **脚本化备份**: 支持通过自定义脚本执行复杂备份逻辑
- 📝 **详细日志**: 分级日志记录，支持日志轮转和详细输出
- 🔐 **权限保持**: 完整保存和恢复文件权限、用户组等元数据
- ⚡ **高性能**: 使用Python实现，支持并发处理和增量备份
- 🌍 **环境配置**: 通过.env文件灵活配置各种参数

## 文件结构

```
.
├── backup.py              # 备份脚本（无需sudo）
├── restore.py             # 恢复脚本（需要sudo）
├── .env.example           # 环境配置模板
├── sync.conf              # 备份配置文件
├── requirements.txt        # 依赖包列表
├── backup/                # Git备份根目录
├── backup-script/         # 备份脚本目录
├── log-backup.log         # 日志文件
└── README.md             # 说明文档
```

## 快速开始

### 1. 环境准备

```bash
# 克隆或下载项目
cd git-config-backup

# 复制环境配置文件
cp .env.example .env

# 根据需要修改.env文件中的配置
nano .env
```

### 2. 配置备份模块

编辑 `sync.conf` 文件，定义需要备份的模块和路径：

```json
[
  {
    "mod": "系统主机配置",
    "paths": [
      "/etc/hostname",
      "/etc/hosts",
      "/etc/resolv.conf"
    ]
  },
  {
    "mod": "SSH配置",
    "parent-path": "/etc/",
    "paths": [
      "ssh/sshd_config",
      "ssh/ssh_config"
    ]
  },
  {
    "mod": "脚本化备份示例",
    "script-path": "example_backup_script.sh"
  }
]
```

### 3. 初始化Git仓库

```bash
# 初始化备份仓库
cd backup
git init
git add .
git commit -m "初始备份仓库"
cd ..

# 如果需要远程同步
git remote add origin <your-git-repo-url>
```

### 4. 执行备份

```bash
# 备份所有模块（无需sudo）
python3 backup.py

# 备份指定模块
python3 backup.py mod "系统主机配置"

# 试运行模式（不实际备份）
python3 backup.py --dry-run
```

### 5. 执行恢复

```bash
# 恢复指定文件（需要sudo）
sudo python3 restore.py restore /etc/hosts

# 恢复指定模块
sudo python3 restore.py restore-mod "SSH配置"

# 全量恢复（危险操作）
sudo python3 restore.py restore-all

# 强制覆盖已存在文件
sudo python3 restore.py restore /etc/hosts --force
```

## 配置说明

### .env 配置文件

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| BACKUP_CONFIG_FILE | 备份配置文件路径 | ./sync.conf |
| GIT_BACKUP_ROOT | Git备份根目录 | ./backup |
| GIT_BACKUP_SCRIPT_ROOT | 脚本备份根目录 | ./backup-script |
| LOG_FILE | 日志文件路径 | ./log-backup.log |
| LOG_KEEP_LINES | 日志保留行数 | 100 |
| AUTO_GIT_COMMIT | 是否自动Git提交 | false |
| AUTO_GIT_PUSH | 是否自动Git推送 | false |
| VERBOSE | 是否显示详细输出 | true |
| EXCLUDE_PATTERNS | 排除文件模式 | .git,*.log,*.tmp等 |
| ENABLE_FILE_CHECKSUM | 是否启用文件校验 | false |

### 备份配置文件 (sync.conf)

每个模块支持以下配置：

- `mod`: 模块名称（必需）
- `paths`: 需要备份的路径列表
- `parent-path`: 父路径前缀（可选）
- `script-path`: 自定义脚本路径（可选）

#### 文件路径备份
```json
{
  "mod": "基础配置",
  "paths": ["/etc/hosts", "/etc/hostname"]
}
```

#### 带父路径的备份
```json
{
  "mod": "SSH配置",
  "parent-path": "/etc/",
  "paths": ["ssh/sshd_config", "ssh/ssh_config"]
}
```

#### 脚本化备份
```json
{
  "mod": "复杂备份",
  "script-path": "custom_backup.sh"
}
```

## 脚本化备份

对于复杂的备份需求，可以编写自定义脚本：

```bash
#!/bin/bash
# custom_backup.sh

OPERATION=$1

case "$OPERATION" in
    "backup")
        echo "执行自定义备份逻辑..."
        # 在这里编写备份逻辑
        ;;
    "restore")
        echo "执行自定义恢复逻辑..."
        # 在这里编写恢复逻辑
        ;;
    *)
        echo "错误: 未知操作类型"
        exit 1
        ;;
esac
```

脚本接收一个参数：
- `backup`: 执行备份操作
- `restore`: 执行恢复操作

## 安全注意事项

1. **权限管理**: 恢复脚本需要root权限，请谨慎使用
2. **备份验证**: 建议启用文件校验和功能
3. **全量恢复**: 全量恢复是危险操作，请确保了解后果
4. **Git安全**: 如果使用远程Git仓库，请确保仓库安全

## 高级功能

### 文件校验和

在 `.env` 文件中启用：
```env
ENABLE_FILE_CHECKSUM=true
```

启用后会在备份时计算MD5校验和，恢复时验证文件完整性。

### 自动Git操作

在 `.env` 文件中配置：
```env
AUTO_GIT_COMMIT=true
AUTO_GIT_PUSH=true
GIT_REMOTE_URL=https://github.com/user/config-backup.git
```

### 排除文件模式

自定义排除的文件和目录：
```env
EXCLUDE_PATTERNS=.git,*.log,*.tmp,cache,temp,__pycache__,node_modules
```

## 故障排除

### 常见问题

1. **权限不足**
   - 备份脚本：通常无需sudo
   - 恢复脚本：必须使用sudo

2. **配置文件解析错误**
   - 检查JSON格式是否正确
   - 确保所有字符串都用双引号

3. **Git操作失败**
   - 检查Git仓库是否正确初始化
   - 确认远程URL和分支配置

4. **备份失败**
   - 检查源文件是否存在
   - 确认目标目录权限
   - 查看日志文件获取详细错误信息

### 日志查看

```bash
# 查看完整日志
tail -f log-backup.log

# 查看最近的错误
grep "ERROR" log-backup.log
```

## 开发说明

### 依赖管理

本工具主要使用Python标准库，无需额外安装依赖。如果需要扩展功能，可以参考 `requirements.txt` 中的可选依赖。

### 代码结构

- `BackupConfig/RestoreConfig`: 配置管理类
- `BackupLogger/RestoreLogger`: 日志管理类
- `BackupManager/RestoreManager`: 核心业务逻辑
- `load_env_config()`: 环境配置加载
- `main()`: 命令行入口

### 扩展开发

如需添加新功能，建议：

1. 保持现有的代码结构和命名规范
2. 添加适当的日志记录
3. 更新配置文件和文档
4. 编写测试用例

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request来改进这个工具。