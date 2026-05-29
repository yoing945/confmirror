# ConfMirror — AI 助手快速指南

声明式系统配置镜像与还原工具。通过 YAML 配置文件定义备份规则，在独立数据仓库中 1:1 维护系统配置的镜像，支持权限/属主精确还原。

## 文档索引

| 文档 | 路径 | 职责 |
|------|------|------|
| 项目说明 | [README.md](README.md) | 功能特性、快速开始、命令参考、多机管理策略 |

## 技术栈与运行

- **语言**：Python 3.13（uv 管理，见 `~/.config/uv/.python-version`）
- **CLI 框架**：Click
- **配置解析**：PyYAML
- **路径匹配**：pathspec
- **包管理器**：uv
- **代码风格**：Black + isort

### 常用命令

```bash
cd /lab/workspace/confmirror
source .venv/bin/activate

# 运行 CLI
confmirror --help
confmirror backup
confmirror restore --module <name>

# 测试与格式化
pytest
black src/
isort src/
```

也可通过 uv 直接运行（无需手动激活）：
```bash
uv run confmirror backup
uv run pytest
```

## 项目结构

```
.
├── archives/              # 历史脚本与提示文件
├── src/confmirror/        # 源代码包
│   ├── __init__.py
│   ├── cli.py             # CLI 入口与命令分发
│   ├── backup.py          # 备份逻辑
│   ├── restore.py         # 还原逻辑
│   ├── diff.py            # 差异比较
│   ├── perms.py           # 权限查看
│   ├── list.py            # 模块列表
│   ├── config.py          # YAML 配置加载与校验
│   ├── meta.py            # .meta 元数据读写
│   ├── gitops.py          # Git 自动提交/推送
│   ├── global_config.py   # 全局配置路径管理
│   ├── logger.py          # 日志与轮转
│   └── utils.py           # 工具函数
├── pyproject.toml         # 项目配置、依赖、入口点
└── README.md              # 项目文档
```

## 架构速查

CLI 入口统一分发至 backup / restore / diff / perms / list / gitops 等功能模块，各模块独立处理单一职责。详细流程与命令设计见源码与 README.md。

## 编码规范

- **格式化**：Black，`line-length = 88`，`target-version = py38`
- **导入排序**：isort，`profile = black`，`multi_line_output = 3`
- **类型注解**：函数参数与返回值尽量标注类型
- **文档字符串**：公共函数与类应包含简要 docstring

## 测试与验证

```bash
pytest
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

### 禁止事项
- **禁止**卸载或覆盖系统预装的 Python 3.10（`python3` 命令保持系统默认）
- **禁止**在 restore 操作中以非 root 身份运行
- **禁止**删除 `.meta` 文件——restore 依赖其还原权限与属主

## 注意事项

- **权限差异**：`backup`、`perms`、`ls`、`diff` 普通用户即可；`restore` **必须 root**，且全量 restore 强制交互确认
- **元数据**：每个备份文件/目录旁生成同名 `.meta` 文件（`mode/uid/gid/type`），缺失则跳过还原
- **脚本钩子**：模块可配置 `script` 字段，工具以 `bash <script> backup|restore` 方式调用，不干预内部逻辑
- **全局配置**：`confmirror global-config-path` 管理默认配置路径，遵循 XDG 规范（`~/.config/confmirror/`）
