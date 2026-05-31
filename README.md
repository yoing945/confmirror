# ConfMirror

**ConfMirror** 是一个声明式系统配置镜像与还原工具，旨在安全可靠地备份和还原系统配置文件。

## 🚀 功能特性

- **安全可靠**：完整保留文件权限、属主、类型，支持精确还原
- **声明式管理**：通过 YAML 配置文件定义备份规则，可版本化、可复用
- **轻量无侵入**：不修改原系统目录，仅在独立数据仓库中维护镜像
- **生产就绪**：支持交互确认、分级日志、错误还原，避免误操作
- **Git 集成**：可与 Git 结合使用，实现历史追溯、差异对比、远程同步
- **智能补全**：支持命令和模块名称的自动补全功能
- **🤖 Agent 友好**：支持 `--format json` 结构化输出、`--dry-run` 预览、`--yes` 非交互模式，便于 AI Agent 集成。项目内置 `.agents/skills/confmirror/SKILL.md`，可直接作为 AI Skill 加载

## 📦 安装

### 通过 uv 安装（推荐）

```bash
uv tool install confmirror
```

### 通过 pip 安装

```bash
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
    paths:
      - "/etc/ssh/sshd_config"

  - name: "nginx"
    base_path: "/etc/nginx"
    paths:
      - "nginx.conf"
      - "sites-available/default"

  - name: "ufw"
    hook: "ufw/script.sh"      # 相对于 script-hooks/ 的脚本路径
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

## 🤖 AI Agent 快速开始

ConfMirror 对 AI Agent 友好，支持结构化 JSON 输出和非交互执行。

### Agent 调用示例

```bash
# 结构化输出（JSON）
confmirror backup --module nginx --format json

# 预览操作（不实际执行）
confmirror backup --module nginx --dry-run --format json

# 非交互模式（跳过所有确认提示）
confmirror backup --yes
confmirror restore --yes

# 组合使用：Agent 安全调用
confmirror backup --module nginx --dry-run --format json
# → 评估影响后，去掉 --dry-run 实际执行
confmirror backup --module nginx --format json
```

### JSON 输出示例

```bash
$ confmirror diff --module nginx --format json
{
  "status": "success",
  "command": "diff",
  "module": "nginx",
  "added": [],
  "deleted": [],
  "changed": [
    {
      "source": "/etc/nginx/nginx.conf",
      "backup": "mirror/etc/nginx/nginx.conf",
      "content_same": false,
      "meta_same": true,
      "unified_diff": ["--- backup: nginx.conf", "+++ source: nginx.conf", "@@ -1 +1 @@", "-old", "+new"]
    }
  ],
  "unchanged": []
}
```

> 💡 **提示**：`--format json` 会自动抑制终端日志输出，确保 stdout 为纯净的 JSON，便于 Agent 解析。

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
| `mirror_file_mode` | 备份文件在 mirror 中的权限（八进制字符串），确保 Git 可读写 | `"0o644"` |
| `mirror_dir_mode` | 备份目录在 mirror 中的权限（八进制字符串），确保 Git 可读写 | `"0o755"` |

### Modules 选项

每个模块可以包含以下字段：

| 字段 | 描述 | 必需 |
|------|------|------|
| `name` | 模块名称 | 是 |
| `paths` | 要备份的路径列表 | 否* |
| `base_path` | 拼接到 `paths` 前的父路径 | 否 |
| `exclude_paths` | 要排除的路径模式 | 否 |
| `hook` | 相对于 `script_hooks_dir` 的脚本路径 | 否* |
| `hook_lang` | 脚本解释器语言，默认 `bash` | 否 |

> * `paths` 和 `hook` 二者选其一；同时存在时 `hook` 优先

### 模块配置示例

```yaml
modules:
  # 1. 路径备份模块
  - name: "ssh-config"
    paths:
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
    hook: "ufw/export-rules.sh"

  # 3. 带父路径的模块
  - name: "docker-apps"
    base_path: "/data/dockerapps/"
    paths:
      - "traefik/docker-compose.yml"
      - "traefik/traefik.yml"
      - "traefik/dynamic/"
    exclude_paths:
      - "*.log"           # 排除所有 .log 文件
      - "**/cache/"       # 排除任意深度的 cache 目录
      - "temp*"           # 排除以 temp 开头的文件或目录
