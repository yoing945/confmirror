# 🤖 AI Agent 快速开始

ConfMirror 对 AI Agent 友好，支持结构化 JSON 输出和非交互执行。

## Agent 调用示例

```bash
# 结构化输出（JSON）
confmirror backup --module nginx --format json

# 预览操作（不实际执行）
confmirror backup --module nginx --dry-run --format json

# 非交互模式（跳过所有确认提示）
confmirror backup --yes
confmirror restore --yes

# 组合使用：Agent 安全调用
confmirror backup --module nginx --dry-run --format json
# → 评估影响后，去掉 --dry-run 实际执行
confmirror backup --module nginx --format json
```

## JSON 输出示例

```bash
$ confmirror diff --module nginx --format json
{
  "status": "success",
  "command": "diff",
  "module": "nginx",
  "added": [],
  "deleted": [],
  "changed": [
    {
      "source": "/etc/nginx/nginx.conf",
      "backup": "mirror/etc/nginx/nginx.conf",
      "content_same": false,
      "meta_same": true,
      "unified_diff": ["--- backup: nginx.conf", "+++ source: nginx.conf", "@@ -1 +1 @@", "-old", "+new"]
    }
  ],
  "unchanged": []
}
```

> 💡 **提示**：`--format json` 会自动抑制终端日志输出，确保 stdout 为纯净的 JSON，便于 Agent 解析。
