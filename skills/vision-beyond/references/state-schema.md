# 最小状态协议

默认路径：`~/.codex/vision-beyond/state.json`。可用 `VISION_BEYOND_STATE_PATH` 或 `--path` 指向其他私有位置。

```json
{
  "schema_version": 1,
  "schedule": {
    "report_time": "17:30",
    "timezone": "Asia/Shanghai"
  },
  "profile": {
    "confirmed": false,
    "topics": [],
    "exclude_terms": [],
    "source_preferences": {}
  },
  "scan": {
    "baseline_days": 7,
    "last_success_at": null,
    "fingerprints": []
  }
}
```

## 约束

- 文件权限建议 `0600`，父目录建议 `0700`。
- `last_success_at` 使用带时区 RFC3339。
- `fingerprints` 只含 `source:sha256hex`，最多保留 2000 个。
- 议题和排除词由用户确认后写入。
- 任何原始飞书标识、业务正文、URL、token 或授权材料都视为 schema 违规。
- 只有正式报告成功生成后才更新 `last_success_at`。
