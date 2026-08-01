# 05 — Frontend: Timeline + Animation Playback

**What to build:** A shared timeline bar at the bottom of the page that controls animation playback across both viewports. Play/pause toggles and a scrub bar allow frame-by-frame navigation. Both Camera View and Free View display the scene at the same animation time. The timeline shows the current time in seconds and total duration.

**Blocked by:** 04 (Dual Viewport + R3F)

**Status:** ready-for-agent

- [ ] Timeline bar at bottom: full-width, fixed height (~48px), Spotify dark style (`#1f1f1f` background)
- [ ] Play/pause button (left side of timeline): Spotify Green (`#1ed760`) when playing, pill shape
- [ ] Time display: "MM:SS.s / MM:SS.s" format (current / total)
- [ ] Scrub bar: clickable/draggable slider showing current frame position within total duration
- [ ] Zustand store fields: `isPlaying`, `currentTime`, `duration`, `fps`
- [ ] `useFrame` in each Canvas reads `currentTime` from Zustand store and advances animation mixer
- [ ] Playback: `currentTime` advances via `requestAnimationFrame` in a single `useFrame` loop (not duplicated per canvas)
- [ ] Both viewports share the same animation mixer time — pausing at 2.3s shows frame 55 in both views
- [ ] Animation duration auto-detected from glTF `AnimationClip` data; exposed in shot metadata from backend
- [ ] When scene has no animations: timeline still visible but disabled (greyed out, play button inactive)
- [ ] Scrubbing during pause: immediate scene update to the scrubbed frame
- [ ] Timeline keyboard shortcuts: Space to toggle play/pause
- [ ] All variable and parameter names use full descriptive words, no abbreviations
