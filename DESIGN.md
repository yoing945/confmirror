# **confmirror 设计文档**
> **Configuration Mirror** —— 声明式系统配置镜像与还原工具

---

## 目录

- [1. 设计目标](#1-设计目标)
- [2. 核心特性](#2-核心特性)
- [3. 低耦合设计](#3-低耦合设计)
- [4. 目录结构](#4-目录结构)
  - [4.1 工具仓库（`confmirror/`）](#41-工具仓库-confmirror)
  - [4.2 数据仓库](#42-数据仓库)
- [5. 功能详细设计](#5-功能详细设计)
  - [5.1 配置文件 (`confmirror.yaml`)](#51-配置文件-confmirroryaml)
  - [5.2 备份流程](#52-备份流程)
  - [5.3 还原流程](#53-还原流程)
  - [5.4 脚本钩子机制](#54-脚本钩子机制)
  - [5.5 权限查看功能](#55-权限查看功能)
  - [5.6 模块列表功能](#56-模块列表功能)
  - [5.7 差异比较功能](#57-差异比较功能)
  - [5.8 元数据管理 (`.meta` 文件)](#58-元数据管理-meta-文件)
  - [5.9 权限与安全](#59-权限与安全)
  - [5.10 日志系统](#510-日志系统)
- [6. 命令行接口 (CLI)](#6-命令行接口-cli)
- [7. 使用示例](#7-使用示例)
  - [7.1 初始化](#71-初始化)
  - [7.2 首次备份](#72-首次备份)
  - [7.3 还原 SSH 配置](#73-还原-ssh-配置)
  - [7.4 查看模块权限信息](#74-查看模块权限信息)
  - [7.5 查看特定路径权限信息](#75-查看特定路径权限信息)
  - [7.6 权限问题处理](#76-权限问题处理)
- [8. 与同类工具对比](#8-与同类工具对比)
- [9. 多服务器配置管理策略](#9-多服务器配置管理策略)

---

## 1. 设计目标

- **安全可靠**：完整保留文件权限、属主、类型，支持精确还原。
- **声明式管理**：通过 YAML 配置文件定义备份规则，可版本化、可复用。
- **轻量无侵入**：不修改原系统目录，仅在独立数据仓库中维护镜像。
- **生产就绪**：支持交互确认、分级日志、错误还原，避免误操作。
- **Git 集成**：可与 Git 结合使用，实现历史追溯、差异对比、远程同步。
- **智能补全**：支持命令和模块名称的自动补全功能。

---

## 2. 核心特性

| 特性 | 说明 |
|------|------|
| **1:1 目录镜像** | `mirror/etc/ssh/sshd_config` 与系统路径完全一致 |
| **元数据持久化** | 自动保存 `mode/uid/gid/type` 到 `.meta` 文件 |
| **YAML 配置驱动** | 声明式定义模块、路径、父路径、脚本钩子 |
| **脚本钩子扩展** | 支持任意 shell/python 脚本处理复杂备份逻辑 |
| **权限感知** | `backup` 无需 root，`restore` 强制提权 |
| **简单日志轮转** | 自动保留最近 N 行日志，避免磁盘占满 |
| **模块化操作** | 支持全量或按模块 (`mod`) 粒度备份/还原 |
| **权限查看** | `perms` 命令可查看备份文件的权限信息 |
| **模块列表** | `ls` 命令可列出所有模块及详细信息 |

---

## 3. 低耦合设计

confmirror 采用低耦合设计，配置即文件，且与 Git 操作解耦，支持多种 Git 工作流：

- **Git 功能独立**：Git 的 submodule、sparse-checkout、branch 等功能可单独使用
- **灵活部署**：支持完整克隆、部分检出、多仓库管理等多种部署方式
- **兼容性好**：无论使用哪种 Git 策略，confmirror 都能在当前目录正常工作
- **扩展性强**：用户可根据需要自由选择 Git 工作流，不影响工具功能

---

## 4. 目录结构

### 4.1 工具仓库（`confmirror/`）

```text
confmirror/                     # ← 工具仓库（代码）
├── pyproject.toml              # ← 支持 pip install
├── README.md
├── src/
│   └── confmirror/
│       ├── __init__.py
│       ├── cli.py              # CLI 解析
│       ├── config.py           # 配置文件加载
│       ├── backup.py           # 备份逻辑
│       ├── restore.py          # 还原逻辑
│       ├── perms.py            # 权限查看功能
│       ├── list.py             # 模块列表功能
│       ├── meta.py             # 元数据管理
│       ├── gitops.py           # Git 操作
│       ├── logger.py           # 日志系统
│       └── utils.py            # 工具函数
├── example/
│   └── confmirror.yaml         # ← 配置文件示例
└── .gitignore
```

### 4.2 数据仓库

默认路径：`./mirror`（由配置文件中的 `backup_root` 指定）

```text
confmirror-data/                # ← 数据仓库
├── confmirror.yaml             # ← 配置文件
├── mirror/                     # ← 配置镜像（1:1 系统结构）
│   └── etc/
│       └── ssh/
│           ├── sshd_config
│           └── sshd_config.meta
├── script-hooks/               # ← 脚本钩子目录
│   └── ufw/
│       └── script.sh           # ← 被 confmirror.yaml 引用
└── .gitignore
```

> 💡 **关键约定**：
> - 所有备份内容存于 `mirror/`
> - 所有脚本钩子存于 `script-hooks/<mod>/script.sh`
> - 配置文件统一命名为 `confmirror.yaml`

---

## 5. 功能详细设计

### 5.1 配置文件 (`confmirror.yaml`)

采用 **YAML 格式**，支持注释、灵活缩进。

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

字段说明：
- `settings`（可选）：元数据配置，包含备份根目录、脚本钩子目录等
- `modules`（必填）：模块列表
- `name`（必填）：模块名称，用于日志和选择性操作
- `include_paths`（二选一）：要备份的路径列表（文件或目录）
- `parent_path`（可选）：拼接到 `include_paths` 前的父路径
- `exclude_paths`（可选）：要排除的路径模式（支持通配符）
- `script`（二选一）：相对于 `script_hooks_dir` 的脚本路径

> ⚠️ `include_paths` 与 `script` 互斥，优先使用 `script`。

> 💡 **注意**：配置文件支持自动验证功能，能够检测YAML语法错误（如制表符、括号不匹配等）并提供清晰的错误信息，帮助快速定位和修复配置问题。

---

### 5.2 备份流程

1. **读取 `confmirror.yaml`** → 获取配置
2. **遍历每个模块**：
   - 若含 `script`：
     - 执行 `script-hooks/<script> backup`
   - 否则：
     - 对每个 `include_path`（拼接 `parent_path`）：
       - 若为文件：复制到 `mirror/<path>`，生成 `.meta`
       - 若为目录：递归处理（遵循 `exclude_paths` 规则）
3. **记录日志**（INFO/WARNING/ERROR）
4. **Git 操作**（如果启用自动提交）
5. **结束**

---

### 5.3 还原流程

1. **检查是否 root**（非 root 则报错退出）
2. **加载配置 & 定位模块/路径**
3. **对每个目标路径**：
   - 检查 `mirror/<path>.meta` 是否存在
   - 读取元数据（`mode`, `uid`, `gid`, `type`）
   - **文件**：`cp` + `chmod` + `chown`
   - **目录**：`rsync` 同步内容 + 设置目录属性
4. **严格不删除**：仅覆盖/新增，不删除目标端额外文件
5. **交互确认**：全量备份和恢复需二次确认，防止误操作。

---

### 5.4 脚本钩子机制

- 脚本位置：相对于 `script_hooks_dir` 配置项的路径（默认为 `./script-hooks/`）
- 调用方式：
  ```bash
  bash script-hooks/ufw/script.sh backup   # 备份时
  bash script-hooks/ufw/script.sh restore  # 还原时
  ```
- 脚本需自行处理：
  - 备份：将输出写入 `mirror/` 下对应位置
  - 还原：从 `mirror/` 读取并应用到系统
- 工具不干预脚本内部逻辑，仅传递 `backup` 或 `restore` 参数
- 配置示例：
  ```yaml
  settings:
    script_hooks_dir: "./script-hooks"  # 脚本钩子目录

  modules:
    - name: "ufw"
      script: "ufw/script.sh"          # 相对于 script-hooks/ 的路径
  ```

---

### 5.5 权限查看功能

- `perms` 命令，用于快速查看备份文件和源文件的权限信息
- 支持按模块或路径查看权限详情
- 显示文件类型、权限模式、所有者等信息
- 使用方法：
  ```bash
  # 查看特定模块的权限信息
  confmirror perms --module sshd

  # 查看特定路径的权限信息
  confmirror perms /etc/ssh/sshd_config
  ```

---

### 5.6 模块列表功能

- `ls` 命令，用于列出所有模块
- 支持查看模块详细信息
- 使用方法：
  ```bash
  # 列出所有模块
  confmirror ls

  # 查看特定模块的详细信息
  confmirror ls --module sshd --detail
  ```

---

### 5.7 差异比较功能

- `diff` 命令，用于比较源文件与备份文件的差异
- 支持按模块或路径进行差异对比
- 显示内容和元数据的详细差异
- 使用方法：
  ```bash
  # 比较指定模块的所有文件
  confmirror diff --module sshd
  
  # 比较指定路径的文件
  confmirror diff /etc/ssh/sshd_config
  
  # 显示详细内容差异
  confmirror diff --module sshd --detail
  ```

- 功能特点：
  - 比较文件内容是否发生变化
  - 检查元数据（权限、属主、类型）是否一致
  - 显示文件大小、修改时间等基本信息
  - 支持统一差异格式（Unified Diff）显示内容差异
  - 对于目录，比较元数据信息

---

### 5.8 元数据管理 (`.meta` 文件)

每个备份文件/目录旁生成同名 `.meta` 文件：

```ini
mode:644
uid:0
gid:0
type:file
```

或

```ini
mode:755
uid:0
gid:0
type:dir
```

> 还原时严格依赖此文件，缺失则跳过。

---

### 5.9 权限与安全

| 操作 | 权限要求 | 说明 |
|------|--------|------|
| `backup` | 普通用户 | 只需读权限 |
| `restore` | **root** | 需写系统目录 + 修改权限/属主 |
| `restore-all` | root + 交互确认 | 高危操作，强制确认 |
| `perms` | 普通用户 | 只读操作 |
| `ls` | 普通用户 | 只读操作 |

---

### 5.10 日志系统

- **日志文件**：默认 `./logs/{name}.log`（若未指定文件名，则使用 settings.name）
- **格式**：`[2026-01-25 20:00:00] [INFO] 消息`
- **轮转**：保留最近 `LOG_KEEP_LINES` 行（默认 1000）
- **终端输出**：带颜色（INFO=绿, WARNING=黄, ERROR=红, 跳过信息=灰）
- **跳过信息**：当备份或还原操作因文件未发生变化而跳过时，会在日志中以灰色显示，方便用户快速识别哪些文件被跳过

---

## 6. 命令行接口 (CLI)

```bash
# 全量备份
confmirror backup

# 备份指定模块
confmirror backup --module sshd

# 备份指定路径
confmirror backup /etc/ssh/sshd_config

# 全量还原（交互确认）
confmirror restore

# 还原单个路径
confmirror restore /etc/hosts

# 还原指定模块
confmirror restore --module ufw

# 查看模块权限信息
confmirror perms --module sshd

# 查看路径权限信息
confmirror perms /etc/ssh/sshd_config

# 比较模块文件差异
confmirror diff --module sshd

# 比较指定路径文件差异
confmirror diff /etc/ssh/sshd_config

# 显示详细差异
confmirror diff --module sshd --detail

# 列出所有模块
confmirror ls

# 列出指定模块的详细信息
confmirror ls --module sshd --detail

# 显示版本
confmirror --version

# 显示帮助
confmirror --help
```

> 所有命令均通过统一入口 `confmirror` 分发。

## 6.1 自动补全功能

confmirror 支持命令和模块名称的自动补全功能。您可以使用以下方式安装自动补全：

```bash
# 对于 Bash 用户
eval "$(_CONFMIRROR_COMPLETE=bash_source confmirror)"

# 对于 Zsh 用户
eval "$(_CONFMIRROR_COMPLETE=zsh_source confmirror)"

# 对于 Fish 用户
_CONFMIRROR_COMPLETE=fish_source confmirror
```

要永久激活自动补全，请参阅 [AUTO_COMPLETION.md](AUTO_COMPLETION.md) 文档。

安装完成后，您可以：

- 输入 `confmirror` 后按 `TAB` 键查看可用的子命令
- 输入 `confmirror backup -m` 后按 `TAB` 键查看可用的模块名
- 输入 `confmirror restore -m` 后按 `TAB` 键查看可用的模块名

---

## 7. 使用示例

### 7.1 初始化
```bash
# 从 PyPI 安装（发布后）
pip install confmirror
```

### 7.2 首次备份
```bash
# 创建配置文件
cp example/confmirror.yaml ./
# 编辑 confmirror.yaml 以满足你的需求
./confmirror backup
```

### 7.3 还原 SSH 配置
```bash
sudo ./confmirror restore --module sshd
```

### 7.4 查看模块权限信息
```bash
./confmirror perms --module sshd
```

### 7.5 查看特定路径权限信息
```bash
./confmirror perms /etc/ssh/sshd_config
```

### 7.6 权限问题处理

在某些情况下，备份或还原操作可能需要更高的权限。如果遇到权限错误，可以使用以下方式提权：

```bash
# 使用完整路径执行提权
sudo $(which confmirror) backup
```

---

## 8. 与同类工具对比

| 工具 | 优点 | 缺点 | confmirror 优势 |
|------|------|------|----------------|
| etckeeper | 专为 `/etc` 设计 | 仅适用于特定目录 | 通用配置管理，支持任意路径 |
| rdiff-backup | 强大的增量备份 | 学习曲线陡峭 | 简单易用，声明式配置 |
| duplicity | 加密备份 | 配置复杂 | 轻量级，Git 集成 |
| rsnapshot | 时间点快照 | 配置复杂 | 简单配置，模块化管理 |

---

## 9. 多服务器配置管理策略

confmirror 支持多种方式管理多台服务器的配置备份，以下是两种主要策略：

### 9.1 独立仓库管理

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

### 9.2 单一仓库管理

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
---
