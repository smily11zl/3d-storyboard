# V7 Design — 技术规格

## 后端 `export_video.py`（Seam 1 核心）

### 输入

- blend 路径、相机列表（`camera_name` + 该相机的段列表）、输出目录、聊天名称、blend 前缀名。

### 渲染流程

1. `bpy` 加载 blend，读出 `scene.render.resolution_x/y`、`scene.render.fps`（沿用，不额外改）。
2. 对每个「有段」的相机：
   - `scene.camera = 该相机对象`；
   - **整段**：`frame_start = min(start) * fps`，`frame_end = max(end) * fps`，逐帧渲染到临时 PNG，合成 `{相机名}_full.mp4`；
   - **每段**：对每段 `frame_start = start * fps`，`frame_end = end * fps`，渲染合成 `{相机名}_{段名}.mp4`。
3. 段间空白（gap）在「整段」里显示前一段最后一帧——渲染时按播放器同规则（gap 帧复用前一有效段的末尾 pose），实现方式在切片 1 落地。

### 合成

`imageio-ffmpeg` 提供 ffmpeg 二进制（`imageio_ffmpeg.get_ffmpeg_exe()`），用 `-framerate {fps} -i frame_%04d.png -c:v libx264 -pix_fmt yuv420p` 合成。

### Blend 复制

把当前 blend 文件复制到目标目录，文件名 `{聊天名称}_{原blend文件名}`。

## 后端 `main.py` 端点

- `POST /export/mp4`：payload = `{ blend, target_dir, chat_name, blend_prefix }` → 调 `export_video.py` 渲染。
- `POST /export/blend`：payload = `{ blend, target_dir, chat_name }` → 复制 blend。

> 注：浏览器 `showDirectoryPicker` 拿到的是目录句柄而非文件路径，后端不能直接写它。约定：后端先写到一个本地临时目录，前端 fetch 产物后写入所选目录（或后端写临时目录、前端把整目录内容搬到所选目录）。

## 前端 `TopBar.tsx`

- Edit 和 Settings 之间加 `Export` 按钮，点击展开下拉：`Export MP4` / `Export Blend`。
- 点任一选项 → `showDirectoryPicker()` 选目录 → 调对应后端端点 → 完成后提示。

## 测试

- Seam 1（后端）：跑 Blender 脚本，断言 MP4 文件存在 + 命名正确 + 时长正确；复制断言文件存在 + 命名 `{聊天名称}_` 前缀。
- Seam 2（前端）：组件渲染 + 下拉打开/选项点击触发。

## 实现后的关键设计决策

1. **渲染与合成分离**：`export_video.py`（Blender 脚本）只渲染 PNG 帧 + 写 `manifest.json`；MP4 合成在宿主进程 `export_video_service.compose_videos` 用 `imageio-ffmpeg` 完成——因为 Blender 内置 Python 无法 import `.venv` 里的 `imageio-ffmpeg`。
2. **后端返回 base64、前端写目录句柄**：`showDirectoryPicker` 拿到的是目录句柄而非路径，后端不能直接写它。约定后端把产物 base64 返回（`/export/blend` 单文件、`/export/mp4` 文件列表），前端 `writeFilesToDirectory` 写进所选目录。
3. **文件夹命名在前端落地**：MP4 导出时 `writeFilesToDirectory(..., subfolderName = `${chatName}_${blendPrefix}`)` 创建命名子文件夹；Blend 导出直接写父目录、文件名带 `{聊天名称}_` 前缀。
4. **聊天名称/blend 前缀来源**：聊天名称取当前 session 的 `folder_name`（时间戳目录名，如 `20260829_152737`）；无 session（用户直接上传的 blend）时为空串。blend 前缀取最新版本的 `filename` 去 `.blend`（fallback `shot`）。
5. **异步导出 + 逐个合成**（V7 联调修复，渲染分钟级）：后端后台任务——`POST /export/mp4` 返回 `task_id`，`GET /export/status/{task_id}` 轮询（`ExportTask` 内存态）；Blender 每渲染完一个文件写 `.done` 标记，主进程轮询到标记就 `compose_single` 合成该文件并 `completed_files += 1`——文件夹里的 MP4 逐个出现。
6. **渲染与合成分离**：Blender 脚本只渲染 PNG 帧（避开 Blender 内置 Python 无 imageio-ffmpeg），合成在 .venv 主进程。
7. **分辨率选项**：`Export 1080p MP4` 沿用 blend 分辨率；`Export 720p MP4` 把 `scene.render.resolution_x` 缩到 1280 宽（保持比例）。
8. **前端逐个写入 + 刷新恢复**：前端轮询 status，逐个 fetch 已完成文件写入目录句柄；`task_id` 存 `localStorage`，刷新后 `restoreExportTask` 恢复进度胶囊（目录句柄丢失需重新选文件夹）。
9. **分块渲染防卡死**：Blender 单进程连续渲染约 100+ 帧后会累积卡死（CPU 0% 等待，实测 3~137 帧都出现过，属 EEVEE Next/显存累积问题，逐帧 `write_still` 和单次动画渲染都会触发）。改为把每个任务的帧范围按 `CHUNK_FRAMES=50` 分块，每块渲染完**重启 Blender 进程**（强制释放资源），全部块渲染完写 `.done` 由主进程逐个合成。动画渲染（`render(animation=True)`）是阻塞的，块内无法逐帧更新进度，故每块**渲染前**写 progress（上一块完成的帧数）、**渲染后**写（本块完成的帧数）——帧进度以块为单位跳变（0→50→100→…），`current_file` 精确到正在渲染的任务。
10. **取消导出**：`POST /export/cancel/{task_id}` 置 `cancel_requested` + `kill` 当前 Blender 子进程（`ExportTask.current_process`）；`run_export_video` 块间检查取消标志立即停止，状态置 `cancelled`（`_run_export_task` 不覆盖）；被 kill 的块不报错。前端进度胶囊的 ✕ → 自定义确认弹窗 → `cancelExport`。
11. **自定义弹窗（ui-design 规范）**：所有确认/提示弹窗用 `ConfirmDialog`（深色表面 `#181818`、8px 圆角、重阴影、pill 按钮大写+字距、主操作绿色 `#1ed760`、危险操作红色 `#f3727f`），替换系统 `window.confirm/alert`——覆盖：停止导出确认、重复导出提示（`exportAlert` 全局状态）、删除相机/删除段确认。进度提示为椭圆胶囊条目，放在 UploadZone topBar 最右侧（与 `export_hash` 短名同行）。
12. **色彩修复（灰蒙蒙）**：渲染输出 PNG 无暗部（均匀天空光场景，实测像素 122~217 全中灰）导致 MP4 灰蒙蒙；三种 view transform + look 对比度变体均无法造出暗部。渲染时启用 compositor：`CurveRGB` 每通道独立 S 曲线（0.62→0.42 压暗部、0.9→0.95 提亮高光），保留色彩同时拉开对比（实测暗部 min 122→63~78，色彩差异度 13→30）。注意不可用 `ColorRamp`（`Image→Fac` 转亮度输出黑白）。
13. **无 session 命名（上传的 blend）**：`chat_name = session?.folder_name || ''`——有 session 时前缀 `{folder_name}_`；无 session（上传 blend）时不加前缀：MP4 文件夹 = `{blend前缀}`、Blend 文件保持原名（后端 `chat_name` 为空时 `filename = source_blend.name`），避免 `scene_v3_scene_v3` 式重复。
