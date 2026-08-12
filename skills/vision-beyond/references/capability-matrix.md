# 能力与授权矩阵

始终遵循最小、增量授权。`doctor.py` 只检查授权状态，不发起登录。

| 能力 | 典型只读 scope | 级别 | 降级方式 |
|---|---|---|---|
| 用户身份 | `auth:user.id:read` 或可用用户资料 scope | 核心 | 停止读取 |
| 消息搜索 | `search:message`、`im:message:readonly` | 核心 | 仅报告其他域，声明缺口 |
| 群/私聊上下文 | `im:message.group_msg:get_as_user`、`im:message.p2p_msg:get_as_user` | 推荐 | 未回最高为候选 |
| 消息表情 | `im:message.reactions:read` | 推荐 | 无消费/轻量回应辅助证据 |
| 文档搜索 | `search:docs:read` | 核心 | 无文档候选 |
| 文档打开记录 | `drive:file:view_record:readonly` | 推荐 | 文档消费状态未知 |
| 文档正文 | `docs:document.content:read` 或 `docx:document:readonly` | 推荐 | 只用元信息 |
| 日历 | `calendar:calendar.event:read` | 可选 | 不覆盖日程 |
| 历史会议 | `vc:meeting.search:read` | 可选 | 不覆盖即时/历史会议 |
| 智能纪要 | `vc:note:read` | 可选 | 只保留会议元信息 |
| 妙记 | `minutes:minutes.search:read`、`minutes:minutes.artifacts:read` | 可选 | 不读取妙记产物 |
| 任务 | `task:task:read` | 可选 | 不覆盖任务 |
| 审批任务 | `approval:task:read` | 可选但高价值 | 不覆盖待办/知会 |
| 审批实例 | `approval:instance:read` | 可选 | 不下钻表单与节点 |
| OKR 周期 | `okr:okr.period:readonly` | 推荐 | 工作地图标为临时 |

权限名称以当前 `lark-cli` 返回的 `missing_scopes` 为准；CLI 和租户策略可能变化。新增授权时使用：

```bash
lark-cli auth login --scope "<MISSING_SCOPE>" --no-wait --json
```

授权链接属于临时认证材料，不能进入状态、日志或仓库。认证流程必须遵循当前 `lark-shared` 的二维码与 split-flow 规则。
