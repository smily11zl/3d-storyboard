# CONTEXT — Storyboard 3D Pipeline

## Domain Glossary

| Term | Definition |
|------|-----------|
| **Shot** | A complete 3D scene produced from an uploaded `.blend` file, containing models, cameras, animations, and lights. |
| **Camera View** | The left viewport locked to a specific camera's perspective. |
| **Free View** | The right viewport with free orbit controls for exploring the scene. |
| **Animation Clip** | A single animation track exported from Blender (may contain skeletal, object, or camera keyframes). |
| **Export** | The output of a `.blend` → `.gltf` conversion, stored under `exports/<hash>/`. |
| **Timeline** | The shared animation playback control (play/pause/frame position), synchronized across both viewports. |
| **Generation** | An AI workflow that turns a text description into a Shot: Hermes Agent generates a `.blend` scene (with multiple camera setups), the backend converts it, and the viewer loads it. |
| **Generation Task** | A single generation run, identified by its timestamped output directory. Only one runs at a time. |
| **Camera Setup (机位)** | One of possibly several cameras inside a generated scene; viewers switch between them via the camera dropdown. |
| **Generation Directory** | `generate/output/<timestamp>/` — the self-contained folder for one generation task (blend file, script, log, status file). |
| **Generation Status** | The lifecycle state of a task recorded in `status.json`: running → done / failed / cancelled. |
| **Shot Metadata** | Scene metadata returned with a done task: glTF URL, camera names, animation names, duration. The frontend loads the scene from it. |
| **Generation Skill** | The editable behavior specification for generation (project `.hermes-home/skills/`). It defines workflow, output conventions, and code standards — editing it changes generated output without code changes. |
| **Embedded Agent Environment** | The project-local Hermes runtime (`.hermes-home/`), fully isolated from any user-installed Hermes. Users never interact with it directly. |
| **Session** | A persistent chat/generation history entry, backed by Hermes's session store (state.db). One session = one generation task = one output folder. |
| **Session History** | The list of past sessions shown in the history dropdown; switching restores that session's chat and scene. |
| **Incremental Edit (二次修改)** | Continuing a session: the agent reads back its `script.py`, edits it, and re-runs to overwrite `scene.blend` — rather than writing a fresh script. |
| **session_id ↔ folder mapping** | The link between a Hermes session UUID and the timestamped output folder name, persisted in `status.json`. |
| **Reasoning (思考/推理)** | The model's internal thinking step, stored per assistant message in Hermes's `reasoning` field. Shown in history as a collapsible "Thinking" block. Not streamed live — only available on history replay. |
| **Shot Segment (镜头段)** | A segment on the timeline that references one camera object and defines its motion over a time range (start pose → end pose + easing + holds). V4's core unit. Distinct from **Shot** (the whole scene). |
| **Pose (姿态)** | A camera's position + orientation at a single moment. A segment's motion is defined by its start pose and end pose. |
| **Simple Segment (S / 可编辑段)** | A shot segment where both channels (position & orientation) are simple: no hard-to-replay constraint, glTF-loadable interpolation, and ≤2 distinct values per channel. Editable. |
| **Complex Segment (C / 自由段)** | A shot segment where either channel is complex: hard-to-replay constraint (FOLLOW_PATH / LIMIT), non-glTF easing (BACK / BOUNCE / ELASTIC), or >2 distinct values (polyline). Not editable via two-pose editing. |
| **Per-channel Classification (分通道判定)** | S/C is decided per channel (position / orientation) separately, then combined: both simple → S, either complex → C. |
| **Constraint (约束)** | A Blender object constraint that drives a transform by rule (e.g. TRACK_TO points the camera at a target). glTF has no constraint semantics, so it's replayed by the frontend or baked. |
| **lookAt 约束系** | TRACK_TO / LOCKED_TRACK / DAMPED_TRACK — orientation = `lookAt(position, target position)`, a deterministic function the frontend can replay. |
| **复制约束系** | COPY_LOCATION / COPY_ROTATION — copy a target's position/rotation, replayable by reading the target node. |
| **Constraint Metadata (约束元数据)** | Per-segment constraint record in the sidecar: type / target / track_axis / up_axis. Used for frontend lookAt replay + V5 constraint editing. |
| ~~Sequence (序列)~~ | **历史术语**：shot segments whose time ranges don't overlap, ordered consecutively on one timeline. 被「一个相机一个轨道」模型替代（V4 T5 轨道模型重构，删除 `timeline_mode`，2026-08）。 |
| ~~Parallel (并行)~~ | **历史术语**：shot segments whose time ranges overlap — rendered as multiple tracks. 同上，被「一个相机一个轨道」模型替代。 |
| **Camera Reuse (机位复用)** | One camera object referenced by multiple shot segments. |
| **Hold (起幅/落幅停留)** | A camera staying still at a segment's start/end, implemented by duplicating the same keyframe pose (doesn't increase pose count). |
| **Easing (缓动)** | Acceleration/deceleration during motion, implemented via keyframe tangents (glTF CUBICSPLINE), not extra keyframes. |
