---
name: confmirror
description: |
  当用户需要备份、还原、查看或管理 Linux 系统配置文件时使用。
  ConfMirror 是一个声明式配置备份/还原工具，通过 YAML 配置定义要备份的模块，
  支持差异备份、Git 版本控制、权限保留和脚本钩子。
---

# ConfMirror — 声明式 Linux 配置备份工具

## 触发场景

- 用户说"备份配置"、"备份 ssh/nginx"、"备份系统配置"
- 用户说"还原配置"、"恢复之前的配置"
- 用户说"查看备份了哪些文件"、"看看权限变化"
- 用户说"对比配置差异"、"diff 配置"
- 用户说"同步到 Git"、"git 提交备份"
- 用户需要管理 `confmirror.yaml` 中的模块定义

## 核心概念

- **配置文件**：`confmirror.yaml`（当前目录或 `-c` 指定）
- **模块**（module）：配置文件中 `modules` 列表的每一项，对应一组要备份的路径或脚本
- **备份根目录**：`settings.backup_root`（默认 `./mirror`），存放备份文件和 `.meta` 元数据
- **元数据**：每个备份文件附带 `.meta` 文件，记录原始权限（mode/uid/gid）
- **差异备份**：默认行为，仅当源文件与备份不同时才覆盖
- **脚本钩子**：模块可配置 `script` 字段，在 backup/restore 时执行自定义脚本

## CLI 命令参考（Agent 友好接口）

所有命令均支持以下全局选项：

| 选项 | 说明 |
|------|------|
| `-c, --config PATH` | 指定配置文件路径 |
| `--format json` | 输出结构化 JSON（推荐 Agent 使用） |
| `--dry-run` | 预览模式，不实际执行 |
| `--yes, --non-interactive` | 跳过所有交互式确认 |

### backup — 备份配置

```bash
# 全量备份所有模块
confmirror backup --format json --yes

# 备份指定模块
confmirror backup -m <module_name> --format json --yes

# 备份指定路径（路径必须属于某个模块）
confmirror backup -p <path> --format json --yes

# 强制覆盖（差异备份时跳过比对）
confmirror backup --force --format json --yes

# 预览模式
confmirror backup --dry-run --format json --yes
```

### restore — 还原配置

```bash
# 全量还原所有模块
confmirror restore --format json --yes

# 还原指定模块
confmirror restore -m <module_name> --format json --yes

# 还原指定路径
confmirror restore -p <path> --format json --yes

# 预览模式
confmirror restore --dry-run --format json --yes
```

> ⚠️ restore 通常需要 root 权限（涉及系统目录如 `/etc`），非 root 运行会打印警告但仍继续。

### diff — 差异对比

```bash
# 对比整个模块
confmirror diff -m <module_name> --format json

# 对比指定路径
confmirror diff -p <path> --format json

# 详细模式（显示文件内容差异）
confmirror diff -m <module_name> --detail --format json
```

### perms — 查看权限

```bash
# 查看所有模块的权限信息
confmirror perms --format json

# 查看指定模块
confmirror perms -m <module_name> --format json

# 查看指定路径
confmirror perms -p <path> --format json
```

### ls — 列出模块

```bash
# 列出所有模块
confmirror ls --format json

# 查看单个模块详情
confmirror ls -m <module_name> --detail --format json
```

### sync — Git 同步

```bash
# 自动 add、commit、push（需先在 confmirror.yaml 中启用 git_auto_commit/git_auto_push）
confmirror sync --format json --yes
```

### global-config-path — 全局配置路径

```bash
# 查看/设置全局默认配置文件路径
confmirror global-config-path get
confmirror global-config-path set <path>
confmirror global-config-path remove
```

## 结构化输出格式（`--format json`）

所有命令在 `--format json` 下返回统一的顶层结构：

```json
{
  "status": "success" | "error",
  "command": "backup" | "restore" | "diff" | ...,
  "module": "ssh",
  // 命令特定字段...
}
```

### `ls` / `perms` 的 data 字段

```json
{
  "status": "success",
  "command": "ls",
  "data": [
    {
      "name": "ssh",
      "type": "path",
      "base_path": "/etc",
      "paths": ["ssh/sshd_config"],
      "exclude_paths": null,
      "script": null,
      "hook_lang": "bash"
    }
  ]
}
```

## Exit Codes

| 码值 | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 配置错误（confmirror.yaml 不存在或格式错误） |
| 2 | 权限错误（restore 时非 root） |
| 3 | 部分失败（某些文件备份/还原失败，但流程继续） |

## 常见工作流

### 工作流 1：备份标准服务配置

1. 确认 `confmirror.yaml` 存在（当前目录或 `-c` 指定）
2. 执行 `confmirror ls --format json` 查看可用模块
3. 执行 `confmirror backup -m <module> --format json --yes`
4. 检查输出 `status` 是否为 `success`

### 工作流 2：比较并还原模块

1. 执行 `confmirror diff -m <module> --format json` 查看差异
2. 分析 `added`（新增）、`deleted`（缺失）、`changed`（变化）列表
3. 如需还原：`confmirror restore -m <module> --dry-run --format json --yes` 预览
4. 确认无误后去掉 `--dry-run` 执行真实还原

### 工作流 3：Git 版本控制备份

1. 确保 `confmirror.yaml` 中 `git_auto_commit: true`
2. 执行备份：`confmirror backup --format json --yes`
3. 同步到远程：`confmirror sync --format json --yes`

### 工作流 4：查看文件权限变化

1. 执行 `confmirror perms -m <module> --format json`
2. 对比 `source`（当前系统状态）和 `meta`（备份记录）的 `mode`/`uid`/`gid`

## 配置文件示例

```yaml
settings:
  name: my-server-configs
  backup_root: ./mirror
  script_hooks_dir: ./script-hooks
  log_dir: ./logs
  git_auto_commit: true
  git_auto_push: false

modules:
  - name: ssh
    base_path: /etc
    paths:
      - ssh/sshd_config
      - ssh/ssh_config

  - name: nginx
    base_path: /etc/nginx
    paths:
      - "*.conf"
      - "conf.d/*"
    exclude_paths:
      - "*.bak"
```

## 反模式

| 错误做法 | 正确做法 |
|----------|----------|
| 解析终端人类可读输出来判断结果 | 始终使用 `--format json` 解析结构化输出 |
| 直接执行 `restore` 不预览 | 先 `--dry-run` 确认影响范围 |
| 假设命令一定成功 | 检查 exit code（0=成功，1=配置错误，2=权限错误，3=部分失败） |
| 忽略 `--yes` 导致交互阻塞 | Agent 场景始终携带 `--yes` / `--non-interactive` |
| 使用绝对路径 `/etc/...` 直接作为模块名 | 模块名是 `confmirror.yaml` 中定义的 `name` 字段 |
