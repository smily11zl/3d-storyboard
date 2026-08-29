---
name: storyboard-scene-generator
description: Use when the user wants to generate a 3D Blender scene with characters via text description. Handles FBX character import, simple-geometry environment, multi-camera shot-segment sequences, and saves a .blend for the storyboard-3d-pipeline web viewer. Output directory is provided by the backend at runtime.
---

# 3D Storyboard Scene Generator

生成一个**单场景、镜头段序列**的 .blend 文件（供 web viewer 查看），或对已有场景做二次修改。不渲染视频、不生成 TTS 音频。所有中间文件必须写入本次输出目录内。

## 运行时约定

- 工作目录 = 项目根目录（`pwd` 检测，不要假设绝对路径）
- 角色资产目录 = `assets/characters/`
- **输出目录 + 输出文件名由后端指令提供**：指令里明确写出本次要输出的 script 文件名和
  blend 文件名（如 `script_v3.py` + `scene_v3.blend`，或首次 `script.py` + `scene.blend`）。
  **严格按指令里的文件名输出，不要写死 `scene.blend`**
- 不要在其他位置创建文件（shots/、render/、根目录等一律不写）

## 路由 — 以指令为准，加载对应流程

本次任务是「新创建」还是「修改已有场景」，**完全以后端指令为准**：

- 后端指令说「生成 / 新场景」→ 加载 `references/generate.md`，按其四步流程从零生成
- 后端指令说「二次修改」→ 加载 `references/modify.md`，按其修改流程改已有代码

后端 `generate.py` 已经分好：新会话 = 生成指令，续接已有会话 = 修改指令，并把输出目录写进指令。**不要自己去搜索项目里的 script.py 来判断是生成还是修改**——指令已分好，搜索历史文件只会误判并浪费 token。

## 角色库

三个 Mixamo FBX 角色（各 49 块骨骼，前缀 `mixamorig:`）：

| 文件 | 身高 | rot=0 朝向 | 说明 |
|------|------|-----------|------|
| male_mixamo_stand.fbx | 2m | **-Y** | 成年男性 |
| female_mixamo_stand.fbx | 2m | **-Y** | 成年女性 |
| child_mixamo_stand.fbx | 1m | **-Y** | 小孩 |

角色导入代码与面朝方向见 `references/generate.md`。

## Blender 代码规范

- **引擎:** `BLENDER_EEVEE_NEXT`
- **材质:** 同时设 `diffuse_color` + `Principled BSDF Base Color`
- **帧范围:** `scene.frame_start/end`，不是 `scene.render.frame_end`
- **节点遍历:** 用 `node.type` 不用 `node.name`

## 常见 LLM 错误（生成代码时避免）

| 错误 | 修正 |
|------|------|
| `BLENDER_EEEVEE_NEXT`（typo） | `BLENDER_EEVEE_NEXT` |
| `scene.render.frame_end` | `scene.frame_end` |
| `mat.diffuse_color` only | 加 Principled BSDF `Base Color` |
| `nodes["Background"]` | 按 `node.type == 'BACKGROUND'` 遍历 |
| `scene.eevee.use_ssr/use_gtao` | EEVEE_NEXT 不存在，删掉 |
| 导入 Mixamo FBX 后 fps 被覆盖成 30（时长缩水 20%）| 导入后重新设 `scene.render.fps = 24` |
