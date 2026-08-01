# V1 — Web 3D Shot Viewer

## Problem Statement

用户在 Blender 中创建了 3D 分镜场景（storyboard shots），目前只能通过命令行渲染 PNG/MP4 来查看结果。每次想看不同角度或回放动画都需要重新渲染，无法在浏览器中交互式地查看 3D 场景。

## Solution

一个 Web 应用，用户拖拽上传 `.blend` 文件，后端通过 Blender 无头导出为 `.gltf` 格式，前端用 Three.js 双视口展示：左侧 Camera View（锁定场景摄像机视角）、右侧 Free View（自由轨道旋转），共享动画时间轴支持播放/暂停/帧拖动。

## User Stories

1. As a storyboard artist, I want to drag a `.blend` file onto a web page, so that I can view my 3D shot without opening Blender.
2. As a storyboard artist, I want to see the scene from the camera's perspective (Camera View), so that I can verify what the final render will look like.
3. As a storyboard artist, I want to freely orbit around the scene (Free View), so that I can inspect character positions and set dressing from any angle.
4. As a storyboard artist, I want both views to share a single timeline, so that pausing at a specific frame shows both views at the same moment.
5. As a storyboard artist, I want playback controls (play/pause/scrub), so that I can review the animation at my own pace.
6. As a storyboard artist, I want to switch between cameras when the scene has multiple, so that I can check every camera angle.
7. As a storyboard artist, I want the page to still show a default view when the `.blend` has no camera, so that I don't see a blank screen.
8. As a storyboard artist, I want the UI to follow the project's Spotify dark design system, so that it feels consistent with the rest of the project.
9. As a storyboard artist, I want the `.gltf` export to be cached by file hash, so that uploading the same file twice doesn't trigger a slow re-conversion.
10. As a storyboard artist, I want to see a clear error message if conversion fails, so that I know what went wrong.
11. As a storyboard artist, I want the page to show progress while converting, so that I know something is happening during the 5-15 second wait.
12. As a storyboard artist, I want the 3D scene to have environment lighting and a ground grid, so that I can perceive depth and spatial relationships.
13. As a storyboard artist, I want to see shadows in the 3D view, so that character positioning relative to the environment is clear.

## Implementation Decisions

### Architecture

- **Monorepo with `backend/` and `frontend/`** — separate directories for independent dependency management and future extensibility.
- **REST API** — `POST /api/shots` (upload) and `GET /api/shots/{id}` (metadata). Simple, no WebSocket/SSE overhead.
- **Blender child process** — `asyncio.create_subprocess_exec` for non-blocking conversion. Single-file export script: `backend/export_shot.py`.

### Conversion Strategy

- Pure `bpy.ops.export_scene.gltf()` with `export_animations=True`, `export_cameras=True`. No pre-processing, no material baking.
- Error on missing cameras handled gracefully — frontend falls back to default orbit view.

### Storage

- `exports/<sha256_hash>/` — hash-based deduplication. Same `.blend` = same export.
- Disk quota — max 500MB total. Oldest exports evicted when exceeded.
- `.gltf` + `.bin` + textures served via FastAPI `StaticFiles` mount.

### Frontend

- **Vite + React + TypeScript** — standard toolchain.
- **react-three-fiber + @react-three/drei** — R3F for `Canvas`, Drei for `OrbitControls`, `Environment`, `Gltf`, `Grid`.
- **Zustand** — state management for shot metadata, camera selection, timeline sync.
- **Spotify dark theme** — `ui-design/DESIGN.md` as design token source.

### API Contract

```
POST /api/shots
  Content-Type: multipart/form-data
  Body: file=<blend_file>
  Response: {
    "id": "abc123",
    "hash": "sha256...",
    "gltfUrl": "/static/exports/abc123/scene.gltf",
    "cameras": ["Camera", "Camera.001"],
    "animations": [{"name": "ArmatureAction", "duration": 3.0}],
    "duration": 3.0,
    "fps": 24
  }

GET /api/shots/{id}
  Response: same as above (cached from upload)

GET /static/exports/{hash}/*
  → StaticFiles serve glTF + .bin + textures
```

### Zustand Store Shape

```typescript
// Conceptual shape — from prototyping session
interface ShotStore {
  shot: Shot | null;          // current shot metadata
  loading: boolean;           // conversion in progress
  error: string | null;       // conversion error
  playing: boolean;           // timeline playing
  currentTime: number;        // timeline position (seconds)
  activeCamera: string | null; // selected camera name
  // actions
  upload: (file: File) => Promise<void>;
  setPlaying: (v: boolean) => void;
  setCurrentTime: (t: number) => void;
  setActiveCamera: (name: string) => void;
}
```

## Testing Decisions

- **Seam 1 (Blender export)**: Integration test — run `export_shot.py` against a fixture `.blend`, assert `.gltf` output structure. Test with and without cameras.
- **Seam 2 (FastAPI endpoints)**: `pytest-asyncio` + `httpx.AsyncClient` — test upload returns correct JSON shape, test `GET /static/exports/` serves files, test hash dedup, test error on non-.blend upload.
- **Seam 3 (Frontend)**: Visual verification. No automated E2E in V1.
- **Test principle**: Tests verify external behavior at seams, not internal implementation.

## Out of Scope

- **Material matching** — glTF PBR will not match Blender EEVEE render 1:1. Users accept visual differences.
- **Multiple shots** — only one shot loaded at a time. No shot list/sidebar.
- **NLA/action selection** — all animations exported. No per-action toggle.
- **Drag-and-drop of assets into the 3D view** — no editing, viewer-only.
- **Mobile support** — desktop first.
- **Authentication/multi-user** — single-user local tool.
- **Background task queue** — conversion runs inline during the HTTP request.

## Further Notes

- Blender 4.4.3 must be installed on the host (`/Applications/Blender.app` or in PATH).
- The existing `.blend` files in `test/render/` can serve as test fixtures.
- Environment variables: `STORYBOARD_EXPORT_DIR` (default `exports/`), `STORYBOARD_MAX_DISK_MB` (default 500).
