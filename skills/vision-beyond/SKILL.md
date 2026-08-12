---
name: vision-beyond
description: "基于飞书 lark-cli，先从身份、OKR、审批、任务与近期活动建立可确认的工作地图，再从消息、会议、纪要和有权限文档中找到视野之外、值得关注的飞书信号，筛出可能影响判断或行动的 Top 5。用户说‘视野之外’‘我漏掉了什么’‘未读未回’‘没参加的会’‘可能没看的文档’或‘飞书信息雷达’时使用。"
---

# 视野之外

## 核心目标

帮用户找到视野之外、值得关注的飞书信号。未读、未回、更新时间和阅读量只负责召回，用户确认的工作地图、责任关系、状态变化和证据强度共同决定排序。

## 开始前

1. 读取当前安装的 `lark-shared`，并按需读取 `lark-im`、`lark-drive`、`lark-doc`、`lark-calendar`、`lark-vc`、`lark-note`、`lark-minutes`、`lark-task`、`lark-approval`、`lark-okr`。
2. 执行 `python3 scripts/doctor.py`。只有用户身份 `verified=true` 才能读取用户数据；某个可选域缺权限时保留降级结果，不能把局部覆盖写成全量巡检。
3. 所有用户历史数据使用 `--as user`。公司飞书、个人飞书及不同 profile 之间不得混用。
4. 本 Skill 只读：不发送或回复消息，不标记已读，不编辑文档，不创建任务，不改日历，不处理或发起审批，不申请会议产物权限。

能力与最小授权见 [references/capability-matrix.md](references/capability-matrix.md)，数据边界见 [references/privacy.md](references/privacy.md)。

## 首次激活

### 1. 配置报告节奏

缺少配置时，只询问报告时间和 IANA 时区。系统时区可以作为建议，最终值由用户确认。用当前 Agent 宿主支持的周期任务能力创建或更新每日巡检；宿主不支持自动任务时，给出手动运行说明，不伪造已创建的调度。

初始化私有状态：

```bash
python3 scripts/state.py init --report-time "17:30" --timezone "Asia/Shanghai"
```

示例时间只展示格式，不能代替用户选择。状态协议见 [references/state-schema.md](references/state-schema.md)。

### 2. 建立工作地图

按 [references/context-profile.md](references/context-profile.md) 读取：

- 当前用户可见身份与租户边界；
- 当前 OKR；缺权限时明确记录缺口；
- 当前审批待办、未读知会及相关任务；
- 最近 14 天用户发送的消息、参与的会议、编辑/评论/打开过的文档；
- 从这些证据归并出的 5–8 个议题草案。

每个议题都包含名称、为什么相关、证据来源、搜索词、置信度和缺失源。把草案交给用户做一次自然语言确认：保留、删除、改名、合并、补充、暂不关注。

工作地图确认前，不执行正式基线报告；用户明确指定的单次查询可以继续。

### 3. 执行 7 天基线

确认工作地图后扫描最近 7 个自然日。成功后记录运行点和不可逆候选指纹。后续每日窗口使用“上次成功运行点 → 本次计划运行点”；固定日报通常表现为前一天同一时刻至当天同一时刻。

时间边界必须由系统时间或 `state.py window` 计算，不能凭模型心算：

```bash
python3 scripts/state.py window
```

## 日常巡检

### 1. 确认身份和窗口

```bash
LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1 \
LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1 \
lark-cli auth status --json --verify
```

只有 `verified=true` 且用户身份可用时继续。状态缺失或损坏时回到首次激活，不用旧报告充当本次结果。

### 2. 采集行动源

审批和任务先进入候选池：

```bash
lark-cli approval tasks query \
  --params '{"topic":"1","page_size":100,"locale":"zh-CN"}' \
  --as user --format json

lark-cli approval tasks query \
  --params '{"topic":"17","page_size":100,"locale":"zh-CN"}' \
  --as user --format json

lark-cli task +get-related-tasks --include-complete=false \
  --as user --format json
```

