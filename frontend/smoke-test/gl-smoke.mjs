// Headless smoke test: exercises the actual Three.js scene-construction logic
// used by src/three/Scene.tsx (voxel InstancedMesh, sensor cones, heatmap
// plane, tracked-object spheres, OrbitControls) against a real (software)
// WebGL context via headless-gl + Xvfb, and a JSDOM-provided `document`.
// This is NOT a browser test, but it does catch: import/runtime errors,
// WebGL API misuse, and Three.js object construction bugs that a pure
// TypeScript/Vite build check cannot.

import { JSDOM } from "jsdom";
import createGL from "gl";
import * as THREE from "three";
import { createCanvas } from "canvas";
import { writeFileSync } from "fs";

const dom = new JSDOM("<!doctype html><html><body></body></html>", { pretendToBeVisual: true });
global.window = dom.window;
global.document = dom.window.document;
Object.defineProperty(global, "navigator", { value: dom.window.navigator, configurable: true });

const WIDTH = 800, HEIGHT = 600;
const glContext = createGL(WIDTH, HEIGHT, { preserveDrawingBuffer: true });
if (!glContext) throw new Error("Failed to create headless GL context");

// Minimal canvas shim whose getContext() returns our real headless-gl context,
// matching what THREE.WebGLRenderer expects from an HTMLCanvasElement.
class FakeCanvas {
  constructor(width, height) {
    this.width = width;
    this.height = height;
    this.style = {};
    this.clientWidth = width;
    this.clientHeight = height;
  }
  getContext(type) {
    if (type === "webgl" || type === "webgl2" || type === "experimental-webgl") return glContext;
    return null;
  }
  addEventListener() {}
  removeEventListener() {}
  setAttribute() {}
  getBoundingClientRect() {
    return { left: 0, top: 0, width: this.width, height: this.height };
  }
}

const canvas = new FakeCanvas(WIDTH, HEIGHT);

console.log("--- 1. Creating renderer, scene, camera (mirrors Scene.tsx setup) ---");
const scene = new THREE.Scene();
scene.background = new THREE.Color("#0a0e13");
scene.fog = new THREE.Fog("#0a0e13", 8, 22);

const camera = new THREE.PerspectiveCamera(50, WIDTH / HEIGHT, 0.1, 100);
camera.position.set(4, 4, 6);

const renderer = new THREE.WebGLRenderer({ canvas, context: glContext, antialias: true, alpha: true });
renderer.setSize(WIDTH, HEIGHT);
console.log("Renderer created OK:", renderer.getContext() === glContext);

console.log("--- 2. Lights, grid, room edges ---");
scene.add(new THREE.AmbientLight("#ffffff", 0.6));
const dirLight = new THREE.DirectionalLight("#ffffff", 0.5);
dirLight.position.set(3, 6, 2);
scene.add(dirLight);
scene.add(new THREE.GridHelper(10, 20, "#1e2830", "#141b23"));
const roomEdges = new THREE.LineSegments(
  new THREE.EdgesGeometry(new THREE.BoxGeometry(5, 3, 5)),
  new THREE.LineBasicMaterial({ color: "#1e2830" })
);
roomEdges.position.set(0, 1.5, 0);
scene.add(roomEdges);

console.log("--- 3. Voxel InstancedMesh (this is the trickiest part of Scene.tsx) ---");
const voxelGeo = new THREE.BoxGeometry(0.18, 0.18, 0.18);
const voxelMat = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.85 });
const voxelMesh = new THREE.InstancedMesh(voxelGeo, voxelMat, 4000);
voxelMesh.count = 0;
scene.add(voxelMesh);

