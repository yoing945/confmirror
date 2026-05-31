# ConfMirror 测试规范

> 本文档定义测试编写规则，确保新功能与修复的测试风格一致。

---

## 1. 基础约定

| 项 | 规则 |
|----|------|
| 框架 | pytest |
| 命名 | `tests/test_<模块名>.py` |
| 运行 | `uv run pytest tests/ -q` |
| 静态检查 | `uv run basedpyright src/confmirror/` |

---

## 2. 测试层级

| 层级 | 目的 | 工具/方式 |
|------|------|----------|
| **单元测试** | 纯函数、独立模块的正确性 | 直接调用函数，传临时路径 |
| **集成测试** | 多模块协作链路 | 组合调用 + 临时文件系统 |
| **Smoke 测试** | CLI 命令不因参数/接口错误崩溃 | `click.testing.CliRunner` |

**优先写单元测试，复杂链路补集成测试，CLI 命令必须补 Smoke 测试。**

---

## 3. 隔离原则

- **不碰真实文件系统之外的状态**：不读写 `~/.config`，不操作真实 `/etc`
- **全局配置隔离**：`global_config.py` 的测试必须 monkeypatch `CONFIG_FILE` 到临时路径
- **Logger 隔离**：涉及 logger handler 的测试，每个测试前清理 `confmirror` logger 的 handlers
- **Git 隔离**：gitops 测试在 `tmp_path` 子目录内 `git init`，不碰真实仓库

---

## 4. 文件系统测试

- 用 `tmp_path` fixture（pytest 内置）创建临时目录和文件
- 用 `monkeypatch.chdir(tmp_path)` 切换工作目录
- 路径断言用 `Path.exists()` / `Path.read_text()`，不硬编码绝对路径字符串
- 涉及 `os.chown` 的测试，非 root 环境下用 `monkeypatch.setattr("os.chown", lambda p, u, g: None)` mock

---

## 5. CLI Smoke 测试规范

```
CliRunner 调用命令 → 断言 exit_code → （可选）断言输出包含关键信息
```

- 必须覆盖：帮助、版本、各子命令至少一种调用方式
- 不验证详细输出内容（logger 输出走 stderr，CliRunner 隔离后捕获不稳定）
- 全量操作的交互式 prompt，用 `-m` 或路径参数绕过，不测 prompt 本身
- `global_config_path` 子命令必须隔离用户真实配置

---

## 6. 外部依赖

| 依赖 | 处理方式 |
|------|----------|
| `git` 命令 | 用真实 `subprocess.run`，在 `tmp_path` 内 `git init` |
| `pathspec` | 可测，传临时路径 + 排除模式 |
| 脚本执行 (`run_script`) | 在 `tmp_path` 内写临时脚本，测多语言解释器路径 |
| 网络 | **禁止**。所有测试必须离线可运行 |

---

## 7. 测试结构示例

```python
# 文件：tests/test_foo.py

import pytest
from pathlib import Path

class TestFooFeature:
    def test_happy_path(self, tmp_path):
        """正常场景"""
        ...

    def test_edge_case(self, tmp_path):
        """边界条件"""
        ...

    def test_missing_input(self, tmp_path, caplog):
        """缺失输入时的行为"""
        with caplog.at_level("INFO", logger="confmirror.foo"):
            ...
        assert "预期日志" in caplog.text
```

---

## 8. 覆盖要求

本节的目的是定义**每个模块应该测什么**，而非罗列当前已有多少测试。新增或修改代码时，以此作为测试义务的检查清单。

### 8.1 各模块覆盖目标

| 模块 | 必须覆盖的场景 | 备注 |
|------|----------------|------|
| `config.py` | 有效配置加载、默认值填充、路径标准化、YAML 语法错误、结构错误、非 dict 顶层 | 错误路径统一返回 `None`，不抛异常 |
| `meta.py` | `.meta` 读写、`.dir.meta` 读写、缺失文件、字段解析 | 纯文件 IO，边界容易覆盖 |
| `utils.py` | `should_exclude_path`（含预编译 spec 分支）、`find_matching_module_with_path`、`run_script` 多语言、超时（如有） | 场景杂，按函数拆分测试 |
| `backup.py` | 文件备份、目录备份（含 `.dir.meta`）、差异跳过（内容未变）、排除模式生效、防递归保护、脚本钩子调用 | 目录递归策略有争议，测当前行为即可 |
| `restore.py` | 文件还原、目录还原、`.meta` / `.dir.meta` 权限还原、差异跳过、缺失 `.meta` 的处理、脚本钩子调用 | `os.chown` 非 root 环境需 mock |
| `diff.py` | `compare_content`（内容差异）、`compare_meta`（权限差异）、`same_file`（无差异跳过）、`diff_module` / `diff_paths` 路径构造 | 终端输出（`click.echo`）不测 |
| `cli.py` | 全部 7 个子命令至少一种调用方式、`--config` 传参、`--help` / `--version` | Smoke 级别，不测输出内容 |
| `logger.py` | handler 缓存（不重复添加）、日志轮转、`ColoredFormatter` 格式化、`ModuleLog` 分类 | 每个测试前清理 logger handlers |
| `gitops.py` | 提交成功、提交失败、推送成功、推送失败、未配置 git 用户名 | subprocess 用 mock 或真实 `tmp_path` git 仓库 |
| `global_config.py` | 读取、写入、删除、XDG 路径解析、sudo 环境变量隔离 | 必须 monkeypatch `CONFIG_FILE` |
| `perms.py` | 文件权限读取、目录权限读取、脚本模块的空返回 | **当前缺失，需补** |
| `list.py` | 模块列表、详情输出 | **当前缺失，需补** |

### 8.2 新增功能时的测试义务

- **修改现有模块**：至少覆盖修改引入的新分支（if/else、try/except、循环边界）
- **新增 CLI 命令/选项**：必须补 Smoke test（`CliRunner`，断言 `exit_code`）
- **新增配置字段**：`config.py` 测加载、`backup.py` / `restore.py` 测生效
- **新增脚本语言支持**：`utils.py` `run_script` 测解释器路径解析
- **不引入测试覆盖倒退**：PR 中测试总数不应减少，除非明确删除废弃功能

### 8.3 已知缺口

| 缺口 | 优先级 | 原因 |
|------|--------|------|
| `perms.py` 无测试 | 低 | 纯读取，逻辑极简单 |
| `list.py` 无测试 | 低 | 纯读取，逻辑极简单 |
