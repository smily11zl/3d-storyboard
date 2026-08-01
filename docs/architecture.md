# Storyboard 3D Pipeline — Architecture Overview

## What is this?

A full-stack web application for viewing Blender 3D storyboard shots in the browser. Upload a `.blend` file, get an interactive 3D viewer with dual viewports and animation playback — no Blender installation needed on the viewing machine.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Browser (http://localhost:5173)                         │
│  ┌─────────────────────┬──────────────────────────────┐  │
│  │  Camera View        │  Free View                    │  │
│  │  (locked camera)    │  (orbit controls)             │  │
│  │  R3F Canvas         │  R3F Canvas                   │  │
│  └─────────────────────┴──────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Timeline [▶][⏸] ═════════●══════════ 00:03.0    │    │
│  └──────────────────────────────────────────────────┘    │
└────────────┬───────────────────────┬────────────────────┘
             │ POST /api/shots       │ GET /static/exports/
             ▼                       ▼
┌──────────────────────────────────────────────────────────┐
│  FastAPI Backend (http://localhost:8000)                  │
│                                                          │
│  POST /api/shots                                          │
│    │                                                      │
│    ├─ Save .blend to temp file                            │
│    ├─ Compute SHA256 hash (dedup)                         │
│    ├─ Spawn: blender --background --python export_shot.py │
│    ├─ Parse scene.gltf → extract cameras, animations      │
│    ├─ Enforce disk quota (500MB)                          │
│    └─ Return JSON metadata                                │
│                                                          │
│  GET /api/shots/{hash}  → cached metadata                │
│  GET /static/exports/   → StaticFiles serve glTF + .bin  │
└────────────┬─────────────────────────────────────────────┘
             │ subprocess
             ▼
┌──────────────────────────────────────────────────────────┐
│  Blender (headless, 4.4.3)                                │
│  backend/export_shot.py                                   │
│                                                          │
│  bpy.ops.export_scene.gltf(                              │
│    export_format='GLTF_SEPARATE',  # .gltf + .bin        │
│    export_cameras=True,                                   │
│    export_animations=True,                                │
│    export_lights=True,                                    │
│  )                                                        │
│                                                          │
│  Output: exports/<sha256>/                                │
│    ├── scene.gltf    (JSON scene graph)                   │
│    └── scene.bin     (binary: vertices, bones, anim)      │
└──────────────────────────────────────────────────────────┘
```

---

## Directory Map

| Path | Purpose |
|------|---------|
| `backend/main.py` | FastAPI application — upload, dedup, disk quota, metadata |
| `backend/export_shot.py` | Blender CLI script — `.blend` → `.gltf` |
| `backend/tests/` | pytest integration tests (10 total) |
| `frontend/src/App.tsx` | Root layout: TopBar → Viewports → Timeline |
| `frontend/src/store.ts` | Zustand: shot state, playback, camera selection |
| `frontend/src/types.ts` | TypeScript interfaces: `ShotMetadata`, `CameraInfo` |
| `frontend/src/components/UploadZone.tsx` | Drag-and-drop + click upload UI |
| `frontend/src/components/CameraView.tsx` | Left viewport: locked camera + dropdown |
| `frontend/src/components/FreeView.tsx` | Right viewport: orbit + grid + shadows |
| `frontend/src/components/SceneModel.tsx` | Shared GLTF loader + animation mixer |
| `frontend/src/components/Timeline.tsx` | Play/pause + scrub bar + time display |
| `frontend/src/index.css` | Spotify dark theme CSS variables |
| `start.sh` | One-command launcher for backend + frontend |
| `ui-design/DESIGN.md` | Design system source of truth |
| `docs/v1/spec.md` | V1 feature specification |
| `CONTEXT.md` | Domain glossary |
| `test/` | Old project files (pre-web-viewer era) |

---

## Data Flow: Upload a .blend → View in Browser

```
1. User drags .blend onto UploadZone
2. UploadZone calls POST /api/shots (multipart form)
3. Backend saves .blend to temp file
4. Backend computes SHA256 hash
5. If exports/<hash>/ already exists → skip to step 8 (cache hit)
6. Backend spawns: blender --background --python export_shot.py -- <temp> <exports/<hash>/>
7. export_shot.py opens .blend, runs bpy.ops.export_scene.gltf()
8. Backend parses scene.gltf JSON → extracts camera names, animation clips, duration
9. Backend returns JSON: { export_hash, gltf_output_url, cameras, animations, ... }
10. Frontend stores metadata in Zustand
11. CameraView and FreeView both call useGLTF(gltf_output_url)
12. Drei's useGLTF caches the loaded scene → both viewports share one network request
13. CameraView: reads glTF camera node → copies position/rotation/fov to R3F camera
14. FreeView: OrbitControls allows free rotation
15. Timeline: space to play/pause, scrub bar to seek
16. SceneModel: useAnimations creates mixer, syncs time via Zustand
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| `.gltf` (JSON + .bin) not `.glb` | Text-readable JSON for debugging; Three.js GLTFLoader supports both |
| `backend/` + `frontend/` separate dirs | Independent dependency management; extensible for future workers |
| REST API (not WebSocket) | Conversion takes 5-15s; SSE/WS overhead not justified |
| `asyncio.create_subprocess_exec` | Non-blocking Blender call; FastAPI stays responsive |
| `useGLTF` (Drei) for caching | Two Canvas viewports share one GLTF load via Drei cache |
| Zustand (not Redux) | Lightweight; `getState()` works inside `useFrame` without re-renders |
| Hash-based dedup | Same .blend → same export → no re-conversion |
| Disk quota (500MB) | Prevents `exports/` from filling the disk |
| Spotify dark theme | Per `ui-design/DESIGN.md` — near-black, green accent, pill geometry |
| Full variable names, no abbreviations | User requirement: `camera_name` not `cam`, `animation_length_seconds` not `anim_len` |
| `pytest-asyncio` + `ASGITransport` | In-process API testing — no real server needed |

---

## How to Run

```bash
# One command
cd ~/Documents/storyboard-3d-pipeline
./start.sh

# Or manually (two terminals)
# Terminal 1:
source .venv/bin/activate && uvicorn backend.main:application --reload

# Terminal 2:
cd frontend && npm run dev
```

Open `http://localhost:5173`.

### Prerequisites

- **Blender 4.4.3** installed (`/Applications/Blender.app` or in PATH)
- **Python 3.11** (venv at `.venv/`)
- **Node.js** (for `npm`)

### Run Tests

```bash
source .venv/bin/activate
pytest backend/tests/ -v
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, uvicorn |
| Blender Integration | `asyncio.create_subprocess_exec` → `bpy.ops.export_scene.gltf()` |
| Frontend | Vite, React 19, TypeScript |
| 3D Rendering | Three.js, react-three-fiber, @react-three/drei |
| State | Zustand |
| Design | Spotify dark system (CSS custom properties) |
| Testing | pytest, pytest-asyncio, httpx (ASGITransport) |

---

## Related Files

- `docs/v1/spec.md` — V1 feature specification (user stories, implementation decisions)
- `CONTEXT.md` — Domain glossary (Shot, Camera View, Free View, Export, Timeline)
- `.scratch/web-shot-viewer/issues/` — 5 tracer-bullet tickets
