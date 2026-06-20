# ConfMirror `init` 命令设计文档

## 背景

ConfMirror 当前需要用户手动创建 `confmirror.yaml` 配置文件及 `mirror/`、`script-hooks/`、`logs/` 等目录。新增 `init` 命令可降低初次使用门槛，实现一键初始化基础项目结构。

## 目标

提供 `confmirror init [PATH]` 命令，静默生成最简配置文件及推荐目录结构；若目标目录已存在 ConfMirror 产物，则拒绝并提示用户。

## 非目标

- 不提供交互式向导
- 不预置启用的示例模块（仅保留注释说明）
- 不引入模板文件系统或多模板支持

## 命令接口

```bash
confmirror init [PATH]
```

- `PATH` 可选，默认为当前工作目录
- 继承全局选项：`--format {human,json}`、`--dry-run`、`--yes`
- 无需 `--force`：遇到已存在的 ConfMirror 产物直接拒绝

## 生成内容

在目标目录创建以下文件和目录：

- `confmirror.yaml`：最简配置 + 注释说明
- `mirror/`：镜像根目录
- `script-hooks/`：脚本钩子目录
- `logs/`：日志目录

### `confmirror.yaml` 模板

```yaml
settings:
  name: "<dir_name>"             # 配置集名称，默认当前目录名
  backup_root: "./mirror"        # 镜像根目录
  script_hooks_dir: "./script-hooks"  # 脚本钩子目录
  log_dir: "./logs"              # 日志目录
  log_max_lines: 1000            # 日志最大保留行数
  git_auto_commit: false         # 是否自动提交到 Git
  git_auto_push: false           # 是否自动推送到远程

# 模块定义示例（取消注释后可用）：
# modules:
#   - name: "sshd"
#     paths:
#       - "/etc/ssh/sshd_config"
```

其中 `<dir_name>` 替换为目标目录的目录名。

## 目录非空判定

拒绝条件：目标目录已存在以下任一 ConfMirror 产物：

- `confmirror.yaml`
- `mirror/`
- `script-hooks/`
- `logs/`

`.git/` 等无关文件不影响初始化。若目标目录本身不存在，则自动创建。

## 错误与退出码

| 场景 | 退出码 | 说明 |
|------|--------|------|
| 初始化成功 | 0 | 正常完成 |
| 已存在 ConfMirror 产物 | 1 | 配置/状态错误 |
| 无权限创建文件 | 2 | 权限错误 |
| 部分创建失败 | 3 | 部分失败 |

## 实现结构

- 新增 `src/confmirror/init.py`：暴露 `execute_init(path, dry_run, output_format)` 函数
- `src/confmirror/cli.py`：注册第 10 个命令 `init`
- 新增 `tests/test_init.py`：覆盖核心场景

## 测试计划

- 空目录成功初始化并生成全部文件
- 已存在 `confmirror.yaml` 时拒绝并返回退出码 1
- 已存在 `mirror/` 目录时拒绝
- `--dry-run` 不创建任何文件
- `--format json` 输出正确的 JSON 结构

## 文档更新

- `README.md` 命令参考表增加 `confmirror init [PATH]`
- `README.md` 快速开始可用 `confmirror init` 替代手写 YAML 的说明

## 方案选择

采用方案 A：新增独立 `init.py` 模块。该方案与现有 CLI 命令"一个模块一个职责"的风格保持一致，改动最小，不引入模板分发等额外复杂度。
