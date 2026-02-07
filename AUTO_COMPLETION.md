# ConfMirror 自动补全功能说明

## 功能介绍

ConfMirror 现在支持智能自动补全功能，包括：

- **命令补全**：输入 `confmirror` 后按 `TAB` 键，自动显示可用的子命令
- **模块补全**：输入 `-m` 或 `--module` 后按 `TAB` 键，自动显示配置文件中定义的模块名称
- **参数补全**：根据当前上下文提供相关的参数选项

## 安装方法

自动补全功能可以通过 Click 框架的内置功能实现，适用于通过 pip 安装或从源码运行的用户。

### 对于 Bash 用户

#### 临时激活（当前会话）
```bash
# 对于 pip 安装的用户
eval "$(_CONFMIRROR_COMPLETE=bash_source confmirror)"

# 对于从源码运行的用户
eval "$(python -m confmirror.cli _CONFMIRROR_COMPLETE=bash_source python -m confmirror.cli)"
```

#### 永久激活
```bash
# 对于 pip 安装的用户 - 添加到 ~/.bashrc
echo 'eval "$(_CONFMIRROR_COMPLETE=bash_source confmirror)"' >> ~/.bashrc
source ~/.bashrc

# 对于从源码运行的用户 - 添加到 ~/.bashrc
echo 'eval "$(python -m confmirror.cli _CONFMIRROR_COMPLETE=bash_source python -m confmirror.cli)"' >> ~/.bashrc
source ~/.bashrc
```

### 对于 Zsh 用户

#### 临时激活（当前会话）
```bash
# 对于 pip 安装的用户
eval "$(_CONFMIRROR_COMPLETE=zsh_source confmirror)"

# 对于从源码运行的用户
eval "$(python -m confmirror.cli _CONFMIRROR_COMPLETE=zsh_source python -m confmirror.cli)"
```

#### 永久激活
```bash
# 对于 pip 安装的用户 - 添加到 ~/.zshrc
echo 'eval "$(_CONFMIRROR_COMPLETE=zsh_source confmirror)"' >> ~/.zshrc
source ~/.zshrc

# 对于从源码运行的用户 - 添加到 ~/.zshrc
echo 'eval "$(python -m confmirror.cli _CONFMIRROR_COMPLETE=zsh_source python -m confmirror.cli)"' >> ~/.zshrc
source ~/.zshrc
```

### 对于 Fish 用户

#### 临时激活（当前会话）
```bash
# 对于 pip 安装的用户
_CONFMIRROR_COMPLETE=fish_source confmirror

# 对于从源码运行的用户
python -m confmirror.cli _CONFMIRROR_COMPLETE=fish_source python -m confmirror.cli
```

#### 永久激活
```bash
# 对于 pip 安装的用户 - 创建补全脚本
mkdir -p ~/.config/fish/completions
_CONFMIRROR_COMPLETE=fish_source confmirror > ~/.config/fish/completions/confmirror.fish

# 对于从源码运行的用户 - 创建补全脚本
mkdir -p ~/.config/fish/completions
python -m confmirror.cli _CONFMIRROR_COMPLETE=fish_source python -m confmirror.cli > ~/.config/fish/completions/confmirror.fish
```

## 使用示例

安装完成后，您可以这样使用自动补全：

```bash
# 补全子命令
confmirror [TAB]  # 显示: backup, restore, perms, ls, diff

# 补全模块名称（假设配置文件中有 sshd, ufw, nginx 模块）
confmirror backup -m [TAB]  # 显示: sshd, ufw, nginx

# 补全参数
confmirror backup --[TAB]   # 显示: --module, --force, --help, --version
```

## 工作原理

自动补全功能通过以下方式实现：

1. **命令补全**：基于 Click 框架的内置命令发现机制
2. **模块补全**：动态读取当前目录下的 `confmirror.yaml` 配置文件，提取模块名称
3. **参数补全**：基于 Click 框架的参数定义

## 注意事项

- 自动补全功能依赖于当前目录下的 `confmirror.yaml` 配置文件
- 如果配置文件不存在或格式错误，模块名称补全可能无法正常工作
- 更改配置文件后，可能需要重启终端或重新加载配置才能看到新的模块名称
- 如果使用的是从源码运行的方式，请确保 `python -m confmirror.cli` 命令可访问
- 确保 confmirror 已通过 `pip install -e .` 或 `pip install .` 安装，以便命令在 PATH 中可用

## 卸载方法

如需卸载自动补全功能，编辑对应配置文件并删除相关行：

- Bash: 编辑 `~/.bashrc`
- Zsh: 编辑 `~/.zshrc`
- Fish: 删除 `~/.config/fish/completions/confmirror.fish`