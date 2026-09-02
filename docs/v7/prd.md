# V7 PRD — 导出 MP4 + 导出 Blend

## Problem

用户编辑好的镜头序列（多相机、多段）只能在线查看，无法导出成视频文件（MP4）保存或分享；也无法方便地把当前 blend 文件复制到指定位置。

## User Stories

1. As a user, I want an Export button between Edit and Settings, so that I can access export options.
2. As a user, I want a dropdown with Export MP4 / Export Blend, so that I can choose what to export.
3. As a user, I want each camera's full continuous shot exported as one MP4, so that I get a whole-shot clip per camera.
4. As a user, I want each segment exported as its own MP4, so that I get per-segment clips.
5. As a user, I want to pick a target folder via a system dialog, so that I control where files land.
6. As a user, I want the export folder named `{聊天名称}_{blend前缀名}`, so that I can identify the output.
7. As a user, I want to export the current blend to a folder with a `{聊天名称}_` prefix, so that I can back up my source file.
8. As a user, I want to choose 1080p or 720p output resolution, so that I can trade quality for speed.
9. As a user, I want a live progress indicator (file count A/B + current file + per-file frame progress) and to see it survive a page refresh, so that I know export status during a long render.
10. As a user, I want to cancel a running export, so that I can stop it early without killing the whole app.
11. As a user, I want to be warned when I try to start a second export while one is running, so that I don't accidentally launch parallel renders.

## Solution

- **Export 按钮**：顶部栏 Edit 和 Settings 之间，点击展开下拉，含 Export 1080p MP4 / Export 720p MP4 / Export Blend。
- **Export MP4**：后端 Blender 无头**异步**渲染（`POST /export/mp4` 立即返回 `task_id`，前端轮询 `GET /export/status/{task_id}`）——对每个相机（无段相机跳过）渲染「整段 `min(start)~max(end)` 连续」+「每段 `start~end`」，**分块渲染**（每块 ≤50 帧重启 Blender 进程，防 EEVEE 累积卡死）+ 每渲完一个文件逐个合成 MP4（`CurveRGB` S 曲线 compositor 拉对比防灰蒙蒙）；前端进度胶囊（UploadZone topBar 最右侧，`Exporting A/B` + 当前文件 + 帧进度）逐个写入所选文件夹，刷新页面进度保持（`task_id` 存 localStorage）；导出中可点 ✕ **取消**（确认弹窗 → kill Blender 子进程），再次导出会被弹窗拦截。
- **Export Blend**：把当前查看的 blend 复制到用户所选文件夹，文件名加 `{聊天名称}_` 前缀。
- **命名**：有 session（聊天生成）→ 文件夹 `{folder_name}_{blend前缀名}`、Blend `{folder_name}_{原blend文件名}`；无 session（上传的 blend）→ 不加前缀（文件夹 `{blend前缀名}`、Blend 原名）。
- **弹窗**：全部自定义（`ConfirmDialog`，ui-design 规范），不用系统弹窗。

## Implementation Decisions（grill-me 结论）

| # | 决策点 | 结论 |
|---|---|---|
| 1 | 文件夹选择 | 系统弹窗（`showDirectoryPicker`） |
| 2 | 整段画面定义 | 每相机 `min(start)~max(end)` 连续（段间空白显示前一段最后一帧） |
| 3 | 视频命名 | 平铺：整段 `{相机名}_full.mp4`，每段 `{相机名}_{段名}.mp4` |
| 4 | 渲染规格 | 沿用 blend 的渲染分辨率 / 帧率 |
| 5 | Export Blend 对象 | 当前查看的 blend |
| 6 | ffmpeg 依赖 | `imageio-ffmpeg`（pip 自带二进制，纳入安装脚本） |
| 7 | 文件夹 / Blend 命名 | 文件夹 `{聊天名称}_{blend前缀名}`；Blend `{聊天名称}_{原blend文件名}` |

## Testing Decisions（seams）

1. **Seam 1 — 后端导出模块（核心）**：新建 `export_video.py`（Blender 渲染整段 + 每段，`imageio-ffmpeg` 合成）+ blend 复制逻辑；测试跑 Blender 脚本断言 MP4 文件生成、命名正确（`{相机名}_full.mp4` / `{相机名}_{段名}.mp4`）、复制断言文件存在 + 命名正确。
2. **Seam 2 — 前端 Export UI**：`TopBar` Export 按钮 + 下拉（Export MP4 / Export Blend）+ `showDirectoryPicker` 选目录 + 调后端两个端点；测试组件渲染 + 下拉交互。

API 两个端点（`POST /export/mp4`、`POST /export/blend`）是 Seam 1/2 之间的薄封装，归入 Seam 1。

## Out of Scope

- 音频导出
- 自定义帧率 / 更高分辨率档位（仅 1080p/720p 两档，帧率沿用 blend）
- 转场效果
- 断点续传（刷新后进度恢复，但目录句柄丢失需重新选文件夹，尚未写入的文件丢失）
