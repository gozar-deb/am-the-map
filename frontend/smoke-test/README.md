# Headless Three.js smoke test

`gl-smoke.mjs` exercises the real scene-construction logic from
`src/three/Scene.tsx` (renderer/camera setup, InstancedMesh voxel
deposits, sensor cone markers with canvas-texture label sprites, tracked
object spheres + trail lines, the CanvasTexture RF heatmap plane,
OrbitControls, and both the default-orbit and top-down camera presets)
against a real WebGL context — via `gl` (headless-gl / software Mesa) and
`jsdom` — and renders + saves actual frames to confirm geometry, color, and
labels show up correctly. This caught real issues during development that a
TypeScript/Vite build alone can't (e.g. WebGL API misuse, canvas-texture
bugs) — it's a much stronger check than "it compiles."

It is **not** a substitute for testing in a real browser (no user input,
no React reconciliation, no CSS/Tailwind layout, no actual pointer-drag
interaction), but it does prove the core 3D rendering pipeline is sound.

## Running it

Not part of the normal `npm install` (these are heavy native deps not
needed to run the app):

```bash
npm install --no-save gl jsdom canvas
apt-get install -y xvfb libosmesa6-dev libglu1-mesa-dev  # Linux; see below for other platforms
xvfb-run -a node smoke-test/gl-smoke.mjs
```

Outputs `smoke-test/rendered-frame.png` and `rendered-frame-top.png` — open
them to visually confirm the scene looks right after changing `Scene.tsx`.

On macOS/Windows, `gl` (headless-gl) has known build issues outside Linux —
easiest is to run this inside the same Docker image as the frontend
container, or just test in a real browser via `npm run dev` instead.
