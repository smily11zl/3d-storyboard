# V2 Plan — 实施计划

状态: ✅ 全部完成（2026-08-13）— 实现细节与偏差见 prd.md §6 / design.md §5

## 阶段划分

### 阶段 1 — 基础环境（无 UI）✅
1. assets/characters/：复制 3 个 Mixamo FBX（从 test/characters/）
2. .hermes-home/ 骨架：config.yaml（api_server 8643 端口）+ 目录结构
3. V2 定制 skill：storyboard-scene-generator V2 版
   （更新资产路径/多机位输出约定/中间文件约定/输出目录由后端传入）
4. start.sh：三进程管理（前端/后端/API Server）+ 健康检查
   （env -i 干净环境 + --force 隔离 launchd 环境变量污染）
5. 验证：API Server 启动、/v1/skills 能看到 V2 skill

### 阶段 2 — 后端生成服务（TDD）✅
6. agent_service.py：Hermes API Server 客户端
   - 健康检查 / 重启（env -i + --force，与 start.sh 一致）
7. 设置接口（GET/POST /api/settings）
   - key 验证（DeepSeek /v1/models）→ 写 .env + config.yaml → 重启 API Server
8. 生成接口（POST /api/generate, GET /{id}, GET /{id}/stream, POST /{id}/stop）
   - 输出目录 + status.json 状态机（done 携带 shot 元数据）
   - SSE 转发（response.output_text.delta / tool.* / response.failed）
   - 完成 → export_shot.py 转换（自动重试 1 次）→ glTF 元数据
   - 取消/超时 → cancel_event + blender 残留进程清理
   - 超时 10 分钟兜底（failed("生成超时")）
   - SSE 断连不取消（EventSource 重连续收）

### 阶段 3 — 前端（V2 页面结构）✅
9. TopBar / Sidebar / SettingsModal / ChatPanel 组件
10. App.tsx 页面结构重组（顶部栏 + 侧边栏 + 主内容区）
11. store.ts：sidebarMode/sidebarCollapsed 扩展
12. SSE 流式日志渲染 + 取消/重试按钮（isGenerating 用 ref 防闭包陷阱）
13. 生成完成自动加载场景（status.json done 的 shot 元数据 → store）

### 阶段 4 — 验证与收尾 ✅
14. pytest 全量（26/26：V1 回归 10 + V2 16）
15. 手动集成验证清单执行（真实生成 ✅：公园场景 → 双机位 + 双角色 + 4s 摄像机动画）
16. 更新 CONTEXT.md / ROADMAP / README（使用者文档：pip 安装 + key 配置）

## 依赖顺序

1→2→3→4→5 → 6→7→8 → 9→10→11→12→13 → 14→15→16

（后端不依赖前端，可并行；阶段 2 完成后可用 curl 验证生成链路）