```

### 排除模式

`exclude_paths` 使用 Git 风格的模式匹配（`.gitignore` 语法）：

| 模式 | 含义 |
|------|------|
| `*.log` | 所有 `.log` 文件 |
| `temp/` | 名为 `temp` 的目录 |
| `*/cache/*` | 任意一级 `cache` 目录下的文件 |
| `**/logs/` | 任意深度的 `logs` 目录 |
| `!important.log` | 例外：不排除该文件 |

## 📋 命令参考

### 命令速查

| 命令 | 说明 |
|------|------|
| `confmirror backup` | 全量备份（交互确认） |
| `confmirror backup -m <module>` | 备份指定模块 |
| `confmirror backup -m <module> --force` | 强制覆盖备份 |
| `confmirror backup <path>` | 备份指定路径 |
| `sudo confmirror restore` | 全量还原（建议 root） |
| `sudo confmirror restore -m <module>` | 还原指定模块 |
| `confmirror diff -m <module>` | 对比模块差异 |
| `confmirror perms -m <module>` | 查看权限信息 |
| `confmirror ls` | 列出所有模块 |
| `confmirror sync` | 手动同步到 Git 远程 |
| `confmirror install-system` | 创建系统级入口（解决 `sudo` PATH 问题） |
| `confmirror global-config-path set <path>` | 设置全局默认配置路径 |
| `confmirror global-config-path show` | 显示全局配置路径 |

### 全局选项

| 选项 | 说明 |
|------|------|
| `--format {human,json}` | 输出格式，默认 `human` |
| `--dry-run` | 预览模式，不实际执行 |
| `--yes` | 非交互模式，跳过所有确认 |
| `--config <path>` | 指定配置文件路径 |
| `--version` | 显示版本 |
| `--help` | 显示帮助 |

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

# 配置 .gitignore（logs/ 为运行时日志，建议忽略）
echo "logs/" >> .gitignore
```

### 启用自动提交

在 `confmirror.yaml` 中启用自动提交：

```yaml
settings:
  git_auto_commit: false    # 是否自动提交到 Git（默认 false）
  git_auto_push: false      # 是否自动推送到远程（默认 false，需先设置 git_auto_commit）
```

启用后，每次执行 `confmirror backup` 命令后，如果启用了 `git_auto_commit`，工具会自动将更改提交到 Git 仓库。

### 手动提交

```bash
confmirror backup
git add mirror/ confmirror.yaml
git commit -m "Backup configuration: $(date +%Y-%m-%d)"
```

## 多机管理

多服务器场景的管理策略详见 [docs/MULTI_SERVER.md](docs/MULTI_SERVER.md)。


## 退出码

ConfMirror 使用标准化退出码，便于脚本和 Agent 判断执行结果：

| 退出码 | 含义 | 场景 |
|--------|------|------|
| `0` | 成功 | 命令正常完成 |
| `1` | 配置错误 | 配置文件加载失败、参数错误 |
| `2` | 权限错误 | restore 非 root 运行 |
| `3` | 部分失败 | 某些文件备份/还原失败，但其他成功 |

## 常见问题

### 权限问题

在某些情况下，备份或还原操作可能需要更高的权限。如果遇到权限错误，可以使用以下方式提权：

```bash
# 推荐：创建系统级入口（一次配置，永久可用）
sudo confmirror install-system
# 之后直接使用：
sudo confmirror restore

# 备选：显式传递 PATH
sudo env "PATH=$PATH" confmirror backup

# 备选：进入 root shell
sudo -i
confmirror backup
```

> `install-system` 会在 `/usr/local/bin/confmirror` 创建一个 wrapper 脚本，内部 hardcode 原始 confmirror 的完整路径，从而绕过 `sudo` 重置 PATH 的问题。卸载时执行 `sudo confmirror uninstall-system`。