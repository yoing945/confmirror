# **confmirror**  
> **Configuration Mirror** —— 基于 Git 的声明式系统配置镜像与还原工具

---

## 目录

- [1. 设计目标](#1-设计目标)
- [2. 核心特性](#2-核心特性)
- [3. 整体架构](#3-整体架构)
- [4. 目录结构](#4-目录结构)
  - [4.1 工具仓库（`confmirror/`）](#41-工具仓库-confmirror)
  - [4.2 数据仓库（由 `.env` 指定）](#42-数据仓库由-env-指定)
- [5. 功能详细设计](#5-功能详细设计)
  - [5.1 配置文件 (`backup-rules.yaml`)](#51-配置文件-backup-rulesyaml)
  - [5.2 备份流程](#52-备份流程)
  - [5.3 还原流程](#53-还原流程)
  - [5.4 脚本钩子机制](#54-脚本钩子机制)
  - [5.5 元数据管理 (`.meta` 文件)](#55-元数据管理-meta-文件)
  - [5.6 权限与安全](#56-权限与安全)
  - [5.7 日志系统](#57-日志系统)
- [6. 命令行接口 (CLI)](#6-命令行接口-cli)
- [7. 使用示例](#7-使用示例)
- [8. 与同类工具对比](#8-与同类工具对比)
- [9. 未来扩展](#9-未来扩展)

---

## 1. 设计目标

- **安全可靠**：完整保留文件权限、属主、类型，支持精确还原。
- **声明式管理**：通过 YAML 配置文件定义备份规则，可版本化、可复用。
- **Git 原生集成**：备份结果即 Git 仓库，天然支持历史追溯、差异对比、远程同步。
- **轻量无侵入**：不修改原系统目录，仅在独立数据仓库中维护镜像。
- **生产就绪**：支持交互确认、分级日志、错误恢复，避免误操作。

---

## 2. 核心特性

| 特性 | 说明 |
|------|------|
| ✅ **1:1 目录镜像** | `mirror/etc/ssh/sshd_config` 与系统路径完全一致 |
| ✅ **元数据持久化** | 自动保存 `mode/uid/gid/type` 到 `.meta` 文件 |
| ✅ **YAML 配置驱动** | 声明式定义模块、路径、父路径、脚本钩子 |
| ✅ **脚本钩子扩展** | 支持任意 shell/python 脚本处理复杂备份逻辑 |
| ✅ **权限感知** | `backup` 无需 root，`restore` 强制提权 |
| ✅ **日志轮转** | 自动保留最近 N 行日志，避免磁盘占满 |
| ✅ **模块化操作** | 支持全量或按模块 (`mod`) 粒度备份/还原 |

---

## 3. 整体架构

```text
+------------------+       +---------------------+
|   confmirror     |       |   Data Repository   |
|   (Tool Repo)    |<----->|  (Config Mirror)    |
+------------------+       +---------------------+
        |                           |
        | .env → MIRROR_ROOT        | mirror-rules.yaml
        | CLI commands              | mirror/
        |                           | script-hooks/
        v                           v
    User Interaction           Git Version Control
```

- **工具仓库**：提供通用逻辑（`confmirror` 命令）
- **数据仓库**：存储特定环境的配置镜像（每个服务器/环境一个）

---

## 4. 目录结构

### 4.1 工具仓库（`confmirror/`）

```text
confmirror/                     # ← 工具仓库（代码）
├── confmirror                  # ← 主入口（可执行脚本）
├── src/
│   ├── __init__.py
│   ├── cli.py                  # CLI 解析
│   ├── core.py                 # 公共函数（路径、日志、.env 加载）
│   ├── backup.py               # 备份逻辑
│   └── restore.py              # 还原逻辑
├── logs/                       # ← 默认日志目录（可配置）
├── .env                        # ← 指向数据仓库根目录
├── .env.example
├── README.md
├── pyproject.toml              # ← 支持 pip install
└── .gitignore
```

### 4.2 数据仓库（由 `.env` 指定）

默认路径：`../confmirror-repository`（若未设置 `BACKUP_ROOT`）

```text
sync-mainserver-configs/        # ← 数据仓库（由 BACKUP_ROOT 指定）
├── mirror-rules.yaml           # ← 镜像备份规则配置
├── mirror/                     # ← 配置镜像（1:1 系统结构）
│   └── etc/
│       └── ssh/
│           ├── sshd_config
│           └── sshd_config.meta
├── script-hooks/               # ← 脚本钩子目录
│   └── ufw/
│       └── script.sh           # ← 被 mirror-rules.yaml 引用
└── .gitignore
```

> 💡 **关键约定**：
> - 所有备份内容存于 `mirror/`
> - 所有脚本钩子存于 `script-hooks/<mod>/script.sh`
> - 配置文件必须命名为 `mirror-rules.yaml`

---

## 5. 功能详细设计

### 5.1 配置文件 (`mirror-rules.yaml`)

采用 **YAML 格式**，支持注释、灵活缩进。

```yaml
modules:
  - mod: "sshd"
    paths:
      - /etc/ssh/sshd_config

  - mod: "ufw"
    script: "ufw/script.sh"   # 相对于 script-hooks/

  - mod: "traefik"
    parent_path: "/data/dockerapps/traefik/"
    paths:
      - docker-compose.yml
      - traefik.yml
      - dynamic/
```

字段说明：
- `mod`（必填）：模块名称，用于日志和选择性操作
- `paths`（二选一）：要备份的路径列表（文件或目录）
- `parent_path`（可选）：拼接到 `paths` 前的父路径
- `script`（二选一）：相对于 `script-hooks/` 的脚本路径

> ⚠️ `paths` 与 `script` 互斥，优先使用 `script`。

---

### 5.2 备份流程

1. **加载 `.env`** → 获取 `MIRROR_ROOT`
2. **读取 `mirror-rules.yaml`**
3. **遍历每个模块**：
   - 若含 `script`：
     - 执行 `script-hooks/<script> backup`
   - 否则：
     - 对每个 `path`（拼接 `parent_path`）：
       - 若为文件：复制到 `mirror/<path>`，生成 `.meta`
       - 若为目录：递归处理（跳过 `*.log`, `cache`, `.git` 等）
4. **记录日志**（INFO/WARNING/ERROR）
5. **结束**（不自动 `git commit/push`，留用户控制）

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
5. **交互确认**：`restore-all` 需输入 `YES`

---

### 5.4 脚本钩子机制

- 脚本位置：`script-hooks/<relative_path>`
- 调用方式：
  ```bash
  bash script-hooks/ufw/script.sh backup   # 备份时
  bash script-hooks/ufw/script.sh restore  # 还原时
  ```
- 脚本需自行处理：
  - 备份：将输出写入 `mirror/` 下对应位置
  - 还原：从 `mirror/` 读取并应用到系统
- 工具不干预脚本内部逻辑，仅传递 `backup`/`restore` 参数

---

### 5.5 元数据管理 (`.meta` 文件)

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

### 5.6 权限与安全

| 操作 | 权限要求 | 说明 |
|------|--------|------|
| `backup` | 普通用户 | 只需读权限 |
| `restore` | **root** | 需写系统目录 + 修改权限/属主 |
| `restore-all` | root + 交互确认 | 高危操作，强制确认 |

---

### 5.7 日志系统

- **日志文件**：默认 `./logs/confmirror.log`（可配置）
- **格式**：`[2026-01-25 20:00:00] [INFO] 消息`
- **轮转**：保留最近 `LOG_KEEP_LINES` 行（默认 100）
- **终端输出**：带颜色（INFO=绿, WARNING=黄, ERROR=红）

---

## 6. 命令行接口 (CLI)

```bash
# 全量备份
confmirror backup-all

# 备份指定模块
confmirror backup --mod sshd

# 全量还原（交互确认）
confmirror restore-all

# 还原单个路径
confmirror restore /etc/hosts

# 还原指定模块
confmirror restore --mod ufw


# 显示版本
confmirror --version

# 显示帮助
confmirror --help
```

> 所有命令均通过统一入口 `confmirror` 分发。

---

## 7. 使用示例

### 初始化
```bash
git clone https://github.com/you/confmirror.git
cd confmirror
cp .env.example .env
# 编辑 .env: MIRROR_ROOT=/data/configs/my-server-configs
```

### 首次备份
```bash
./confmirror backup
# 自动生成 /data/configs/my-server-configs/ 并提示编辑 mirror-rules.yaml
```

### 还原 SSH 配置
```bash
sudo ./confmirror restore --mod sshd
```

---
