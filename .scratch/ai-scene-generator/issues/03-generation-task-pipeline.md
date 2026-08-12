# 03 — 生成任务核心链路

**What to build:** 后端完整生成链路：提交场景描述 → 创建生成任务（时间戳目录 + status.json）→ 向 Agent 发起生成（指令 = 固定前缀 + 本次输出路径 + 用户描述，行为由 skill 决定）→ SSE 流式转发过程 → 完成后自动调现有导出流程转 glTF（失败自动重试 1 次）→ 状态落盘。支持取消（中断 Agent + 清理残留 blender 进程）与 10 分钟超时兜底。

**Blocked by:** 02 — 后端设置接口 + key 验证

**Status:** ready-for-agent

- [ ] POST /api/generate {description} → 创建任务（generate/output/<时间戳>/ + status.json=running）→ 返回 task_id
- [ ] 向 Agent POST /v1/responses：固定前缀 + 输出路径 + 描述，SSE 接收
- [ ] GET /api/generate/{task_id}/stream — SSE 转发 Agent 事件（message.delta/tool.*）
- [ ] 完成后校验 scene.blend 存在 → 调 export_shot.py 转 glTF（失败自动重试 1 次）→ status=done
- [ ] 失败：status=failed + error 信息 + generation.log 落盘
- [ ] POST /api/generate/{task_id}/stop：中断 Agent 会话 + 扫描并 kill 残留 blender 进程（按命令行含本次目录）→ status=cancelled
- [ ] 10 分钟总超时兜底（同取消流程，status=failed timeout）
- [ ] 同时只允许一个生成任务（进行中拒绝新提交）
