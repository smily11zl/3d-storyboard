# Storyboard 3D Pipeline — Web Viewer

A web application for viewing Blender 3D storyboard shots directly in the browser. Upload a `.blend` file, and it gets converted to glTF and displayed in an interactive dual-viewport viewer — no Blender installation needed on the viewing machine.

## Features

- **Upload & convert** — drag-and-drop (or click) a `.blend` file; the backend converts it to glTF (`.gltf` + `.bin` + textures) using headless Blender
- **Camera View** — left viewport locked to a scene camera's perspective, with a dropdown to switch between cameras (falls back to a default orbit view when the scene has no cameras)
- **Free View** — right viewport with free orbit controls, ground grid, and gizmo orientation helper
- **Animation playback** — shared timeline across both viewports: play / pause / scrub, with Space shortcut
- **Cache & dedup** — same file (SHA256 hash) is converted only once; hold `Shift` while uploading to force re-conversion
- **Spotify dark theme** — UI styled per `ui-design/DESIGN.md`

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, uvicorn |
| Conversion | Headless Blender 4.4.3 (`bpy.ops.export_scene.gltf`) |
| Frontend | Vite, React, TypeScript |
| 3D Rendering | Three.js, react-three-fiber, @react-three/drei |
| State | Zustand |
| Testing | pytest, pytest-asyncio, httpx |

## Quick Start

Prerequisites: Blender 4.4.3 in PATH, Python 3.11, Node.js.

```bash
# One command — starts backend (port 8000) + frontend (port 5173)
./start.sh
```

Then open http://localhost:5173 and drag a `.blend` file onto the page.

Manual start:

```bash
# Terminal 1 — backend
source .venv/bin/activate
uvicorn backend.main:application --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

## Project Structure

```
storyboard-3d-pipeline/
├── backend/
│   ├── main.py            # FastAPI: upload, dedup, disk quota, glTF serving
│   ├── export_shot.py     # Blender headless script: .blend → .gltf
│   └── tests/             # pytest integration tests
├── frontend/
│   └── src/
│       ├── components/    # UploadZone, CameraView, FreeView, SceneModel, Timeline
│       ├── store.ts       # Zustand state
│       └── types.ts       # Shot metadata types
├── ui-design/DESIGN.md    # Spotify dark design system
├── docs/                  # Architecture + V1 spec
└── test/                  # Legacy storyboard files (pre-web-viewer)
```

## API

```
POST /api/shots?force=true   # Upload .blend, returns shot metadata
GET  /api/shots/{hash}       # Cached shot metadata
GET  /static/exports/{hash}/*  # Served glTF files
```

## Testing

```bash
source .venv/bin/activate
pytest backend/tests/ -v
```

## Notes

- glTF export is not 1:1 with Blender EEVEE rendering — PBR material mapping loses some effects (Sheen, Clearcoat, SSR), and Blender Area lights are not supported by glTF.
- The viewer uses a locally-generated environment light (no external CDN) so material colors and depth read clearly without hard shadows.
