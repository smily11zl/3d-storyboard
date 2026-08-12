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
