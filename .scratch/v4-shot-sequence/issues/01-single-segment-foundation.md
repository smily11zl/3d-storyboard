# 01 — 单段识别地基（sidecar + 段列表 + S/C 标记）

**What to build:** 上传一个 blend 后，系统能识别出相机动画段并展示。Blender 导出脚本读相机的 NLA strips，写出 `segments.json` sidecar（含相机名、绝对起止时间、S/C 类型）；后端读 sidecar 组装成 ShotSegment 列表放进 shot metadata；前端用一级段列表展示（相机名 + 起止时间 + S/C 标记）。

**Blocked by:** None — 可立即开始

**Status:** ready-for-agent

- [ ] Blender 脚本读单个相机的 NLA track，写 segments.json（含相机名 / 绝对起止时间 / S-C 类型）
- [ ] ShotSegment 数据结构定义（camera_name / start_time / end_time / start_pose / end_pose / segment_type）
- [ ] 后端读 segments.json 组装 ShotSegment，metadata 含 `segments` 字段
- [ ] 前端一级段列表显示单段（相机名 + 时间 + S/C 标记）
- [ ] 单元测试 `parse_segments_sidecar(sidecar_json)`（mock sidecar 覆盖 2 pose→S、3+ pose→C）
