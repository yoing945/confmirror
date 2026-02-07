# ConfMirror

**ConfMirror** 是一个声明式系统配置镜像与还原工具，旨在安全可靠地备份和还原系统配置文件。

## 🚀 功能特性

- **安全可靠**：完整保留文件权限、属主、类型，支持精确还原
- **声明式管理**：通过 YAML 配置文件定义备份规则，可版本化、可复用
- **轻量无侵入**：不修改原系统目录，仅在独立数据仓库中维护镜像
- **生产就绪**：支持交互确认、分级日志、错误还原，避免误操作
- **Git 集成**：可与 Git 结合使用，实现历史追溯、差异对比、远程同步
- **智能补全**：支持命令和模块名称的自动补全功能

## 📦 安装

```bash
# 从 PyPI 安装
pip install confmirror
```

## 🛠️ 快速开始

### 1. 创建配置文件

首先，在工作目录中创建 `confmirror.yaml` 配置文件：

```yaml
settings:
  name: "my-config"             
  backup_root: "./mirror"       # 镜像根目录
  script_hooks_dir: "./script-hooks"    # 脚本钩子目录
  log_dir: "./logs"             # 日志目录
  git_auto_commit: true         # 是否自动提交到 Git
  git_auto_push: false          # 是否自动推送到远程

modules:
  - name: "sshd"
    include_paths:
      - "/etc/ssh/sshd_config"

  - name: "nginx"
    include_paths:
      - "/etc/nginx/nginx.conf"
      - "/etc/nginx/sites-available/default"

  - name: "ufw"
    script: "ufw/script.sh"      # 相对于 script-hooks/ 的脚本路径
```

### 2. 执行备份

```bash
# 全量备份
confmirror backup

# 备份指定模块
confmirror backup --module sshd

# 备份指定路径
confmirror backup /etc/ssh/sshd_config
```

### 3. 执行还原

```bash
# 还原指定模块
sudo confmirror restore --module sshd

# 还原指定路径
sudo confmirror restore /etc/ssh/sshd_config

# 全量还原
sudo confmirror restore
```

## 🔧 配置详解

### 配置文件结构

`confmirror.yaml` 文件包含两个主要部分：

- `settings`：全局设置
- `modules`：备份模块列表

### Settings 选项

| 选项 | 描述 | 默认值 |
|------|------|--------|
| `name` | 配置集名称 | 当前目录名 |
| `backup_root` | 镜像根目录 | `"./mirror"` |
| `script_hooks_dir` | 脚本钩子目录 | `"./script-hooks"` |
| `log_dir` | 日志目录 | `"./logs"` |
| `log_max_lines` | 日志最大保留行数 | `1000` |
| `git_auto_commit` | 是否自动提交到 Git | `false` |
| `git_auto_push` | 是否自动推送到远程 | `false` |

### Modules 选项

每个模块可以包含以下字段：

| 字段 | 描述 | 必需 |
|------|------|------|
| `name` | 模块名称 | 是 |
| `include_paths` | 要备份的路径列表 | 否* |
| `parent_path` | 拼接到 `include_paths` 前的父路径 | 否 |
| `exclude_paths` | 要排除的路径模式（支持通配符） | 否 |
| `script` | 相对于 `script_hooks_dir` 的脚本路径 | 否* |

> * `include_paths` 和 `script` 二选一，不能同时使用

### 模块配置示例

```yaml
modules:
  # 1. 路径备份模块
  - name: "ssh-config"
    include_paths:
      - "/etc/ssh/sshd_config"
      - "/etc/ssh/ssh_config.d/"
    exclude_paths:
      - "*.bak"

  # 2. 脚本备份模块
  - name: "ufw-rules"
    script: "ufw/export-rules.sh"

  # 3. 带父路径的模块
  - name: "docker-apps"
    parent_path: "/data/dockerapps/"
    include_paths:
      - "traefik/docker-compose.yml"
      - "traefik/traefik.yml"
      - "traefik/dynamic/"
    exclude_paths:
      - "*.log"
```

## 📋 命令参考

### 备份命令

```bash
# 全量备份
confmirror backup

# 备份指定模块
confmirror backup --module <module-name>

# 强制覆盖备份
confmirror backup --module <module-name> --force

# 备份指定路径
confmirror backup <path1> <path2> ...
```

### 还原命令

```bash
# 还原指定模块 (需要 root 权限)
sudo confmirror restore --module <module-name>

# 强制覆盖还原
sudo confmirror restore --module <module-name> --force

# 还原指定路径 (需要 root 权限)
sudo confmirror restore <path1> <path2> ...

# 全量还原 (需要 root 权限，有交互确认)
sudo confmirror restore
```

### 其他命令

```bash
# 查看模块信息
confmirror ls

# 查看指定模块的详细信息
confmirror ls --module <module-name> --detail

# 查看备份文件权限信息
confmirror perms --module <module-name>

# 查看指定路径的权限信息
confmirror perms <path>

# 比较源文件与备份文件的差异
confmirror diff --module <module-name>

# 比较指定路径的差异
confmirror diff <path>

# 显示版本
confmirror --version

# 显示帮助
confmirror --help
```

## ⚡ 自动补全

ConfMirror 支持命令和模块名称的自动补全功能。您可以使用以下方式安装自动补全：

```bash
# 对于 Bash 用户
eval "$(_CONFMIRROR_COMPLETE=bash_source confmirror)"

# 对于 Zsh 用户
eval "$(_CONFMIRROR_COMPLETE=zsh_source confmirror)"

# 对于 Fish 用户
eval "$(_CONFMIRROR_COMPLETE=fish_source confmirror)"
```

要永久激活自动补全，请将相应的命令添加到您的 shell 配置文件中（如 `.bashrc`、`.zshrc`）。


## 📁 目录结构

执行备份后，目录结构如下：

```
your-project/
├── confmirror.yaml          # 配置文件
├── mirror/                  # 配置镜像目录
│   └── etc/
│       └── ssh/
│           ├── sshd_config
│           └── sshd_config.meta    # 元数据文件
├── script-hooks/            # 脚本钩子目录
│   └── ufw/
│       └── script.sh
└── logs/                    # 日志目录
    └── my-config.log
```

## 🔄 与 Git 结合使用

虽然 ConfMirror 本身不依赖 Git，但您可以将其与 Git 结合使用，以获得更好的版本控制体验：

### 初始化 Git 仓库

```bash
# 初始化 Git 仓库
git init

# 添加配置文件
git add confmirror.yaml

# 配置 .gitignore
echo "mirror/" >> .gitignore
echo "logs/" >> .gitignore
```

### 启用自动提交

在 `confmirror.yaml` 中启用自动提交：

```yaml
settings:
  git_auto_commit: false    # 启用自动提交（可选）
  git_auto_push: false     # 启用自动推送（可选）
```

启用后，每次执行 `confmirror backup` 命令后，如果启用了 `git_auto_commit`，工具会自动将更改提交到 Git 仓库。

### 手动提交备份

如果您不想启用自动提交，也可以手动使用提交备份：

```bash
# 执行备份
confmirror backup

# 检查更改
git status
git diff

# 提交更改
git add .
git commit -m "Backup configuration: $(date +%Y-%m-%d)"
```
## 常见问题

### 权限问题

在某些情况下，备份或还原操作可能需要更高的权限。如果遇到权限错误，可以使用以下方式提权：

```bash
# 如在备份时使用完整路径执行提权
sudo $(which confmirror) backup