# V2 Tasks — 任务清单

## 阶段 1 — 基础环境 ✅ 完成

- [x] T1-1 复制 Mixamo 资产到 assets/characters/（3 个 FBX，不含 README/.DS_Store）
- [x] T1-2 创建 .hermes-home/ 骨架（config.yaml: api_server 8643 + DeepSeek provider）
- [x] T1-3 编写 V2 定制 skill（storyboard-scene-generator V2：
       资产路径 assets/characters/、单场景多机位、中间文件收本次目录、
       输出目录由后端运行时传入）
- [x] T1-4 start.sh 三进程管理 + API Server 健康检查
       （env -i 干净环境防 weixin 污染 + --force 绕过 launchd 保护）
- [x] T1-5 验证: API Server 启动、/v1/skills 可见 V2 skill（health 200 ✅）

## 阶段 2 — 后端生成服务（TDD）✅ 完成

- [x] T2-1 agent_service.py: 健康检查 / 停止 / 重启（env -i 干净环境 + --force）
- [x] T2-2 设置接口: GET/POST /api/settings + DeepSeek key 验证
- [x] T2-3 设置保存 → 写 .env/config.yaml → 重启 API Server
- [x] T2-4 生成接口: POST /api/generate（输出目录 + status.json=running）
- [x] T2-5 SSE 流式转发: GET /api/generate/{id}/stream（断开即中断）
- [x] T2-6 完成衔接: scene.blend → export_shot.py（自动重试 1 次）→ status=done
- [x] T2-7 失败处理: status=failed + error（response.failed 事件解析）+ 日志文件
- [x] T2-8 取消: POST /{id}/stop → 中断 + blender 残留清理 → status=cancelled
- [x] T2-9 超时: 10 分钟兜底 → status=failed(timeout) + 残留清理

## 阶段 3 — 前端 ✅ 完成

- [x] T3-1 TopBar（产品名/侧边栏开关/设置入口）
- [x] T3-2 Sidebar（直接上传 / AI 生成 切换）
- [x] T3-3 ChatPanel（聊天样式: 输入框 + 流式日志 + 停止/重试按钮 + 返回）
- [x] T3-4 SettingsModal（provider/模型/推理级别/key + 验证 + 掩码显示）
- [x] T3-5 App.tsx 页面结构重组 + store.ts 扩展
- [x] T3-6 SSE 流式渲染（消息/工具事件区分 + 闭包陷阱修复）
- [x] T3-7 生成完成自动加载场景（done 状态携带 shot 元数据，复用现有加载流程）

## 阶段 4 — 验证与收尾 ✅ 完成

- [x] T4-1 pytest 全量通过（26/26：V1 回归 10 + V2 mock 16）
- [x] T4-2 手动集成验证（真实生成 ✅）：描述 → skill 四步流程 → 双机位 .blend（cam_01/cam_02 + 2 角色）→ 自动导出 → 前端加载 + 摄像机切换
- [x] T4-3 README 更新 + requirements.txt + .gitignore（test/、generate/、.hermes-home 运行时）

## 集成验证中发现并修复的问题

- SSE 断连误取消 → 改为仅显式 stop 取消（断连任务继续，EventSource 可重连）
- export_scene 内 asyncio.run 嵌套（真实事件循环报错）→ 改 async/await
- skill 自检过度耗时（像素级验证）→ 精简为点积验证 + 8 分钟时间预算

## 测试要点（mock 策略）

- agent_service: mock Hermes HTTP 响应（成功/失败/中断）
- 设置: mock DeepSeek /v1/models（200/401）
- 生成: mock SSE 事件流（delta/tool/complete）、mock export_shot 结果
- 超时/取消: mock 慢响应 + 验证 stop 调用 + blender 清理逻辑
