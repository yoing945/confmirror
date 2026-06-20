# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-06-20

### Added

- **`confmirror init [PATH]` 命令** — 一键初始化 ConfMirror 项目结构，生成 `confmirror.yaml`、`mirror/`、`script-hooks/`、`logs/`
- **10 个 CLI 命令**：在原有 9 个命令基础上新增 `init`

### Fixed

- 修复 `pyproject.toml` 中 Black 的 `include` 正则格式错误，使代码格式化工具能正确处理 Python 文件

## [1.0.0] - 2026-05-29

### Added

- **声明式配置备份与还原** — 通过 YAML 配置文件定义备份规则，1:1 镜像系统配置
- **9 个 CLI 命令**：`backup`, `restore`, `diff`, `perms`, `ls`, `sync`, `install-system`, `uninstall-system`, `global-config-path`
- **权限精确还原** — 备份时记录 `mode/uid/gid`，还原时精确恢复（通过 `.meta` 文件）
- **增量备份支持** — 仅备份变更文件，支持按模块选择性还原
- **差异比较** — 对比源文件与备份的内容和元数据差异
- **路径通配与排除** — 支持 `*`/`?` 通配，基于 pathspec 的排除匹配
- **脚本钩子** — 模块可配置 `hook` 和 `hook_lang`，在备份/还原前后自动执行
- **Git 自动提交** — 可选在备份后自动 commit/push 到 Git 仓库
- **多机配置同步** — 通过 `sync` 命令将配置分发到多台服务器
- **系统级安装** — `install-system` 创建 `/usr/local/bin` 包装器，解决 `sudo confmirror` PATH 问题
- **全局配置管理** — 遵循 XDG 规范，支持用户级和系统级默认配置
- **JSON 输出** — 所有命令支持 `--format json`，便于脚本集成
- **Dry-run 模式** — `--dry-run` 预览操作，不实际执行
- **配置文件校验** — 启动时自动校验 YAML 配置结构和必填项
- **日志轮转** — 自动轮转日志文件，防止无限增长

### Changed

- **配置字段命名规范化**：
  - `backup_file_mode` → `mirror_file_mode`
  - `backup_dir_mode` → `mirror_dir_mode`
  - `include_paths` → `paths`
  - `script` → `hook`
  - `parent_path` → `base_path`
  - `script_lang` → `hook_lang`

### Fixed

- 还原时正确识别备份根目录路径
- 提权后正确解析用户目录中的全局配置文件

[1.1.0]: https://github.com/yoing945/confmirror/releases/tag/v1.1.0
[1.0.0]: https://github.com/yoing945/confmirror/releases/tag/v1.0.0
