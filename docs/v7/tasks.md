# V7 Tasks — 导出 MP4 + 导出 Blend

| # | 切片 | 依赖 | 验证 | 状态 |
|---|---|---|---|---|
| 1 | 后端导出模块 + 端点（Seam 1） | — | pytest / Blender | ✅ |
| 2 | 前端 Export UI + 文件夹选择（Seam 2） | 1 | 浏览器 | ✅ |
| 3 | 收尾：安装脚本依赖 + 端到端验证 | 1–2 | HITL | ✅ |

## 切片 1：后端导出模块 + 端点

- 新建 `export_video.py`：Blender 渲染每个相机「整段 `min~max` 连续」+「每段 `start~end`」，`imageio-ffmpeg` 合成 MP4，输出 `{相机名}_full.mp4` / `{相机名}_{段名}.mp4`。
- blend 复制逻辑：当前 blend → 目标目录，文件名 `{聊天名称}_{原blend文件名}`。
- `main.py` 端点：`POST /export/mp4`、`POST /export/blend`。
- `requirements.txt` 加 `imageio-ffmpeg`。
- 验证：pytest（复制命名）+ Blender 脚本（MP4 生成 + 命名 + 时长）。

## 切片 2：前端 Export UI + 文件夹选择

- `TopBar`：Edit 和 Settings 之间加 `Export` 按钮 + 下拉（Export MP4 / Export Blend）。
- `showDirectoryPicker` 选目录 → 调后端端点 → 完成提示。
- 验证：浏览器渲染 + 下拉交互；实测 `showDirectoryPicker` 在 Hermes webview 是否可用（不可用则 Electron IPC 或退回固定目录）。

## 切片 3：收尾

- 安装脚本纳入 `imageio-ffmpeg`（+ 其它新依赖）。
- 端到端：真实 blend 导出 MP4 + 复制 blend，人工检查产物。

## 验收标准

1. 顶部栏 Edit 和 Settings 之间出现 Export 按钮，下拉含 Export 1080p MP4 / Export 720p MP4 / Export Blend；
2. Export MP4 弹出系统文件夹选择，选定后导出 `{folder_name}_{blend前缀名}` 文件夹（无 session 时 `{blend前缀名}`），内含每个相机的 `{相机名}_full.mp4` + `{相机名}_{段名}.mp4`；
3. Export Blend 弹出系统文件夹选择，选定后复制当前 blend，文件名 `{folder_name}_{原blend文件名}`（无 session 时原名）；
4. 无段相机跳过；分辨率可选 1080p/720p，帧率沿用 blend；
5. 导出中显示进度胶囊（A/B + 当前文件 + 帧进度），可 ✕ 取消（确认弹窗），刷新页面进度保持；导出中再次导出被弹窗拦截。

## 开发后修复记录（联调迭代）

1. **同步导出 500 → 异步导出**：初版 `POST /export/mp4` 同步渲染（1212 帧 @1080p > 6 分钟）超过前端等待上限报 500。改为返回 `task_id` + 前端轮询 `GET /export/status/{task_id}`；`ExportTask` 内存态记录进度。
2. **逐个合成**：原「全部渲染完再合成」→ 渲染期间文件夹一直空。改为 Blender 每渲完一个文件写 `.done` 标记，主进程轮询到标记即 `compose_single` 合成（渲染完一个出一个文件）。
3. **进度不更新（0/6 Preparing 卡住）**：`_write_task_progress` 只写 `progress.json` 而 `export_status` 读 `task` 字段，渲染阶段前端一直拿到 `current_file=null`/`current_frame=0`。改为直接同步 `task.current_file/current_frame/current_total_frames`；帧进度以块为单位跳变（渲染前写上一块完成帧、渲染后写本块完成帧）。
4. **渲染累积卡死**：Blender 单进程连续渲染 100+ 帧后 CPU 0% 卡死（实测 3~137 帧不定，逐帧 `write_still` 与单次动画渲染都触发，属 EEVEE Next 显存累积）。改为分块渲染（`CHUNK_FRAMES=50`，每块渲染完重启 Blender 进程强制释放资源）——277 帧连渲 6 块不再卡死。
5. **取消导出 + 轮询残留**：新增 `POST /export/cancel/{task_id}`（置 `cancel_requested` + kill 当前 Blender 子进程，被 kill 的块不报错）；`run_export_video` 块间检查取消立即停止，状态 `cancelled`（`_run_export_task` 不覆盖）；前端 ✕ → 确认弹窗 → `cancelExport`；`pollExportTask` 停止条件补 `cancelled`（修复取消后后台仍轮询 `export-status`）。
6. **重复导出拦截**：导出中再次点导出 → 自定义弹窗提示「正在导出，等待结束或取消后可再次尝试」。
7. **自定义弹窗（ui-design 规范）**：新建 `ConfirmDialog`（深色表面 `#181818`、8px 圆角、重阴影、pill 按钮大写+字距、绿 `#1ed760`/红 `#f3727f`），替换系统 `window.confirm/alert`——停止导出确认、重复导出提示（`exportAlert`）、删除相机/删除段确认 3 处；进度提示为椭圆胶囊，放 UploadZone topBar 最右侧。
8. **MP4 灰蒙蒙 → CurveRGB 色彩增强**：均匀天空光场景渲染 PNG 无暗部（实测 122~217 全中灰），三种 view transform + look 均无法造出暗部。渲染时 compositor 加 `CurveRGB` 每通道 S 曲线（0.62→0.42、0.9→0.95）保留色彩拉对比（不可用 `ColorRamp`——`Image→Fac` 转亮度输出黑白）。
9. **命名规则修正**：chat_name 用 session `folder_name`（时间戳）而非 preview 文字；无 session（用户上传的 blend）用 blend 文件名且**不加前缀**（MP4 文件夹 `{blend前缀}`、Blend 保持原名），避免 `scene_v3_scene_v3` 式重复。