// Simulate what updateScene() does with a realistic backend snapshot shape
const fakeSnapshot = {
  environment: { bounds_m: [5, 5, 3], voxel_resolution_m: 0.2 },
  voxels: Array.from({ length: 250 }, (_, i) => ({
    world: [Math.random() * 5, Math.random() * 5, Math.random() * 3],
    occupancy_probability: Math.random(),
    movement_probability: Math.random() * 0.5,
    rf_intensity: Math.random(),
    confidence: Math.random(),
  })),
  sensors: [
    { id: "NODE-01", status: "online", position: [0, 0, 2.2] },
    { id: "NODE-02", status: "online", position: [5, 0, 2.2] },
    { id: "NODE-03", status: "offline", position: [2.5, 5, 2.2] },
  ],
  objects: [
    { id: "obj-1", x: 2.1, y: 2.4, z: 1.0, confidence: 0.6, trail: [[2.0, 2.3], [2.1, 2.4]] },
  ],
};

const dummy = new THREE.Object3D();
let vi = 0;
const [bx, by] = fakeSnapshot.environment.bounds_m;
for (const v of fakeSnapshot.voxels) {
  const [wx, wy, wz] = v.world;
  dummy.position.set(wx - bx / 2, wz, wy - by / 2);
  dummy.scale.setScalar(0.4 + v.occupancy_probability * 1.4);
  dummy.updateMatrix();
  voxelMesh.setMatrixAt(vi, dummy.matrix);
  const color = new THREE.Color("#173037").lerp(new THREE.Color("#4fd1e8"), v.occupancy_probability);
  voxelMesh.setColorAt(vi, color);
  vi++;
}
voxelMesh.count = vi;
voxelMesh.instanceMatrix.needsUpdate = true;
if (voxelMesh.instanceColor) voxelMesh.instanceColor.needsUpdate = true;
console.log(`Deposited ${vi} voxel instances OK`);

console.log("--- 4. Sensor cone markers + label sprites (canvas texture path) ---");
const sensorGroup = new THREE.Group();
for (const sensor of fakeSnapshot.sensors) {
  const group = new THREE.Group();
  group.userData.sensorId = sensor.id;
  const cone = new THREE.Mesh(
    new THREE.ConeGeometry(0.12, 0.24, 4),
    new THREE.MeshBasicMaterial({ color: sensor.status === "online" ? "#4fd1e8" : "#3e4a55" })
  );
  cone.rotation.x = Math.PI;
  group.add(cone);

  // label sprite -- uses document.createElement('canvas') + 2D context,
  // this is the part most likely to break outside a real browser
  const labelCanvas = document.createElement("canvas");
  labelCanvas.width = 256;
  labelCanvas.height = 64;
  const ctx2d = labelCanvas.getContext("2d");
  ctx2d.font = "600 28px monospace";
  ctx2d.fillStyle = "#e7edf2";
  ctx2d.fillText(sensor.id, 4, 32);
  const texture = new THREE.CanvasTexture(labelCanvas);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true }));
  sprite.position.y = 0.3;
  group.add(sprite);

  group.position.set(sensor.position[0] - bx / 2, sensor.position[2], sensor.position[1] - by / 2);
  sensorGroup.add(group);
}
scene.add(sensorGroup);
console.log(`Created ${sensorGroup.children.length} sensor markers with label sprites OK`);

console.log("--- 5. Tracked object spheres + trail lines ---");
const objectGroup = new THREE.Group();
for (const obj of fakeSnapshot.objects) {
  const sphere = new THREE.Mesh(
    new THREE.SphereGeometry(0.14, 12, 12),
    new THREE.MeshBasicMaterial({ color: "#e85d4d", transparent: true, opacity: 0.4 + obj.confidence * 0.6 })
  );
  sphere.position.set(obj.x - bx / 2, obj.z, obj.y - by / 2);
  objectGroup.add(sphere);
  if (obj.trail.length > 1) {
    const points = obj.trail.map(([tx, ty]) => new THREE.Vector3(tx - bx / 2, 0.03, ty - by / 2));
    const line = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(points),
      new THREE.LineBasicMaterial({ color: "#e85d4d" })
    );
    objectGroup.add(line);
  }
}
scene.add(objectGroup);
console.log(`Created ${objectGroup.children.length} object scene nodes OK`);

