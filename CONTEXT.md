# CONTEXT — Storyboard 3D Pipeline

## Domain Glossary

| Term | Definition |
|------|-----------|
| **Shot** | A complete 3D scene produced from an uploaded `.blend` file, containing models, cameras, animations, and lights. |
| **Camera View** | The left viewport locked to a specific camera's perspective. |
| **Free View** | The right viewport with free orbit controls for exploring the scene. |
| **Animation Clip** | A single animation track exported from Blender (may contain skeletal, object, or camera keyframes). |
| **glTF Export** | The output of a `.blend` → `.gltf` conversion, stored under `exports/<hash>/`. |
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
| **Edit Mode (编辑态)** | The global editing mode entered via the top-bar "Edit" button. UI switches to focused editing: simplified top bar (Discard + "Edit Mode" + Save), chat hidden, center dual viewports kept, bottom shows a timeline (scale + playhead) plus one segment track per camera. |
| **Playhead (播放头)** | The vertical marker on the edit-mode timeline showing the currently viewed frame. Draggable; plays to preview a segment's motion. |
| **Segment Track (段轨道)** | In edit mode, one horizontal lane per camera object at the bottom, holding that camera's segments in time order. Tracks can be added/deleted in edit mode (add = new camera object + empty track + one initial segment; delete = remove the camera object + track + all its segments + its exclusive aim_target, shared targets kept). |
| **Two-pose Editing (两 pose 编辑)** | Editing a simple (S) segment by changing its start/end pose (position + orientation) — drag in viewport + numeric fine-tune, both synced. |
| **Constraint Editing (约束编辑)** | Editing a TRACK_TO segment by moving its target point; orientation recomputes via frontend lookAt. |
| **Static Target (静态目标)** | A TRACK_TO target that is stationary within each segment; the frontend replays orientation via lookAt using **that segment's own target position** (per-segment, from the aim_target animation). Editable (move that segment's target point — other segments unaffected). |
| **Follow (跟随)** | A TRACK_TO target that is an animated object (a moving model). Not supported this version — such segments classify as complex (C). |
| **Versioned Blend (版本化 blend)** | A saved edit writes a new `scene_vN.blend` (N increments from the original `scene.blend`), never overwriting — preserving edit history for manual switching. Chat source only; upload source uses flat files instead. |
| **Upload Source (上传源)** | A `.blend` the user uploaded manually (not AI-generated). Its source and every saved edit live flat under `generate/upload_output/<timestamp>.blend`; each save writes a new file that becomes the new source, so the next edit builds on the last save. Tracked via `source` = `{type:'upload', file:'<timestamp>.blend'}`. |
| **Segment Shift (平移)** | Dragging a segment's middle: start/end move together, duration unchanged (S and C segments alike). |
| **Re-time (重定时)** | Dragging an S segment's edge to change duration: start/end pose values stay, linear interpolation re-runs, speed changes. |
| **Trim (裁剪)** | Dragging a C segment's edge to change duration: the full sampled keyframes are kept intact (non-destructive); rendering and saving filter them to the segment's current range, so dragging back restores the cut frames. |
| **Segment Duration (原始时长)** | The segment's duration at the moment it entered edit mode — the upper bound for dragging. Editable for S segments, read-only for C. |
| **Effective Duration (有效时长)** | The segment's current `end − start`, a derived read-only value shown as `current / original`. |
| **Fixed Timeline Range (固定时间轴范围)** | The edit-mode timeline shows a fixed 10-minute total length at a fixed pixels-per-second ratio, horizontally scrollable; segments lay out by their start/end times, and the effective total duration is marked by a vertical line plus a highlight from 0 to that line. |
| **Export (导出按钮)** | V7 top-bar button between Edit and Settings; its dropdown offers Export MP4 / Export Blend. |
| **Full Shot Export (整段导出)** | Renders one camera's continuous `min(start)~max(end)` range to a single MP4; gaps show the previous segment's last frame. |
| **Segment Export (每段导出)** | Renders each segment of a camera to its own MP4 (the segment's `start~end`). |
| **Blend Export (导出 Blend)** | Copies the currently-viewed blend to the user-chosen folder; filename prefixed with `{Chat Name}_` when there is a chat session, otherwise keeps the original name (uploaded blends get no prefix). |
| **Chat Name (聊天名称)** | The current chat session's `folder_name` (timestamp dir, e.g. `20260829_152737`), used as the export naming prefix. Empty when the shot came from a direct blend upload (no session) — exports then carry no prefix. |
| **Blend Prefix (blend 前缀名)** | The current blend filename minus its extension (e.g. `scene_v3`). |
