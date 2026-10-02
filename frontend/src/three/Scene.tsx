import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { api } from "../api/client";
import { useAppStore } from "../state/store";
import type { MapSnapshot } from "../types";

const VOXEL_COLOR_LOW = new THREE.Color("#173037");
const VOXEL_COLOR_HIGH = new THREE.Color("#4fd1e8");
const MOVEMENT_COLOR = new THREE.Color("#ffb454");
const SENSOR_ONLINE = new THREE.Color("#4fd1e8");
const SENSOR_OFFLINE = new THREE.Color("#3e4a55");
const OBJECT_COLOR = new THREE.Color("#e85d4d");

function makeLabelSprite(text: string, color = "#e7edf2"): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext("2d")!;
  ctx.font = "600 28px 'IBM Plex Mono', monospace";
  ctx.fillStyle = color;
  ctx.textBaseline = "middle";
  ctx.fillText(text, 4, 32);
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(0.9, 0.22, 1);
  return sprite;
}

export default function Scene() {
  const mountRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef<{
    scene: THREE.Scene;
    camera: THREE.PerspectiveCamera;
    renderer: THREE.WebGLRenderer;
    controls: OrbitControls;
    voxelMesh: THREE.InstancedMesh;
    movementMesh: THREE.InstancedMesh;
    sensorGroup: THREE.Group;
    objectGroup: THREE.Group;
    heatmapPlane: THREE.Mesh;
    heatmapTexture: THREE.CanvasTexture;
    heatmapCanvas: HTMLCanvasElement;
    bounds: [number, number, number];
    raycaster: THREE.Raycaster;
    dragging: { sensorId: string; mesh: THREE.Object3D } | null;
  } | null>(null);

  const layers = useAppStore((s) => s.layers);
  const zSlice = useAppStore((s) => s.zSlice);
  const viewMode = useAppStore((s) => s.viewMode);
  const selectedSensorId = useAppStore((s) => s.selectedSensorId);
  const setSelectedSensor = useAppStore((s) => s.setSelectedSensor);

  // `updateScene` (and the helpers it calls) can be invoked from a listener
  // registered once on mount (the zustand subscribe effect below) as well
  // as from effects that re-run on every render. A callback registered with
  // an empty dependency array closes over whatever `layers`/`zSlice` were
  // at *mount* time and never sees later toggles/slider moves -- since new
  // snapshots arrive ~5x/sec over the WebSocket, that stale closure would
  // silently re-apply the original layer/Z-slice state shortly after every
  // toggle. Refs sidestep this: they're mutable cells `updateScene` can read
  // through regardless of which render's closure is calling it.
  const layersRef = useRef(layers);
  const zSliceRef = useRef(zSlice);
  useEffect(() => {
    layersRef.current = layers;
  }, [layers]);
  useEffect(() => {
    zSliceRef.current = zSlice;
  }, [zSlice]);

  // one-time scene setup
  useEffect(() => {
    const mount = mountRef.current!;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#0a0e13");
    scene.fog = new THREE.Fog("#0a0e13", 8, 22);

    const camera = new THREE.PerspectiveCamera(50, mount.clientWidth / mount.clientHeight, 0.1, 100);
    camera.position.set(4, 4, 6);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.target.set(0, 1, 0);

    scene.add(new THREE.AmbientLight("#ffffff", 0.6));
    const dirLight = new THREE.DirectionalLight("#ffffff", 0.5);
    dirLight.position.set(3, 6, 2);
    scene.add(dirLight);

    const grid = new THREE.GridHelper(10, 20, "#1e2830", "#141b23");
    scene.add(grid);

    const roomEdges = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(5, 3, 5)),
      new THREE.LineBasicMaterial({ color: "#1e2830" })
    );
    roomEdges.position.set(0, 1.5, 0);
    scene.add(roomEdges);

    const voxelGeo = new THREE.BoxGeometry(0.18, 0.18, 0.18);
    const voxelMat = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.85 });
    const voxelMesh = new THREE.InstancedMesh(voxelGeo, voxelMat, 4000);
    voxelMesh.count = 0;
    scene.add(voxelMesh);

    const moveGeo = new THREE.SphereGeometry(0.09, 6, 6);
    const moveMat = new THREE.MeshBasicMaterial({ color: MOVEMENT_COLOR, transparent: true, opacity: 0.55 });
    const movementMesh = new THREE.InstancedMesh(moveGeo, moveMat, 1000);
    movementMesh.count = 0;
    scene.add(movementMesh);

    const sensorGroup = new THREE.Group();
    scene.add(sensorGroup);
    const objectGroup = new THREE.Group();
    scene.add(objectGroup);

    // RF heatmap plane (section 7) -- textured from a 2D canvas we redraw
    // whenever the active Z slice's voxel data changes.
    const heatmapCanvas = document.createElement("canvas");
    heatmapCanvas.width = 128;
    heatmapCanvas.height = 128;
    const heatmapTexture = new THREE.CanvasTexture(heatmapCanvas);
    const heatmapPlane = new THREE.Mesh(
      new THREE.PlaneGeometry(5, 5),
      new THREE.MeshBasicMaterial({ map: heatmapTexture, transparent: true, opacity: 0.75, side: THREE.DoubleSide })
    );
    heatmapPlane.rotation.x = -Math.PI / 2;
    heatmapPlane.visible = false;
    scene.add(heatmapPlane);

    const raycaster = new THREE.Raycaster();

    stateRef.current = {
      scene,
      camera,
      renderer,
      controls,
      voxelMesh,
      movementMesh,
      sensorGroup,
      objectGroup,
      heatmapPlane,
      heatmapTexture,
      heatmapCanvas,
      bounds: [5, 3, 5],
      raycaster,
      dragging: null,
    };

    let raf = 0;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    window.addEventListener("resize", onResize);

    // --- drag-to-reposition sensors (section 10) ---
    const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    const pointer = new THREE.Vector2();
    const dragPoint = new THREE.Vector3();

    function setPointer(e: PointerEvent) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    }

    function onPointerDown(e: PointerEvent) {
      setPointer(e);
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(sensorGroup.children, true);
      if (hits.length > 0) {
        let obj: THREE.Object3D | null = hits[0].object;
        while (obj && !obj.userData.sensorId) obj = obj.parent;
        if (obj) {
          const s = stateRef.current!;
          s.dragging = { sensorId: obj.userData.sensorId, mesh: obj };
          // Raycast against a plane at the sensor's own height, not a fixed
          // y=0 floor -- sensors are typically mounted ~2m up, and
          // intersecting the wrong plane introduces parallax error that
          // makes the marker drift away from the cursor as you drag.
          floorPlane.constant = -obj.position.y;
          controls.enabled = false;
          setSelectedSensor(obj.userData.sensorId);
        }
      }
    }
    function onPointerMove(e: PointerEvent) {
      const s = stateRef.current;
      if (!s?.dragging) return;
      setPointer(e);
      raycaster.setFromCamera(pointer, camera);
      const [bx, , by] = s.bounds;
      if (raycaster.ray.intersectPlane(floorPlane, dragPoint)) {
        const clampedX = Math.max(-bx / 2, Math.min(bx / 2, dragPoint.x));
        const clampedZ = Math.max(-by / 2, Math.min(by / 2, dragPoint.z));
        s.dragging.mesh.position.x = clampedX;
        s.dragging.mesh.position.z = clampedZ;
      }
    }
    function onPointerUp() {
      const s = stateRef.current;
      if (!s?.dragging) return;
      const { sensorId, mesh } = s.dragging;
      const [bx, , by] = s.bounds;
      const worldX = mesh.position.x + bx / 2;
      const worldY = mesh.position.z + by / 2;
      api.updateSensorPosition(sensorId, worldX, worldY, mesh.position.y).catch(() => {
        /* best effort -- position will resync from the next snapshot */
      });
      s.dragging = null;
      controls.enabled = true;
    }

    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // camera view presets
  useEffect(() => {
    const s = stateRef.current;
    if (!s) return;
    if (viewMode === "top") {
      s.camera.position.set(0.01, 9, 0.01);
      s.controls.target.set(0, 0, 0);
      s.controls.minPolarAngle = 0;
      s.controls.maxPolarAngle = 0.05;
    } else if (viewMode === "first_person") {
      s.camera.position.set(0, 1.6, 0);
      s.controls.target.set(1, 1.6, 0);
      s.controls.minPolarAngle = Math.PI / 2 - 0.6;
      s.controls.maxPolarAngle = Math.PI / 2 + 0.6;
    } else {
      s.camera.position.set(4, 4, 6);
      s.controls.target.set(0, 1, 0);
      s.controls.minPolarAngle = 0;
      s.controls.maxPolarAngle = Math.PI;
    }
  }, [viewMode]);

  // subscribe to live snapshot updates without re-running the whole effect graph
  useEffect(() => {
    const unsub = useAppStore.subscribe((s) => s.snapshot, (snapshot) => {
      if (snapshot) updateScene(snapshot);
    });
    return unsub;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // re-apply layer/zSlice-driven visibility whenever those (or the latest
  // snapshot) change
  useEffect(() => {
    const snapshot = useAppStore.getState().snapshot;
    if (snapshot) updateScene(snapshot);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [layers, zSlice]);

  useEffect(() => {
    const s = stateRef.current;
    if (!s) return;
    for (const child of s.sensorGroup.children) {
      const ring = (child as THREE.Object3D).getObjectByName("selection-ring");
      if (ring) ring.visible = child.userData.sensorId === selectedSensorId;
    }
  }, [selectedSensorId]);

  function updateScene(snapshot: MapSnapshot) {
    const s = stateRef.current;
    if (!s) return;
    const currentLayers = layersRef.current;
    const currentZSlice = zSliceRef.current;
    const [bx, by, bz] = snapshot.environment.bounds_m;
    s.bounds = [bx, bz, by];

    // --- voxels (occupancy + confidence layers) ---
    const dummy = new THREE.Object3D();
    let vi = 0;
    const showOcc = currentLayers.occupancy;
    const showConf = currentLayers.confidence;
    if (showOcc) {
      for (const v of snapshot.voxels) {
        if (v.occupancy_probability < 0.03 || vi >= s.voxelMesh.instanceMatrix.count) continue;
        const [wx, wy, wz] = v.world;
        dummy.position.set(wx - bx / 2, wz, wy - by / 2);
        const scale = 0.4 + v.occupancy_probability * 1.4;
        dummy.scale.setScalar(scale);
        dummy.updateMatrix();
        s.voxelMesh.setMatrixAt(vi, dummy.matrix);
        const color = VOXEL_COLOR_LOW.clone().lerp(VOXEL_COLOR_HIGH, v.occupancy_probability);
        s.voxelMesh.setColorAt(vi, color);
        vi++;
      }
    }
    s.voxelMesh.count = vi;
    s.voxelMesh.instanceMatrix.needsUpdate = true;
    if (s.voxelMesh.instanceColor) s.voxelMesh.instanceColor.needsUpdate = true;
    (s.voxelMesh.material as THREE.MeshBasicMaterial).opacity = showConf ? 0.9 : 0.55;

    // --- movement layer ---
    let mi = 0;
    if (currentLayers.movement) {
      for (const v of snapshot.voxels) {
        if (v.movement_probability < 0.08 || mi >= s.movementMesh.instanceMatrix.count) continue;
        const [wx, wy, wz] = v.world;
        dummy.position.set(wx - bx / 2, wz + 0.05, wy - by / 2);
        dummy.scale.setScalar(0.5 + v.movement_probability);
        dummy.updateMatrix();
        s.movementMesh.setMatrixAt(mi, dummy.matrix);
        mi++;
      }
    }
    s.movementMesh.count = mi;
    s.movementMesh.instanceMatrix.needsUpdate = true;

    // --- RF heatmap plane (section 7) ---
    s.heatmapPlane.visible = currentLayers.rf_field;
    s.heatmapPlane.scale.set(bx / 5, 1, by / 5);
    s.heatmapPlane.position.y = currentZSlice;
    if (currentLayers.rf_field) drawHeatmap(s, snapshot, currentZSlice);

    // --- sensors (section 9-10) ---
    syncSensors(s, snapshot, bx, by, currentLayers);

    // --- tracked objects + trails (sections 16, 33) ---
    syncObjects(s, snapshot, bx, by, currentLayers);
  }

  function drawHeatmap(s: NonNullable<typeof stateRef.current>, snapshot: MapSnapshot, z: number) {
    const ctx = s.heatmapCanvas.getContext("2d")!;
    const w = s.heatmapCanvas.width;
    const h = s.heatmapCanvas.height;
    ctx.clearRect(0, 0, w, h);
    const [bx, by] = snapshot.environment.bounds_m;
    if (!bx || !by) return;
    const tolerance = snapshot.environment.voxel_resolution_m;
    for (const v of snapshot.voxels) {
      const [wx, wy, wz] = v.world;
      if (Math.abs(wz - z) > tolerance) continue;
      const px = (wx / bx) * w;
      const py = h - (wy / by) * h;
      const intensity = Math.max(v.rf_intensity, v.occupancy_probability * 0.7);
      if (intensity < 0.03) continue;
      const radius = 10 + intensity * 14;
      const grad = ctx.createRadialGradient(px, py, 0, px, py, radius);
      grad.addColorStop(0, `rgba(79, 209, 232, ${Math.min(0.85, intensity)})`);
      grad.addColorStop(1, "rgba(79, 209, 232, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(px, py, radius, 0, Math.PI * 2);
      ctx.fill();
    }
    s.heatmapTexture.needsUpdate = true;
  }

  function syncSensors(
    s: NonNullable<typeof stateRef.current>,
    snapshot: MapSnapshot,
    bx: number,
    by: number,
    currentLayers: typeof layers
  ) {
    s.sensorGroup.visible = currentLayers.sensors;
    const existing = new Map(s.sensorGroup.children.map((c) => [c.userData.sensorId, c]));
    const seen = new Set<string>();

    for (const sensor of snapshot.sensors) {
      seen.add(sensor.id);
      let group = existing.get(sensor.id) as THREE.Group | undefined;
      if (!group) {
        group = new THREE.Group();
        group.userData.sensorId = sensor.id;
        const geo = new THREE.ConeGeometry(0.12, 0.24, 4);
        const mat = new THREE.MeshBasicMaterial({ color: SENSOR_ONLINE });
        const cone = new THREE.Mesh(geo, mat);
        cone.rotation.x = Math.PI;
        group.add(cone);
        const ring = new THREE.Mesh(
          new THREE.RingGeometry(0.18, 0.22, 16),
          new THREE.MeshBasicMaterial({ color: "#4fd1e8", side: THREE.DoubleSide, transparent: true, opacity: 0.8 })
        );
        ring.name = "selection-ring";
        ring.rotation.x = -Math.PI / 2;
        ring.position.y = -0.13;
        ring.visible = false;
        group.add(ring);
        const label = makeLabelSprite(sensor.id);
        label.position.y = 0.3;
        group.add(label);
        s.sensorGroup.add(group);
      }
      // don't fight an in-progress drag with server echoes of the old position
      if (!(s.dragging && s.dragging.sensorId === sensor.id)) {
        group.position.set(sensor.position[0] - bx / 2, sensor.position[2], sensor.position[1] - by / 2);
      }
      const cone = group.children[0] as THREE.Mesh;
      (cone.material as THREE.MeshBasicMaterial).color = sensor.status === "online" ? SENSOR_ONLINE : SENSOR_OFFLINE;
    }
    for (const [id, obj] of existing) {
      if (!seen.has(id)) s.sensorGroup.remove(obj);
    }
  }

  function syncObjects(
    s: NonNullable<typeof stateRef.current>,
    snapshot: MapSnapshot,
    bx: number,
    by: number,
    currentLayers: typeof layers
  ) {
    s.objectGroup.clear();
    for (const obj of snapshot.objects) {
      const sphere = new THREE.Mesh(
        new THREE.SphereGeometry(0.14, 12, 12),
        new THREE.MeshBasicMaterial({ color: OBJECT_COLOR, transparent: true, opacity: 0.4 + obj.confidence * 0.6 })
      );
      sphere.position.set(obj.x - bx / 2, obj.z, obj.y - by / 2);
      s.objectGroup.add(sphere);

      if (currentLayers.historical_trails && obj.trail.length > 1) {
        const points = obj.trail.map(([tx, ty]) => new THREE.Vector3(tx - bx / 2, 0.03, ty - by / 2));
        const line = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(points),
          new THREE.LineBasicMaterial({ color: OBJECT_COLOR, transparent: true, opacity: 0.5 })
        );
        s.objectGroup.add(line);
      }
    }
  }

  return <div ref={mountRef} className="h-full w-full" />;
}
