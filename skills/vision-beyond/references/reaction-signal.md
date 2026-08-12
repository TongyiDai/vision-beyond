# 表情信号

## 能力事实

`lark-cli` 的消息读取快捷命令默认附加 `reactions: {counts, details}`。明细包含操作者、动作时间和 `emoji_type`，因此可以判断当前用户是否在某条消息上发过表情。需要 `im:message.reactions:read`。

字段缺失有两种可能：消息没有表情，或批量查询失败。必须同时检查 stderr 的 `reactions_batch_query_failed` / `reactions_partial_failed`，不能只看字段是否存在。

## 用途

### 1. 消费证据

当前用户在消息发送后添加了任意 reaction，说明用户至少接触过该消息。阅读状态不再标为“可能未读”，但不能声称用户理解了正文或附件。

### 2. 群体关注

多位相关协作者对同一消息使用表情，可以作为关注度的弱信号。它在价值评分中最多增加 3 分，不能证明内容正确、团队共识或用户态度。

### 3. 分歧与风险线索

`ERROR`、`CrossMark`、`ThumbsDown`、`FROWN`、`ANGRY`、`THINKING` 等可以提示存在异议、疑问或风险。输出语言使用“出现分歧/疑问表情”，不推断个人情绪、关系质量或团队立场。

## 证据优先级

1. 消息正文、线程后续与任务状态；
2. 当前用户 reaction 的操作者与时间；
3. 单纯 reaction 总数。

没有表情不构成任何反向证据。社交表情如笑脸、爱心、鼓掌通常只提供低权重语境，不能单独进入 Top 5。

## 性能策略

广泛召回时使用 `--no-reactions`。只有高位消息候选才用 `+messages-mget` 补充 reaction 计数和线程回复；缺少 reaction 权限不影响主流程。
