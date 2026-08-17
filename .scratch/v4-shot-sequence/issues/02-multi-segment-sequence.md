# 02 — 多段序列 + 自动播放

**What to build:** 一个相机多段（多个 NLA track）能被识别为多个段，`timeline_mode=sequence`，前端显示多段列表，时间轴自动按段顺序播放并在段边界自动切换相机。

**Blocked by:** 01 — 单段识别地基

**Status:** ready-for-agent

- [ ] 后端识别多个段（一个相机多个 NLA track）+ 判断 `timeline_mode=sequence`（时间不重叠）
- [ ] 前端多段列表（按时间顺序，每段显示相机名 + 时间 + S/C）
- [ ] 自动序列播放：到段边界自动切下一段的相机
- [ ] 点击某段 → 跳到该段的起点时间 + 切到该段相机
- [ ] 单元测试覆盖「时间不重叠 → sequence」
