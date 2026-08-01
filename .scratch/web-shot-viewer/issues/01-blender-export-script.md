# 01 — Backend: Blender Export Script

**What to build:** A Python script (`backend/export_shot.py`) that Blender runs headlessly to convert a `.blend` file into `.gltf` format. Takes input `.blend` path and output directory as CLI arguments. Uses `bpy.ops.export_scene.gltf()` with animation and camera export enabled. Returns exit code 0 on success, non-zero on failure (with error message to stderr).

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] `backend/export_shot.py` exists and is callable as `blender --background --python export_shot.py -- <input.blend> <output_dir>`
- [ ] Output directory contains `scene.gltf` + `scene.bin` after successful export
- [ ] Exports all animations (`export_animations=True`)
- [ ] Exports all cameras (`export_cameras=True`)
- [ ] Exits non-zero with stderr message when `.blend` is invalid or missing
- [ ] Integration test: run against a fixture `.blend` (simple cube + camera), assert `.gltf` structure contains `cameras` and `nodes`
- [ ] Test verifies behavior when `.blend` has zero cameras (should still export scene)
- [ ] All variable names use full descriptive words, no abbreviations
