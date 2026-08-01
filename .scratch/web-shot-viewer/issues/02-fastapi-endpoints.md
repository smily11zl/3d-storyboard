# 02 — Backend: FastAPI Endpoints

**What to build:** A FastAPI application serving REST endpoints for `.blend` upload and `.gltf` serving. The upload endpoint receives a `.blend` file, computes its SHA256 hash for deduplication, spawns `export_shot.py` via `asyncio.create_subprocess_exec`, stores the output in `exports/<hash>/`, and returns shot metadata. A metadata endpoint returns cached shot info. Static files for `exports/` are served directly. Disk quota enforces a maximum total size for the exports directory.

**Blocked by:** 01 (Blender Export Script)

**Status:** ready-for-agent

- [ ] `POST /api/shots` accepts multipart form with a `.blend` file
- [ ] Computes SHA256 hash of uploaded file; skips conversion if `exports/<hash>/` already exists
- [ ] Spawns `blender --background --python export_shot.py -- <temp_path> <exports/<hash>/` via `asyncio.create_subprocess_exec`
- [ ] Returns JSON: `{id, hash, gltfUrl, cameras, animations, duration, fps}`
- [ ] Cameras extracted by parsing the exported `scene.gltf` JSON for camera nodes
- [ ] Animations extracted by reading animation clip names and durations from `scene.gltf`
- [ ] Returns error JSON `{error: "message"}` with appropriate HTTP status on failure (invalid file, Blender crash, export failure)
- [ ] `GET /api/shots/{hash}` returns cached shot metadata (same JSON shape as upload response)
- [ ] `GET /static/exports/{hash}/*` serves exported glTF files via FastAPI `StaticFiles` mount
- [ ] Disk quota: max total `exports/` size (configurable via `STORYBOARD_MAX_DISK_MB` env var, default 500). Evicts oldest exports when exceeded.
- [ ] CORS configured for frontend dev server (localhost:5173)
- [ ] Tests: `pytest-asyncio` + `httpx.AsyncClient` — upload returns correct shape, duplicate upload returns cached result without re-conversion, error on non-.blend file, static file serving works, disk quota eviction
- [ ] All variable names use full descriptive words, no abbreviations
