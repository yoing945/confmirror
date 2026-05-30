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
# 开发模式安装（当前未发布到 PyPI）
git clone <仓库地址>
cd confmirror
pip install -e ".[dev]"
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
    parent_path: "/etc/nginx"
    include_paths:
      - "nginx.conf"
      - "sites-available/default"

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
| `backup_file_mode` | 备份文件在 mirror 中的权限（八进制字符串） | `"0o644"` |
| `backup_dir_mode` | 备份目录在 mirror 中的权限（八进制字符串） | `"0o755"` |

### Modules 选项

每个模块可以包含以下字段：

| 字段 | 描述 | 必需 |
|------|------|------|
| `name` | 模块名称 | 是 |
| `include_paths` | 要备份的路径列表 | 否* |
| `parent_path` | 拼接到 `include_paths` 前的父路径 | 否 |
| `exclude_paths` | 要排除的路径模式 | 否 |
| `script` | 相对于 `script_hooks_dir` 的脚本路径 | 否* |
| `script_lang` | 脚本解释器语言，默认 `bash` | 否 |

> * `include_paths` 和 `script` 二者选其一；同时存在时 `script` 优先

### 模块配置示例

```yaml
modules:
  # 1. 路径备份模块
  - name: "ssh-config"
    include_paths:
      - "/etc/ssh/sshd_config"
      - "/etc/ssh/ssh_config.d/"
    exclude_paths:
      - "*.bak"           # 排除所有 .bak 文件
      - "*.tmp"           # 排除所有 .tmp 文件
      - "config.bak"      # 排除特定文件
      - "temp/"           # 排除目录
      - "*/temp/*"        # 排除所有层级的 temp 目录中的文件
      - "**/logs/"        # 排除任意深度的 logs 目录
      - "!important.log"  # 例外：不排除 important.log 文件（即使它匹配了 *.log 模式）

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
      - "*.log"           # 排除所有 .log 文件
      - "**/cache/"       # 排除任意深度的 cache 目录
      - "temp*"           # 排除以 temp 开头的文件或目录
```

### 排除模式说明

ConfMirror 的 `exclude_paths` 支持 Git 风格的模式匹配，类似于 `.gitignore` 文件的语法：

- `*.txt` - 匹配所有 .txt 文件
- `*.log` - 匹配所有 .log 文件
- `dir/` - 匹配名为 dir 的目录
- `temp/` - 排除名为 temp 的目录及其内容
- `*/temp/*` - 匹配任意一级目录下的 temp 目录中的文件
- `**/temp` - 匹配任意深度的名为 temp 的文件或目录
- `!important.log` - 作为例外，不排除 important.log 文件（必须放在 *.log 规则之后）
- `a/**/b` - 匹配 a 和 b 之间有任意层级目录的路径，如 a/x/y/z/b

## 📋 命令参考

### 备份命令

```bash
# 全量备份（有交互确认）
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
# 还原指定模块 (建议 root，涉及写系统目录和改权限)
sudo confmirror restore --module <module-name>

# 强制覆盖还原
sudo confmirror restore --module <module-name> --force

# 还原指定路径 (建议 root)
sudo confmirror restore <path1> <path2> ...

# 全量还原 (建议 root，有交互确认)
sudo confmirror restore
```

### 高级配置选项

ConfMirror 支持通过命令行参数和全局配置来指定配置文件路径，方便在不同环境下使用不同的配置。

#### 指定配置文件路径

使用 `--config` 参数可以手动指定配置文件路径，而不必在当前目录下寻找 `confmirror.yaml`：

```bash
# 备份时指定配置文件路径
confmirror backup --config /path/to/your/config.yaml

# 还原时指定配置文件路径
sudo confmirror restore --config /path/to/your/config.yaml

# 使用特定配置文件执行其他命令
confmirror ls --config /path/to/your/config.yaml
confmirror perms --config /path/to/your/config.yaml
```

#### 管理全局配置路径

通过 `global-config-path` 子命令，可以设置一个全局默认的配置文件路径，这样在没有指定 `--config` 参数且当前目录没有 `confmirror.yaml` 时，会自动使用全局配置：

```bash
# 设置全局配置文件路径
confmirror global-config-path set /default/path/to/config.yaml

# 显示当前全局配置文件路径
confmirror global-config-path show

# 移除全局配置文件路径设置
confmirror global-config-path remove
```

全局配置文件存放在 `~/.config/confmirror/config.yaml`，遵循 XDG Base Directory 规范。

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

# 手动同步到远端仓库
confmirror sync

# 使用自定义提交信息同步到远端仓库
confmirror sync --message "自定义提交信息"

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

## 多机配置管理策略

confmirror 支持多种方式管理多台服务器的配置备份，以下是两种主要策略：

### 1. 独立仓库管理

为每台服务器创建独立的配置仓库，实现完全隔离。

#### 目录结构
```
config-server1/      # server1 的配置
├── confmirror.yaml
├── mirror/
├── script-hooks/
└── logs/

config-server2/     # server2 的配置
├── confmirror.yaml
├── mirror/
├── script-hooks/
└── logs/

config-shared/      # 共享配置
├── common-scripts/
└── templates/

```

### 2. 单一仓库管理

使用一个仓库管理所有服务器配置，通过 Git 的 sparse checkout 功能实现每台服务器只拉取自己的配置。也可以使用分支来管理不同服务器的配置，下面以sparse checkout为例说明。

#### 目录结构
```
backup-repo/
├── server1/
│   ├── confmirror.yaml
│   ├── mirror/
│   │   ├── etc/
│   │   │   ├── ssh/
│   │   │   │   └── sshd_config
│   │   │   └── nginx/
│   │   │       └── nginx.conf
│   │   └── home/
│   │       └── user/
│   │           └── .bashrc
│   ├── script-hooks/
│   └── logs/
├── server2/
│   ├── confmirror.yaml
│   ├── mirror/
│   │   ├── etc/
│   │   │   ├── network/
│   │   │   │   └── routes.conf
│   │   │   └── firewall/
│   │   │       └── iptables.rules
│   │   └── home/
│   │       └── admin/
│   │           └── .bashrc
│   ├── script-hooks/
│   └── logs/
├── shared/
│   ├── common-scripts/
│   └── templates/
├── .gitignore
└── README.md
```

#### 配置 sparse checkout

在每台服务器上执行以下操作：

1. 初始化仓库并启用 sparse checkout：
```bash
git clone <repository-url> .
git config core.sparseCheckout true
```

2. 编辑 `.git/info/sparse-checkout` 文件，添加对应服务器的目录：
```bash
# 对于 server1，添加以下内容到 .git/info/sparse-checkout
/server1/*
/shared/*

# 对于 server2，添加以下内容到 .git/info/sparse-checkout
/server2/*
/shared/*
```

3. 更新工作目录：
```bash
git read-tree -m -u HEAD
```


## 常见问题

### 权限问题

在某些情况下，备份或还原操作可能需要更高的权限。如果遇到权限错误，可以使用以下方式提权：

```bash
# 如在备份时使用完整路径执行提权
sudo $(which confmirror) backup