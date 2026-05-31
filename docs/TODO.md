# ConfMirror 待办计划

> 按优先级排序，高优先级项阻塞低优先级项的推进。

---

## P0 — 代码质量与基础修复 ✅

**目标**：稳定现有代码，修复已知缺陷，补充测试覆盖。

- [x] 补充单元测试（`tests/` 目录，25 个测试全部通过）
- [x] `restore` 添加 root 权限前置检查（降级为警告，非 root 时打印 `logger.warning` 继续执行）
- [x] 修复已知边界错误处理（3 处裸 `except Exception:` 改为具体异常类型）
- [x] 清理已删除文档的残留引用（项目中无 QWEN.md / DESIGN.md 残留）

---

## P1 — 打包与分发

**目标**：让用户可以通过标准包管理器安装，无需手动克隆。

- [ ] 配置 PyPI 发布流程（`uv build` + `uv publish`）
- [ ] 验证 `uv tool install confmirror` 可用（**首选方式**，uv 自动管理 Python）
- [ ] 验证 `pip install confmirror` 可用（备选方式，依赖系统 Python）
- [ ] README 中补充安装说明，推荐 uv
- [ ] （可选）发布到 Homebrew 等其他包管理器

---

## P2 — Windows 平台支持

**目标**：让工具在 Windows 上可运行，扩大用户覆盖范围。

> 当前代码深度依赖类 Unix 特性（`os.chown`、`os.chmod`、Unix 权限模型、bash 脚本钩子）。

- [ ] 调研 Windows 权限模型（ACL / `icacls` / `Set-FileAcl`）与 Unix `mode/uid/gid` 的映射策略
- [ ] `.meta` 文件格式扩展：支持 Windows 特有的权限字段，或降级为仅记录基础信息
- [ ] `restore.py` 中 `os.chown` / `os.chmod` 改为平台感知实现（Unix 保持现有行为，Windows 使用 ACL 或跳过）
- [ ] `backup.py` 中权限读取改为平台感知（Windows 使用 `pathlib` + `os.stat` 或 `win32security`）
- [ ] 脚本钩子支持 Windows 解释器（PowerShell / CMD），`script_lang` 字段扩展 `"powershell"`、`"cmd"`
- [ ] 路径分隔符统一处理（`pathspec` 在 Windows 上的反斜杠兼容性）
- [ ] CI 中添加 Windows 运行环境测试（GitHub Actions `windows-latest`）

---

## P3 — CLI Agent 化改造

**目标**：让 CLI 本身对 AI Agent 友好，这是别人能方便接入的**前提**。

- [x] 添加 `--format json`：输出结构化结果（`{status, command, module, ...}`）✅
- [x] 添加 `--dry-run`：预览操作不实际执行，避免 Agent 误操作 ✅
- [x] 添加 `--yes` / `--non-interactive`：跳过所有交互式 prompt ✅
- [x] 标准化 exit code：
  - `0` = 成功
  - `1` = 配置错误
  - `2` = 权限错误
  - `3` = 部分失败
  ✅
- [x] 保留人类可读输出作为默认行为，`--format json` 为可选开关 ✅

---

## P4 — MCP Server 支持

**目标**：通过 MCP (Model Context Protocol) 提供标准化的 Agent 集成接口。

- [ ] 调研 `mcp` Python SDK
- [ ] 暴露 MCP Tools：`backup()`, `restore()`, `diff()`, `list_modules()`, `get_perms()`
- [ ] 参数和返回值使用结构化 Schema（无需解析终端输出）
- [ ] 用户配置示例：`confmirror mcp` 作为 stdio server 启动
- [ ] 测试与 Claude Desktop / Cursor / Kimi 的兼容性

---

## P5 — 开源准备（GPL + GitHub）

**目标**：完成许可证和仓库迁移，具备开源条件。

- [ ] 生成 GPL-3.0 `LICENSE` 文件
- [ ] 更新 `pyproject.toml`：`license = {text = "GPL-3.0"}`
- [ ] 迁移远程仓库到 GitHub
- [ ] 更新 README 中的克隆地址和安装说明
- [ ] 检查并移除代码中可能的硬编码个人信息

---

## P6 — Skill 文件

**目标**：为 Claude Code 等工具提供领域特定的 Skill 包装。

- [ ] 创建 `.claude/skills/confmirror/SKILL.md`（或 user-scope skill）
- [ ] 封装常见工作流："备份标准服务配置"、"比较并还原模块" 等
- [ ] 依赖前置条件：**P3 CLI Agent 化完成后才有价值**

---

## P7 — Docker 容器化（可选）

**目标**：支持完全离线或强隔离场景下的部署。

> 由于 `uv tool install` 已能自动管理 Python 解释器，Docker 的优先级大幅降低，仅在以下场景有必要：
> - 完全离线环境（无法下载 uv/Python）
> - 需要与宿主系统强隔离的安全要求
> - 多用户共享同一运行环境

- [ ] 解决容器内路径映射问题（主机 `/etc` → 容器内可访问）
- [ ] 评估方案：
  - A：挂载主机根目录到 `/host`，配置中使用 `/host/etc/...`
  - B：CLI 增加 `--chroot /host` 参数自动映射
  - C：仅用于分发，运行时绑定挂载 `/etc:ro`
- [ ] 编写 `Dockerfile` 和 `docker-compose.yml` 示例
- [ ] 更新 README 中的 Docker 使用说明

---

## 备注

- **P0 是首要阻塞项**：P1~P7 都依赖代码基础稳定。
- **P1 尽早完成**：打包分发越早落地，越早获得真实用户反馈，有利于后续迭代。
- **P2 与 P1 可部分并行**：Windows 适配中的路径分隔符、脚本钩子扩展可与打包工作同步推进。
- **P3 是 Agent 化的基础**：P4（MCP）和 P6（Skill）都依赖 CLI 具备结构化输出和非交互能力。
- **P5 可与 P2/P3 并行**：开源准备（许可证、GitHub 迁移）不阻塞功能开发。
- **P7 保持可选**：`uv tool install` 已覆盖大多数部署场景，无需系统预装 Python，比 Docker 更轻量且无路径映射问题。
