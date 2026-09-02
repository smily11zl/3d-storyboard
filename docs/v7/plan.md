# V7 Plan — 导出 MP4 + 导出 Blend

## 决策记录（grill-me + grill-with-docs）

术语已同步进 `CONTEXT.md`：`Export`（原 glTF 导出一条改名为 `glTF Export`）、新增 `Export`（导出按钮）/ `Full Shot Export` / `Segment Export` / `Blend Export` / `Chat Name` / `Blend Prefix`；顺带修正 V6 过时定义（`Trim` 非破坏性、`Fixed Timeline Range` 像素比例滚动）。

| # | 决策点 | 结论 |
|---|---|---|
| 1 | 文件夹选择 | 系统弹窗（`showDirectoryPicker`） |
| 2 | 整段画面定义 | 每相机 `min(start)~max(end)` 连续（含空白，空白显示前一段最后一帧） |
| 3 | 视频命名 | 平铺：整段 `{相机名}_full.mp4`，每段 `{相机名}_{段名}.mp4` |
| 4 | 渲染规格 | 沿用 blend 分辨率 / 帧率 |
| 5 | Export Blend 对象 | 当前查看的 blend |
| 6 | ffmpeg 依赖 | `imageio-ffmpeg`（纳入 requirements / 安装脚本） |
| 7 | 命名来源 | 文件夹 `{聊天名称}_{blend前缀名}`；Blend `{聊天名称}_{原blend文件名}` |

## 实现计划

### 后端

1. 新建 `export_video.py`：加载 blend → 对每个相机（有段的）切 `scene.camera` → 渲染「整段连续」+「每段」到临时帧序列 → `imageio-ffmpeg` 合成 MP4 → 输出 `{相机名}_full.mp4` / `{相机名}_{段名}.mp4`。
2. 新建 blend 复制逻辑：复制当前 blend 到目标目录，文件名 `{聊天名称}_{原blend文件名}`。
3. `main.py` 新增端点：`POST /export/mp4`（blend + 目标目录 + 聊天名称）、`POST /export/blend`。
4. 依赖：`requirements.txt` 加 `imageio-ffmpeg`。

### 前端

5. `TopBar.tsx`：Edit 和 Settings 之间加 `Export` 按钮 + 下拉（Export MP4 / Export Blend）。
6. 文件夹选择：`showDirectoryPicker` 拿目录句柄 → 调后端导出到临时目录 → 前端把产物写入选定目录（`showDirectoryPicker` 在 Hermes webview 是否可用需实测，不可用则走 Electron IPC 或退回固定目录）。

## 切片顺序（供 to-tickets 拆票参考）

1. 后端：`export_video.py` 渲染 + 合成 + blend 复制 + 端点（Seam 1，先整段后每段）
2. 前端：`TopBar` Export 按钮 + 下拉 + 文件夹选择（Seam 2）
3. 收尾：安装脚本依赖 + 端到端验证
