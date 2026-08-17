# 03 — 并行兼容（多轨道）

**What to build:** 旧并行 blend（多相机同时、时间重叠）识别为 `timeline_mode=parallel`，前端多轨道展示（保留并行语义、手动切换，不触发自动序列播放）。

**Blocked by:** 01 — 单段识别地基

**Status:** ready-for-agent

- [ ] 后端判断 `timeline_mode=parallel`（多个段的时间范围重叠）
- [ ] 前端多轨道展示（并行段不强制排成单时间轴）
- [ ] 并行 blend 保持手动切换（不触发自动序列播放）
- [ ] 单元测试覆盖「时间重叠 → parallel」