- `topic=1` 表示当前待办审批；结合审批定义、发起人、当前节点和表单摘要判断行动价值。
- `topic=17` 表示未读知会；旧积压按审批定义和业务对象聚合，只下钻排名靠前的实例。
- 多年未完成任务只有在近期更新、接近截止或关联已确认议题时保留。
- 审批详情仅用于证据核验，禁止调用任何写操作。

### 3. 采集消息

先以工作地图的议题词做窄搜索，再补充 `@我`、私聊和含链接消息。时间使用带时区的 RFC3339：

```bash
lark-cli im +messages-search --as user --query "<TOPIC>" \
  --start "<START>" --end "<END>" --page-size 50 --page-limit 4 \
  --format json --no-reactions

lark-cli im +messages-search --as user --query "" --is-at-me \
  --start "<START>" --end "<END>" --page-size 50 --page-limit 4 \
  --format json --no-reactions

lark-cli im +messages-search --as user --query "" --chat-type p2p \
  --start "<START>" --end "<END>" --page-size 50 --page-limit 4 \
  --format json --no-reactions
```

对可能需要回复的消息，读取同一线程或私聊窗口的后续上下文。分页或线程不完整时，未回状态最高只能为 `candidate`。详细规则见 [references/message-state.md](references/message-state.md)。

广泛召回阶段使用 `--no-reactions` 控制请求量。若已授权 `im:message.reactions:read`，只对高位消息候选补充 reaction 聚合计数：

```bash
lark-cli im +messages-mget --as user \
  --message-ids "<COMMA-SEPARATED-MESSAGE-IDS>" --format json
```

reaction 数量只作为弱关注线索，排序加分最多 3 分，不能单独进入 Top 5。当前用户的 reaction 最多支持“接触过”，不能替代复杂请求的正文回复或任务闭环。字段缺失不构成反向证据。细则见 [references/reaction-signal.md](references/reaction-signal.md)。

### 4. 采集会议与会议产物

- 日历范围：`calendar +agenda --as user --start <START> --end <END>`。
- 已结束会议：`vc +search --as user`，至少带时间范围或参会人条件。
- 排名靠前的会议用 `vc +detail` 获取纪要入口，再按 `note_id`、`minute_token` 路由。
- 妙记无权限时停止下钻；智能纪要与妙记分别标记证据来源。

会议状态只使用可证实语言：

- `not_attended`：参会快照能证明用户没有有效参会记录；
- `no_minutes_view_evidence`：没有证据表明用户看过纪要；
- `not_opened`：仅在接口明确返回用户打开状态时使用。

没有出现在日历中，不能直接推出用户没有参加。

### 5. 采集有权限文档

文档是一等候选源。并行执行“近期更新”和“窗口内新建”两条召回路径。对每个已确认议题先做主题搜索：

```bash
lark-cli drive +search --as user --query "<TOPIC>" \
  --doc-types doc,docx,sheet,bitable,wiki,file --sort edit_time \
  --page-size 20 --format json

lark-cli drive +search --as user --query "<TOPIC>" \
  --created-since "<START_DATE>" --created-until "<END_DATE>" \
  --doc-types doc,docx,sheet,bitable,wiki,file --sort create_time \
  --page-size 20 --format json
```

- `drive +search --as user` 只证明当前身份可发现该对象，无法证明覆盖全部可访问文档。
- `update_time > last_open_time` 可标为“更新后可能未看”；`last_open_time` 缺失或为零且议题高度相关，可标为“未发现本人访问证据”。
- 日期过滤按自然日召回。返回后必须用 `create_time` 在内存中裁剪到精确的 `<START> → <END>` 窗口。
- 缺少打开字段、分页未完成或仅凭搜索缺失，只能标为 `unknown`。
- `--edited-since` 描述用户编辑行为，不能充当“别人最近更新”的全局过滤器。
- 先按工作地图相关性、标题、摘要、创建/更新时间和本人打开时间初排；最多对前 20 条相关文档调用聚合统计：

```bash
lark-cli drive file.statistics get --as user \
  --file-token "<TOKEN>" --file-type "<TYPE>" --format json
```

