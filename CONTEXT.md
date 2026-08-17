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
| **Simple Segment (S / 可编辑段)** | A shot segment whose motion has ≤2 distinct keyframe poses (+ easing) — expressible and manually editable. |
| **Complex Segment (C / 自由段)** | A shot segment with >2 distinct keyframe poses — free/composite motion, read-only (not manually editable). |
| **Sequence (序列)** | Shot segments whose time ranges don't overlap, ordered consecutively on one timeline (the V4 target model). |
| **Parallel (并行)** | Shot segments whose time ranges overlap (the current multi-camera model) — rendered as multiple tracks. |
| **Camera Reuse (机位复用)** | One camera object referenced by multiple shot segments. |
| **Hold (起幅/落幅停留)** | A camera staying still at a segment's start/end, implemented by duplicating the same keyframe pose (doesn't increase pose count). |
| **Easing (缓动)** | Acceleration/deceleration during motion, implemented via keyframe tangents (glTF CUBICSPLINE), not extra keyframes. |
