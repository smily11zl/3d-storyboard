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
