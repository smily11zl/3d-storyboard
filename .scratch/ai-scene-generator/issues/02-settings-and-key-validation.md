# 02 — 后端设置接口 + key 验证

**What to build:** 用户可以在 Web UI（或 API）配置生成服务：选择 DeepSeek provider、模型（v4-flash/v4-pro）、推理级别（low/high/max）、输入 API key。保存时后端直接调 DeepSeek 官方接口验证 key 有效性，验证通过后写入项目配置并自动重启 Agent 服务使配置生效。

**Blocked by:** 01 — 内嵌 Agent 环境 + API Server 启动

**Status:** ready-for-agent

- [ ] GET /api/settings 返回当前配置（key 掩码显示）
- [ ] POST /api/settings 接收 provider/模型/推理级别/key
- [ ] key 验证：调 DeepSeek GET /v1/models（200=有效，401=无效提示）
- [ ] 保存：key 写 .hermes-home/.env，模型/推理级别写 config.yaml
- [ ] 保存后自动重启 Agent API Server（kill + 拉起 + 健康检查）
- [ ] 未配置 key 时启动后端标记"未配置"状态供前端引导
