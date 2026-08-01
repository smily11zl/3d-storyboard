# 03 — Frontend: React Scaffold + Upload Flow

**What to build:** A Vite + React + TypeScript frontend scaffold with Spotify dark theme styling from `ui-design/DESIGN.md`. Includes an upload area that supports drag-and-drop and click-to-browse for `.blend` files. On upload, calls `POST /api/shots` and displays loading state while conversion runs. On success, displays the shot metadata. On error, shows an error message.

**Blocked by:** 02 (FastAPI Endpoints)

**Status:** ready-for-agent

- [ ] Vite + React + TypeScript project in `frontend/` (created with `npm create vite@latest`)
- [ ] `react-three-fiber`, `@react-three/drei`, `three`, `zustand` installed
- [ ] Vite dev server proxies `/api` and `/static` to FastAPI backend (localhost:8000)
- [ ] CSS custom properties defined from `ui-design/DESIGN.md`: colors (`#121212`, `#181818`, `#1f1f1f`, `#1ed760`, `#b3b3b3`, `#ffffff`), border radii (pill: 9999px, card: 8px), shadows (heavy: `rgba(0,0,0,0.5) 0px 8px 24px`)
- [ ] Upload area: large centered drop zone with dashed border, supports drag-and-drop and click-to-browse
- [ ] Upload area accepts `.blend` files only; rejects other file types with visual feedback
- [ ] On upload: drop zone collapses to a compact top bar, main area shows loading state (spinner + "Converting..." message)
- [ ] On success: loading replaced by dual-viewport placeholder area (empty containers with "Camera View" and "Free View" labels)
- [ ] On error: toast/error bar with the server's error message, upload area re-expands for retry
- [ ] Top bar shows uploaded filename after successful conversion
- [ ] Upload flow uses Zustand store with actions: `uploadFile`, `clearError`
- [ ] All variable and parameter names use full descriptive words, no abbreviations
