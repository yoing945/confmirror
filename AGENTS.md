# ConfMirror — AI 助手快速指南

声明式系统配置镜像与还原工具。通过 YAML 配置文件定义备份规则，在独立数据仓库中 1:1 维护系统配置的镜像，支持权限/属主精确还原。

## 文档索引

| 文档 | 路径 | 职责 |
|------|------|------|
| 项目说明 | [README.md](README.md) | 功能特性、快速开始、命令参考 |
| 多机管理 | [docs/MULTI_SERVER.md](docs/MULTI_SERVER.md) | 多服务器配置同步策略 |
| 技能定义 | [.agents/skills/confmirror/SKILL.md](.agents/skills/confmirror/SKILL.md) | AI 助手技能说明 |

## 技术栈与运行

- **语言**：Python >=3.9（开发环境 3.13，uv 管理）
- **CLI 框架**：Click
- **配置解析**：PyYAML
- **路径匹配**：pathspec
- **包管理器**：uv
- **代码风格**：Black + isort
- **类型检查**：basedpyright

### 常用命令

```bash
cd /lab/workspace/confmirror

# 运行 CLI
uv run confmirror --help
uv run confmirror backup
uv run confmirror restore --module <name>

# 测试、类型检查与格式化
uv run pytest
uv run basedpyright
uv run black src/
uv run isort src/

# 构建
uv build
```

## 项目结构

```
.
├── archives/              # 历史脚本与提示文件
├── src/confmirror/        # 源代码包
│   ├── cli.py             # CLI 入口与 9 个命令分发
│   ├── backup.py          # 备份逻辑
│   ├── restore.py         # 还原逻辑
│   ├── diff/              # 差异比较（core.py 纯逻辑 + display.py 输出）
│   ├── perms.py           # 权限查看
│   ├── list.py            # 模块列表
│   ├── sync.py            # 配置同步
│   ├── config.py          # YAML 配置加载与校验
│   ├── meta.py            # .meta 元数据读写
│   ├── gitops.py          # Git 自动提交/推送
│   ├── global_config.py   # 全局配置路径管理（XDG 规范）
│   ├── logger.py          # 日志与轮转
│   ├── system_install.py  # 系统级入口安装（解决 sudo PATH 问题）
│   ├── output.py          # 统一输出格式化（JSON/plain）
│   └── utils.py           # 工具函数
├── docs/                  # 补充文档
├── .agents/skills/        # AI 助手技能定义
├── pyproject.toml         # 项目配置、依赖、入口点
├── README.md              # 用户文档
└── LICENSE                # MIT 协议
```

## 架构速查

CLI 入口统一分发至 9 个命令模块，各模块独立处理单一职责。支持 `--format json` 和 `--dry-run` 全局选项。详见源码与 README.md。

## 编码规范

- **格式化**：Black，`line-length = 88`，`target-version = py39`
- **导入排序**：isort，`profile = black`，`multi_line_output = 3`
- **类型检查**：basedpyright，`typeCheckingMode = basic`
- **类型注解**：公共函数与返回值必须标注类型
- **文档字符串**：公共函数与类应包含简要 docstring

## 测试与验证

```bash
uv run pytest        # 146 个测试
uv run basedpyright  # 类型检查
```

## 依赖与禁忌

### 核心依赖
- `PyYAML>=6.0`
- `click>=8.0`
- `pathspec>=0.10`

### 开发依赖
- `pytest>=7.0`
- `black`
- `isort`
- `build`
- `basedpyright>=1.39.6`

### 禁止事项
- **禁止**在 restore 操作中以非 root 身份运行
- **禁止**删除 `.meta` 文件——restore 依赖其还原权限与属主
- **禁止**修改 `__init__.py` 中的 `__all__`（触发 basedpyright warning）

## 注意事项

- **权限差异**：`backup`、`perms`、`ls`、`diff` 普通用户即可；`restore` **必须 root**，且全量 restore 强制交互确认
- **sudo PATH**：`sudo confmirror` 可能找不到命令，使用 `confmirror install-system` 创建 `/usr/local/bin` 包装器
- **元数据**：每个备份文件/目录旁生成同名 `.meta` 文件（`mode/uid/gid/type`），缺失则跳过还原
- **钩子脚本**：模块可配置 `hook` 和 `hook_lang` 字段，工具按对应方式调用，不干预内部逻辑
- **全局配置**：`confmirror global-config-path` 管理默认配置路径，遵循 XDG 规范（`~/.config/confmirror/`）
- **远程仓库**：当前双 remote——`origin`（Gitea 自建）+ `github`（GitHub 镜像）
