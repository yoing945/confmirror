# ConfMirror 项目开发指南

## 项目概述

ConfMirror 是一个基于 Git 的声明式系统配置镜像与还原工具，旨在安全可靠地备份和还原系统配置文件。该项目具有以下特点：

- **安全可靠**：完整保留文件权限、属主、类型，支持精确还原
- **声明式管理**：通过 YAML 配置文件定义备份规则，可版本化、可复用
- **Git 原生集成**：备份结果即 Git 仓库，天然支持历史追溯、差异对比、远程同步
- **轻量无侵入**：不修改原系统目录，仅在独立数据仓库中维护镜像
- **生产就绪**：支持交互确认、分级日志、错误恢复，避免误操作

### 技术栈

- **Python 3**：主要编程语言
- **Click**：命令行界面框架
- **PyYAML**：YAML 配置文件解析
- **标准库**：pathlib、logging、subprocess 等

### 项目架构

项目分为两个部分：
1. **工具仓库**（confmirror/）：提供通用逻辑的 Python 包
2. **数据仓库**：存储特定环境的配置镜像（每个服务器/环境一个）

## 低耦合设计

ConfMirror 采用低耦合设计，与 Git 操作完全解耦，支持多种 Git 工作流：

- **Git 功能独立**：Git 的 submodule、sparse-checkout、branch 等功能可单独使用
- **灵活部署**：支持完整克隆、部分检出、多仓库管理等多种部署方式
- **兼容性好**：无论使用哪种 Git 策略，confmirror 都能在当前目录正常工作
- **扩展性强**：用户可根据需要自由选择 Git 工作流，不影响工具功能

## 项目结构

```
confmirror/
├── pyproject.toml          # 项目配置文件
├── README.md              # 项目文档
├── script.sh              # 示例脚本
├── example/
│   └── confmirror.yaml    # 示例配置文件
└── src/
    └── confmirror/
        ├── __init__.py
        ├── backup.py       # 备份逻辑实现
        ├── cli.py          # 命令行接口
        ├── config.py       # 配置文件加载
        ├── core.py         # 核心公共函数
        ├── gitops.py       # Git 操作封装
        ├── logger.py       # 日志系统
        ├── meta.py         # 元数据管理
        ├── restore.py      # 还原逻辑实现
        └── utils.py        # 工具函数
```

## 核心功能

### 1. 配置管理

项目使用 `confmirror.yaml` 作为配置文件，定义备份规则：

```yaml
metadata:
  name: "web-server"             # 可选，默认为当前目录名
  backup_root: "./mirror"        # 镜像根目录
  script_hooks_dir: "./script-hooks"    # 脚本钩子目录
  log_dir: "./logs"              # 日志目录
  git_auto_commit: true          # 是否自动提交到 Git
  git_auto_push: false           # 是否自动推送到远程

modules:
  - name: "sshd"
    paths:
      - "/etc/ssh/sshd_config"
```

### 2. 备份功能

备份过程会：
- 复制指定路径的文件/目录到镜像目录
- 为每个备份文件生成对应的 `.meta` 文件存储权限信息
- 支持脚本钩子进行自定义备份逻辑
- 自动提交到 Git 仓库（可选）

### 3. 还原功能

还原过程需要 root 权限，会：
- 从镜像目录读取文件
- 使用 `.meta` 文件恢复原始权限、属主等属性
- 支持模块化或按路径精确还原

## 开发规范

### 代码风格

- 使用 Black 格式化代码（line-length = 88）
- 使用 isort 管理导入排序
- 遵循 PEP 8 Python 代码规范
- 函数和类应包含适当的文档字符串

### 测试

项目使用 pytest 进行测试，开发时应：
- 为新功能编写单元测试
- 确保现有测试用例通过
- 在提交前运行所有测试

### 依赖管理

- 主要依赖：PyYAML, Click
- 开发依赖：pytest, black, isort, build
- 通过 pyproject.toml 管理依赖

## 构建和运行

### 安装

```bash
pip install -e .
```

这将安装 confmirror 作为可执行包，提供 `confmirror` 命令。

### 命令行接口

```bash
# 全量备份
confmirror backup

# 还原配置
confmirror restore
```

### 开发模式运行

```bash
# 直接运行 Python 模块
python -m confmirror.cli backup

# 或者直接运行脚本
./confmirror backup
```

## 关键实现细节

### 元数据管理

每个备份文件都会生成一个同名的 `.meta` 文件，存储以下信息：
- mode: 文件权限（如 644）
- uid: 所有者用户 ID
- gid: 所有者组 ID
- type: 文件类型（file/dir）

### 日志系统

- 日志文件位于 `./logs/{name}.log`（若未指定文件名，则使用 settings.name）
- 同时输出到控制台和文件
- 包含时间戳和日志级别

### Git 集成

- 自动添加更改的文件到暂存区
- 提交消息格式为 "Backup by confmirror: {配置集名称}"
- 可选择是否自动推送至远程仓库

## 未来发展方向

根据项目文档，可能的改进方向包括：
- 完善备份和还原的具体实现
- 增强错误处理和恢复机制
- 添加更多模块化操作选项
- 改进性能和用户体验