# 01 — 内嵌 Agent 环境 + API Server 启动

**What to build:** 项目具备自包含的 Hermes 生成环境：Mixamo 角色资产就位、项目专属 Hermes 配置目录（含 V2 定制生成 skill）、一条命令启动三个服务（前端/后端/Agent API Server）。使用者无需安装或了解 Hermes——它只是项目依赖。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 复制 3 个 Mixamo FBX（male/female/child）从 test/characters/ 到 assets/characters/
- [ ] 创建 .hermes-home/ 骨架：config.yaml（api_server enabled + port 8643 + DeepSeek provider）
- [ ] 编写 V2 定制 skill（storyboard-scene-generator V2）：
      资产路径指向 assets/characters/、单场景多机位输出约定、
      中间文件收本次生成目录、输出目录由后端运行时传入
- [ ] start.sh 统一管理三进程（前端 5173 / 后端 8000 / Agent 8643）+ 后端健康检查
- [ ] 验证：start.sh 后 GET http://localhost:8643/v1/skills 能看到 storyboard-scene-generator
