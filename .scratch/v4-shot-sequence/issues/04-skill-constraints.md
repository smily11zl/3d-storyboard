# 04 — skill 强约束改造

**What to build:** 改生成 skill，让 AI 生成「相机对象 + 多段组合」：每段一个独立 Action + 每段一个独立 NLA track（禁止一个 track 塞多个 strip），简单运动 2 pose / 复杂 3+ pose，段首尾相接不重叠，支持机位复用。

**Blocked by:** 02 — 多段序列 + 自动播放

**Status:** ready-for-agent

- [ ] SKILL.md 增加「多段序列生成」约束（每段一个 Action + 每段一个独立 NLA track）
- [ ] SKILL.md 明确「简单运动 2 pose / 复杂 3+ pose / 静止 2 相同 pose 跨 N 秒」
- [ ] SKILL.md 明确「段之间时间首尾相接、互不重叠」+「一个相机对象可被多段复用」
- [ ] 手动生成一个多段场景，检查 blend 的 Action / NLA 结构符合约束（一段一 clip）
- [ ] 生成结果能被识别端正确识别多段 + S/C 标记
