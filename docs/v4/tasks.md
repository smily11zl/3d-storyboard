# V4 任务清单 — 镜头序列（Shot Sequence）

状态: 进行中
日期: 2026-08-16

依赖图：

```
T1（单段识别地基）
├─ T2（多段序列 + 自动播放）── T4（skill 强约束改造）
└─ T3（并行兼容多轨道）
        └─ T5（轨道模型重构 + 状态可视化 + 边界修复）
```

## T1 — 单段识别地基（sidecar + 段列表 + S/C 标记）✅ 完成

- [x] Blender 脚本读单个相机的 NLA track，写 segments.json（相机名 / 绝对起止时间 / S-C 类型）
- [x] ShotSegment 数据结构定义（camera_name / start_time / end_time / start_pose / end_pose / segment_type）
- [x] 后端读 segments.json 组装 ShotSegment，metadata 含 `segments` 字段
- [x] 前端一级段列表显示单段（相机名 + 时间 + S/C 标记）
- [x] 单元测试 `parse_segments_sidecar(sidecar_json)`（2 pose→S、3+ pose→C）

## T2 — 多段序列 + 自动播放（依赖 T1）✅ 完成

- [x] 后端识别多个段 + 判断 `timeline_mode=sequence`（时间不重叠）
- [x] 前端多段列表（按时间顺序，parse_segments_sidecar 按 start_time 排序）
- [x] 自动序列播放：到段边界自动切下一段的相机（SceneModel useFrame 检查段边界）
- [x] 点击某段 → 跳到该段起点时间 + 切到该段相机（T1 已做）
- [x] 单元测试「时间不重叠 → sequence」+「乱序 → 按时间排序」

## T3 — 并行兼容多轨道（依赖 T1）✅ 完成

- [x] 后端判断 `timeline_mode=parallel`（时间范围重叠，parse_segments_sidecar 已实现）
- [x] 前端多轨道展示（SegmentList 按相机分组，不强制单时间轴）
- [x] 并行 blend 保持手动切换（SceneModel 仅 sequence 触发自动播放）
- [x] 单元测试「时间重叠 → parallel」（T1 已写 2 个 overlap 测试）

## T4 — skill 强约束改造（依赖 T2）✅ 完成

- [x] SKILL.md 增加「多段序列生成」约束（每段一个 Action + 每段一个独立 NLA track）
- [x] SKILL.md 明确「简单 2 pose / 复杂 3+ pose / 静止 2 相同 pose 跨 N 秒」
- [x] SKILL.md 明确「段之间首尾相接不重叠」+「一个相机对象可被多段复用」
- [x] 手动生成验证：用 skill 的 add_segment 模板造 blend，结构符合约束（一段一 clip）
- [x] 生成结果被识别端正确识别多段 + S/C 标记（含静止镜头判 S）

> 注：真正的「AI 按新 skill 生成」需用户在前端聊天生成实测（skill 代码模板正确性已通过脚本验证）。

## T5 — 轨道模型重构 + 状态可视化 + 边界修复（收尾）✅ 完成

- [x] 移除 `timeline_mode`（sequence/parallel 判断），统一「一个相机一个轨道」
- [x] 前端 SegmentList 统一按相机 optgroup 分组（不再区分 sequence/parallel）
- [x] 时间轴全局（时长 = 最长内容总时长），选择相机只切视角、不改时长
- [x] 去掉自动切换相机，纯手动切换（加载后默认第一个相机，下拉框选段才切）
- [x] Free View 状态可视化：生效=蓝 / 未生效=红（锥体+线框）；选中=实线 / 未选中=虚线
- [x] Camera View 边框：生效=蓝 / 未生效=红
- [x] 修复段边界 1 帧 gap：export_shot.py `start_time` 改 `(frame_start-1)/fps`
- [x] 切换聊天自动重转（reload 端点）+ 下拉标签英文 + 生成超时默认 20 分钟
- [x] 验证：前端 tsc exit 0 + 后端 pytest 48 passed + 实际导出段边界 gap=0
