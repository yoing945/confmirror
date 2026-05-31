# 多机配置管理策略

confmirror 支持多种方式管理多台服务器的配置备份。

## 1. 独立仓库管理

为每台服务器创建独立的配置仓库，实现完全隔离。

```
config-server1/
├── confmirror.yaml
├── mirror/
├── script-hooks/
└── logs/

config-server2/
├── confmirror.yaml
├── mirror/
├── script-hooks/
└── logs/
```

## 2. 单一仓库管理

使用一个仓库管理所有服务器配置，通过 Git 的 sparse checkout 实现每台服务器只拉取自己的配置。

```
backup-repo/
├── server1/
│   ├── confmirror.yaml
│   ├── mirror/
│   └── script-hooks/
├── server2/
│   ├── confmirror.yaml
│   ├── mirror/
│   └── script-hooks/
└── shared/
    └── common-scripts/
```

### 配置 sparse checkout

```bash
git clone <repository-url> .
git config core.sparseCheckout true

# 编辑 .git/info/sparse-checkout
/server1/*
/shared/*

git read-tree -m -u HEAD
```
