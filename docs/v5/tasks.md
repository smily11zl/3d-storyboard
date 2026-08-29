# V5 任务清单 — 手动编辑镜头段 + 回存 blend

状态: 进行中（切片 1-7 完成，已知问题 1/2/4/5/6 已修复，问题 3 后续版本）
日期: 2026-08-21

依赖图：

```
切片1（编辑态入口 + 段轨道展示）
└─ 切片2（段选中 + 侧栏）
   └─ 切片3（两 pose 编辑 + 约束编辑）
      └─ 切片4（新增 + 删除段）
         └─ 切片5（回存 blend）
            └─ 切片6（多 blend 切换）
```

## 切片 1 — 编辑态入口 + 段轨道展示（无依赖）✅ 完成

- [x] 顶栏「编辑」按钮 → 进入编辑态（store 加 `editMode`）
- [x] 编辑态顶栏：放弃 + "Edit Mode" 标题 + Save（脏标记 `dirty`）
- [x] 聊天框收起
- [x] 底部时间轴（刻度 + 播放头 playhead，可拖动 + 播放）
- [x] 底部段轨道：一个相机一条轨道，段块蓝=S / 橙=C（选中深浅留切片 2）
- [x] 点「放弃」退出编辑态，恢复查看态
- [x] 验证：前端 tsc exit 0 + 后端 pytest 48 passed

## 切片 2 — 段选中 + 侧栏（依赖切片 1）✅ 完成

- [x] 左键点选段 → 选中态（深色）
- [x] 右键段 → 菜单（编辑 / 删除）
- [x] 选中 S 段 → 右侧侧栏（属性区占位，编辑操作留切片 3）
- [x] 选中 C 段 → 侧栏（只读信息 +「复杂段不可编辑」提示 + 删除按钮）
- [x] 关闭侧栏 = 取消选中
- [x] 验证：tsc exit 0 + pytest 48 passed

## 切片 3 — 两 pose 编辑 + 约束编辑（依赖切片 2）

- [ ] S 段改起点 pose：点「起点」→ 播放头跳起点帧 → 拖拽相机 + 侧栏数值（双向同步）
- [ ] S 段改终点 pose：点「终点」→ 跳终点帧 → 拖拽 + 数值
- [ ] 画面实时预览（改属性立即反映到视口）
- [ ] 朝向编辑形态切换：线性段→起点/终点朝向角度；TRACK_TO 段→目标点
- [ ] TRACK_TO 段拖拽目标点 → 朝向 lookAt 重算（读约束元数据 target + glTF 节点）
- [ ] 验证：tsc + pytest

## 切片 4 — 新增 + 删除段（依赖切片 3）✅ 完成

- [x] 轨道末尾加段：默认静止段（起点=终点=上一段终点），时长 3 秒可改，朝向继承上一段
- [x] 删除段：右键菜单 + 侧栏删除按钮，删前弹窗确认
- [x] 删除后不补位（留空档，空档期间相机静止）
- [x] 验证：tsc exit 0 + pytest 48 passed

## 切片 5 — 回存 blend（依赖切片 4）✅ 完成

- [x] Save 按钮：有改动才亮（脏标记）
- [x] `POST /api/shots/{hash}/edit`：编辑操作打包 operations JSON → 后端回存
- [x] 后端 Blender 回存脚本 `apply_edit_to_blend`：改关键帧 / 改约束 target / 删段 / 加段 → 另存 `scene_vN.blend`
- [x] 回存后重新导出 → 前端加载新版本
- [x] 纯函数 `parse_edit_request` 单测
- [x] 无损验证：编辑生效 + 其它段不变（回存后重新导出断言）
- [x] 验证：pytest 全绿（56 passed）

## 切片 6 — 多 blend 切换（依赖切片 5）✅ 完成

- [x] `GET /api/shots/{hash}/blends`：扫描文件夹 blend 版本（按版本号排序 + 最新）
- [x] 纯函数 `build_blend_version_list` 单测（3 个）
- [x] 前端聊天区：blend 下拉框（>1 版本时显示，TopBar）
- [x] 切换聊天自动加载最新 blend
- [x] 手动切换其它 blend 版本
- [x] 验证：tsc exit 0 + pytest 59 passed

## 切片 7 — 存储层重构 + 上传源扁平化 ✅ 完成

- [x] `exports/<hash>/` 回归纯渲染缓存（gltf/bin/metadata，不再存 blend）
- [x] 源 blend 统一管理：聊天源 `output/<folder>/`（scene_vN 版本化），上传源 + 保存输出扁平 `upload_output/<时间戳>.blend`
- [x] `source` 字段统一：upload 用 `file`、chat 用 `folder`
- [x] 保存 = 生成新 blend 成为新源（二次编辑不丢第一次编辑）
- [x] 缓存命中补回源文件（删源重传自动恢复；兼容旧 file/folder 字段）
- [x] 验证：pytest 64 passed

## 已知问题

1. ~~**编辑态与保存后不一致**~~ ✅ 已修复，定位到多个根因：
   - TRACK_TO 约束丢失（`export_shot.py` 漏写 `orientation_mode`）
   - 关键帧插值残留 BEZIER（`apply_edit.py` insert 引用失效）
   - C 段被简化成 S（保存只写首尾，改为 C 段逐帧复刻完整采样点）
   - 旧缓存缺 `orientation_mode`（前端显示 follow 但保存默认 interpolate，前后端加兜底推导）
   - follow/interpolate 段级混用（TRACK_TO 约束是相机级，改为约束 influence 动画 + export 读 influence 判定）
   - 复杂段朝向 X/Y 互换（`rotation_euler` 按 intrinsic 读写但 Blender 求值是 extrinsic，多轴朝向翻车；保存/导出端对称改为 extrinsic `mathutils.Euler('XYZ')`）
2. ~~**片段类型误判为复杂段**~~ ✅ 已修复（同 BEZIER 残留根因）
3. **缺手动拖动交互**：镜头目前只能通过数值编辑变化，缺手动拖动等高效交互手段（后续版本）。
4. ~~**编辑模式切换清空聊天历史**~~ ✅ 已修复（ChatPanel 编辑模式卸载丢 useState，改始终挂载 + CSS 隐藏）
5. ~~**重复选择同一聊天版本下拉消失**~~ ✅ 已修复（loadShotIntoViewer 清空 blendVersions 后主动重新加载）
6. ~~**版本下拉样式不统一**~~ ✅ 已修复（原生 select 改自定义 BlendVersionDropdown，与 HistoryDropdown 同风格）
