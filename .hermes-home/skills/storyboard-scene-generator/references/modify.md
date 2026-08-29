# 修改流程 — 二次修改

后端指令会说明这是「二次修改」，并提供：修改基础的 script 文件名（当前查看版本对应的 script）和本次要输出的新版本文件名（N 以指令为准）。

**修改基础以指令为准，优先级：用户消息里说的版本 > 用户当前选中的版本 > 最新版本。**
禁止自己用 `search_files` 搜目录、按 mtime 挑「最新」版本；禁止以「保留所有已有相机/内容」为由改用最新版本。

## 第一步：判断修改基础是否可用

先检查指令指定的 script 文件是否存在：

- **script 存在**（AI 生成的版本）→ 走下方「情况 A：基于 script 修改」。
- **script 不存在**（手动保存的版本，只有 blend 没有 script）→ 走下方「情况 B：直接改 blend」。

## 情况 A：基于 script 修改

1. 先读回指令指定的 script 文件（如 `{OUTPUT_DIR}/script_v2.py`），了解现有场景结构（人物、机位、环境、材质）。
2. **只修改用户要求的部分**（换人物 / 调机位 / 改材质 / 移动物体）。
3. 保留未涉及的内容（场景环境、灯光、其他人物和机位）。
4. **区分"扩展镜头段"和"新增相机"**：
   - 用户描述"先…再…"这类顺序运动 → 仍是**一个相机 + 多段**，在同一个相机上扩展时间轴段，不要新增相机对象。
   - 用户明确要求"新增相机/机位"（独立视角）→ 才新增相机对象；用户没提这个新相机从哪里开始，默认从 0 开始（frame 1）。
5. 把改好的脚本写为指令指定的新版本 script 文件名（如 `script_v3.py`），运行它生成新版本 blend（如 `scene_v3.blend`）。
6. **不要覆盖旧的 script/blend**——输出到指令指定的新版本文件名。

**不要**从头重新生成整个场景（会丢失之前已调好的细节）。

## 情况 B：直接改 blend（script 不存在时）

当对应的 script 文件不存在（该版本是手动保存的，只有 blend），用一个**临时 bpy 脚本**直接改 blend。**临时脚本用完即弃，不保存**，也不新建 script_vN.py。

分两步：

### 第 1 步：分析 blend 现状

先用一个脚本打开现有 blend、打印现状，运行后**读它的输出**，理解场景里已有的相机、动画段、约束、角色位置、材质，再决定怎么改。

```python
import bpy

bpy.ops.wm.open_mainfile(filepath="{BLEND_PATH}")

for cam in [o for o in bpy.data.objects if o.type == 'CAMERA']:
    print(f"相机 {cam.name}: 位置{cam.location} 朝向{cam.rotation_euler}")
    ad = cam.animation_data
    if ad and ad.nla_tracks:
        for track in ad.nla_tracks:
            for strip in track.strips:
                print(f"  NLA: {track.name}/{strip.name} frame {strip.frame_start}-{strip.frame_end}")
    for c in cam.constraints:
        print(f"  约束: {c.type} target={c.target.name if c.target else None}")

for obj in bpy.data.objects:
    if obj.type == 'ARMATURE':
        print(f"角色 {obj.name}: 位置{obj.location} 朝向{obj.rotation_euler}")
```

### 第 2 步：增量修改 + 保存

根据用户需求，对 blend 做增量修改（加相机 / 加动画段 / 加约束 / 改材质），**不动未涉及的内容**。

新增相机、动画段、约束的写法，复用 `references/generate.md` 里的「镜头段约定」和「NLA 代码模板」（`add_segment`、TRACK_TO 约束、点积自检等）。改完保存为最新版本：

```python
bpy.ops.wm.save_as_mainfile(filepath="{OUTPUT_DIR}/scene_v{N}.blend")
print("GENERATION_DONE")
```

**注意**：情况 B 不新建 script_vN.py——该版本本来就没有对应 script，保持没有即可。

## 修改后自检

修改后仍需执行 `references/generate.md` 里「步骤 4」的点积自检，验证改动后的相机方向符合预期。

## 修改涉及角色时

换人物 / 移动人物时，参照 `references/generate.md` 里的「角色操作」（角色导入 + 面朝方向）：导入新角色后按需要的位置/朝向摆放，再删除旧角色。

## 修改涉及镜头段时

若修改涉及镜头段的增删或运动调整，参照 `references/generate.md` 里的「镜头段约定」和「NLA 代码模板」，确保：

- 每段仍是独立 Action + 独立 NLA track（一个 track 一个 strip）
- 段之间时间首尾相接、互不重叠
- 简单运动（S）= 2 pose LINEAR；复杂运动（C）= 3+ pose
- 改完清除 active action（`camera_obj.animation_data.action = None`），避免 tweak 层覆盖 NLA 求值
