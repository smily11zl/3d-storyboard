# 04 — Frontend: Dual Viewport + R3F Scene

**What to build:** Two Three.js viewports using react-three-fiber. The left viewport (Camera View) renders from the active scene camera's perspective. The right viewport (Free View) allows free orbit with OrbitControls. The scene is loaded from the `.gltf` URL returned by the backend. Environment lighting, a ground grid, and shadows provide spatial context. A camera selector dropdown in the Camera View lets the user switch between cameras. When the scene has no cameras, Camera View falls back to a default orbit perspective.

**Blocked by:** 03 (React Scaffold + Upload)

**Status:** ready-for-agent

- [ ] Two `<Canvas>` components side by side (50/50 split, responsive)
- [ ] Left Canvas (Camera View): labeled "Camera View" header
- [ ] Right Canvas (Free View): labeled "Free View" header
- [ ] Both canvases load the same `.gltf` scene via `useGLTF` (Drei)
- [ ] Left Canvas: camera locked to the selected scene camera (`useThree` + camera position/orientation from glTF camera node)
- [ ] Right Canvas: `OrbitControls` (Drei) with pan, zoom, rotate
- [ ] Camera selector dropdown inside Camera View header: lists all cameras from shot metadata, default selection is first camera
- [ ] When scene has zero cameras: Camera View falls back to a default perspective (positioned at a reasonable distance, looking at scene center)
- [ ] `Environment` (Drei) with preset "studio" or "city" for ambient lighting
- [ ] `Grid` (Drei) on the ground plane (`position={[0,0,0]}`, infinite grid) for spatial reference
- [ ] Directional light with shadow map for shadow casting
- [ ] Both canvases share the same dark background (`#121212`), camera frustum helper disabled
- [ ] Camera selection persisted in Zustand store (`activeCameraName`)
- [ ] All variable and parameter names use full descriptive words, no abbreviations