- 当前自然日优先使用 `uv_today`，较早但仍在窗口内的新建文档使用生命周期 `uv`。`uv` 比 `pv` 更接近独立阅读人数。
- 用户已配置独立阅读人数门槛时遵循用户配置。没有配置时，在同日、同议题候选中做相对排名：至少 5 个候选时，只有独立阅读人数高于同批中位数且位于前 20% 才标为“多人阅读”；样本不足 5 个时要求至少 5 个独立访问者。
- 聚合统计调用返回 `forbidden`、`not found`、文件类型不支持或字段缺失时，不补写热度结论，保留更新时间与本人打开时间证据并降低置信度。
- `file.view_records` 只能作为可选交叉验证，常受文档所有者权限限制；不能把调用失败写成“本人未读”。
- 阅读量本身没有业务价值。候选仍须命中工作地图，并能说明变化、关系和下一步。
- 只有进入高位候选后才读取正文。

### 6. 合并、去重和排序

在内存中以消息、会议、纪要、文档和审批的稳定标识去重；持久化前只保存 SHA-256 指纹。跨来源属于同一变化时合并成一条，保留最强证据和必要链接。

按 [references/ranking.md](references/ranking.md) 评分，并执行三道门槛：

1. 具体改变了什么；
2. 为什么与当前用户有关；
3. 用户现在需要阅读、回复、补会、处理审批，还是可以忽略。

任一问题无法简洁回答时降级或丢弃。

## 输出合同

正式报告只列一个跨来源 Top 5。分类、摘要和统计只能引用这 5 条，不得在后续章节新增第 6 条候选。高价值候选不足时少于 5 条，不凑数。

```text
视野之外｜<START> → <END>
工作地图：<已确认议题；新增议题候选另行标记>

1. 【高｜可能未看｜已确认待回复】一句话说明发生了什么
   与你有关：...
   建议动作：阅读 / 回复 / 补会 / 看纪要 / 处理审批 / 暂不处理
   证据：可点击来源；时间；必要的第二来源
   置信度：高 / 中 / 低

...最多 5 条

覆盖说明：已覆盖域、缺失权限、分页截断、状态不确定性
本次无结果时：本窗口没有足够证据支持打扰你的内容
```

状态语言严格区分：

- “已确认未读”：接口或用户提供了明确阅读状态；
- “可能未读 / 可能未看”：相关且缺少消费证据；
- “已确认待回复”：明确请求，且完整后续上下文中没有用户回复；
- “可能待回复”：存在请求信号，但上下文不完整。

## 成功后写入最小状态

先对稳定标识做不可逆指纹：

```bash
printf '%s' '<SOURCE-STABLE-ID>' | python3 scripts/state.py fingerprint --source message
```

完成报告后再标记成功；失败或覆盖中断不能推进检查点：

```bash
printf '%s\n' '<HEX-FINGERPRINT>' | \
  python3 scripts/state.py mark-success --at "<RFC3339>"
```

## 失败与降级

- 用户认证失败：停止读取，不切换 bot，不使用旧缓存。
- 某业务域缺权限：继续已授权域，并在覆盖说明中列出缺口。
- 消息搜索或文档搜索分页未完成：标记覆盖不完整。
- 会议产物无权限：只保留会议元信息，不申请权限。
- OKR 缺权限：工作地图标记为临时版本，不从群名推断目标。
- 审批知会过多：聚合后只核验高位候选，报告覆盖上限。
- 没有高价值候选：保持安静结论，不用低价值内容填满 Top 5。

## 永久边界

- 不把发送者职级、群规模、消息长度、reaction 数量或文档阅读量单独当作价值。
- 不把 AI 会议摘要未经原始证据核验地写成事实。
- 不把业务正文、人员标识、reaction ID、文档 token、会议 ID、审批实例号或授权材料写入状态、日志、仓库或长期记忆。
- 不声称“扫描了用户所有未读内容”；当前能力本质上是权限感知、议题驱动的高价值召回。