console.log("--- 6. Heatmap plane with CanvasTexture ---");
const heatmapCanvas = document.createElement("canvas");
heatmapCanvas.width = 128;
heatmapCanvas.height = 128;
const heatmapTexture = new THREE.CanvasTexture(heatmapCanvas);
const heatmapPlane = new THREE.Mesh(
  new THREE.PlaneGeometry(5, 5),
  new THREE.MeshBasicMaterial({ map: heatmapTexture, transparent: true, opacity: 0.75, side: THREE.DoubleSide })
);
heatmapPlane.rotation.x = -Math.PI / 2;
scene.add(heatmapPlane);
const hctx = heatmapCanvas.getContext("2d");
const grad = hctx.createRadialGradient(64, 64, 0, 64, 64, 40);
grad.addColorStop(0, "rgba(79,209,232,0.8)");
grad.addColorStop(1, "rgba(79,209,232,0)");
hctx.fillStyle = grad;
hctx.beginPath();
hctx.arc(64, 64, 40, 0, Math.PI * 2);
hctx.fill();
heatmapTexture.needsUpdate = true;
console.log("Heatmap plane + canvas gradient draw OK");

console.log("--- 7. OrbitControls construction ---");
const { OrbitControls } = await import("three/examples/jsm/controls/OrbitControls.js");
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.target.set(0, 1, 0);
controls.update();
console.log("OrbitControls constructed and updated OK");

console.log("--- 8. Actually rendering a frame (orbit view) ---");
renderer.render(scene, camera);
const pixels = new Uint8Array(WIDTH * HEIGHT * 4);
glContext.readPixels(0, 0, WIDTH, HEIGHT, glContext.RGBA, glContext.UNSIGNED_BYTE, pixels);

// Save as PNG for actual visual inspection (readPixels is bottom-up, PNG is top-down)
const outCanvas = createCanvas(WIDTH, HEIGHT);
const outCtx = outCanvas.getContext("2d");
const imgData = outCtx.createImageData(WIDTH, HEIGHT);
for (let y = 0; y < HEIGHT; y++) {
  const srcRow = HEIGHT - 1 - y;
  imgData.data.set(pixels.subarray(srcRow * WIDTH * 4, (srcRow + 1) * WIDTH * 4), y * WIDTH * 4);
}
outCtx.putImageData(imgData, 0, 0);
writeFileSync(new URL("./rendered-frame.png", import.meta.url), outCanvas.toBuffer("image/png"));
console.log("Saved rendered-frame.png for visual inspection");

let colorPixels = 0; // pixels meaningfully different from the flat background color
const bgR = 10, bgG = 14, bgB = 19;
for (let i = 0; i < pixels.length; i += 4) {
  if (Math.abs(pixels[i] - bgR) > 8 || Math.abs(pixels[i + 1] - bgG) > 8 || Math.abs(pixels[i + 2] - bgB) > 8) {
    colorPixels++;
  }
}
console.log(`Pixels meaningfully different from background: ${colorPixels} / ${WIDTH * HEIGHT}`);

if (colorPixels < 100) {
  throw new Error("Almost nothing rendered beyond flat background -- likely a real bug");
}

console.log("--- 9. Top-down camera preset (mirrors viewMode === 'top' in Scene.tsx) ---");
camera.position.set(0.01, 9, 0.01);
camera.lookAt(0, 0, 0);
renderer.render(scene, camera);
glContext.readPixels(0, 0, WIDTH, HEIGHT, glContext.RGBA, glContext.UNSIGNED_BYTE, pixels);
const topImgData = outCtx.createImageData(WIDTH, HEIGHT);
for (let y = 0; y < HEIGHT; y++) {
  const srcRow = HEIGHT - 1 - y;
  topImgData.data.set(pixels.subarray(srcRow * WIDTH * 4, (srcRow + 1) * WIDTH * 4), y * WIDTH * 4);
}
outCtx.putImageData(topImgData, 0, 0);
writeFileSync(new URL("./rendered-frame-top.png", import.meta.url), outCanvas.toBuffer("image/png"));
console.log("Saved rendered-frame-top.png");

console.log("\n✅ ALL SCENE-CONSTRUCTION AND RENDER STEPS SUCCEEDED — no exceptions, frame is non-blank.");
