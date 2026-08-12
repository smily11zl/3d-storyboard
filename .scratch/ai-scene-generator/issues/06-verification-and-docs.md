# 06 — 验证与收尾

**What to build:** V2 全量验证与使用者文档：自动化测试全绿（V1 回归 + V2 mock 测试）、手动集成验证清单执行（真实生成一次完整流程）、使用者文档（README 更新：pip 安装 hermes-agent、.env 配置 key、Web UI 引导；gitignore 规则确认）。

**Blocked by:** 05 — 前端生成交互

**Status:** ready-for-agent

- [ ] pytest 全量通过（V1 10 项回归 + V2 新增 mock 测试）
- [ ] 前端构建通过（vite build 无错误）
- [ ] 手动集成验证清单执行：真实生成一次（skill 流程 → 多机位 .blend → 自动转 glTF → 前端展示 → 摄像机切换）
- [ ] 取消/超时/失败路径手动验证一次
- [ ] README 更新：使用者视角（安装依赖 → 配置 key → 使用 AI 生成）
- [ ] .gitignore 确认：.hermes-home/.env、generate/ 被排除
