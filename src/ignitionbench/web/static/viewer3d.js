// Interactive 3D motor model built with Three.js (MIT-licensed, vendored).
// Dimensions arrive in mm; the scene works in metres.

import * as THREE from "three";
import { OrbitControls } from "./vendor/OrbitControls.js";

const MM = 1 / 1000;
const WALL = 3, BULKHEAD = 10, FWD = 6, AFT = 5, GAP = 3; // mm, visual construction

// Outline (mm) of the core circle fused with the tapered slit wedges —
// one closed loop walked counter-clockwise: core arc, out along a slit
// wall to its tip, back, next arc…
function voidOutline(g) {
  const rc = g.core_d_mm / 2;
  const tip = rc + g.slit_depth_mm;
  const mouthHalf = g.slit_width_mm / 2;
  const tipHalf = mouthHalf * (g.slit_taper ?? 0);
  const beta = Math.asin(Math.min(mouthHalf / rc, 1));
  const points = [];
  for (let k = 0; k < g.slit_count; k++) {
    const th = (2 * Math.PI * k) / g.slit_count - Math.PI / 2;
    const prev = th - (2 * Math.PI) / g.slit_count;
    // core arc from the previous slit's exit to this slit's entry
    const a0 = prev + beta, a1 = th - beta;
    for (let i = 0; i <= 14; i++) {
      const a = a0 + ((a1 - a0) * i) / 14;
      points.push([rc * Math.cos(a), rc * Math.sin(a)]);
    }
    const ux = Math.cos(th), uy = Math.sin(th);
    const vx = -uy, vy = ux;
    points.push([tip * ux - tipHalf * vx, tip * uy - tipHalf * vy]);
    points.push([tip * ux + tipHalf * vx, tip * uy + tipHalf * vy]);
  }
  return points;
}

export class MotorViewer {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.setClearColor(0x141413);
    this.renderer.localClippingEnabled = true;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(38, 1, 0.005, 10);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;

    this.scene.add(new THREE.HemisphereLight(0xdfe5ee, 0x1c1a18, 1.15));
    const key = new THREE.DirectionalLight(0xffffff, 1.9);
    key.position.set(0.5, 1, 0.8);
    this.scene.add(key);
    const rim = new THREE.DirectionalLight(0x88aaff, 0.5);
    rim.position.set(-0.6, -0.3, -0.8);
    this.scene.add(rim);

    this.clipPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
    this.materials = [];
    this.group = null;
    this.cutaway = true;
    this.viewDist = 0.45;

    // CAD-style reference grid under the part
    this.grid = new THREE.GridHelper(1, 40, 0x33322f, 0x232221);
    this.scene.add(this.grid);

    this._resize();
    new ResizeObserver(() => this._resize()).observe(canvas.parentElement);
    this.renderer.setAnimationLoop(() => {
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
    });
  }

  _resize() {
    const w = this.canvas.parentElement.clientWidth - 2;
    const h = 380;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  _material(opts) {
    const m = new THREE.MeshStandardMaterial({ side: THREE.DoubleSide, ...opts });
    this.materials.push(m);
    return m;
  }

  rebuild(g) {
    if (this.group) {
      this.scene.remove(this.group);
      this.group.traverse((o) => o.geometry?.dispose());
      this.materials.forEach((m) => m.dispose());
      this.materials = [];
    }
    const group = new THREE.Group();

    const rGrain = (g.outer_d_mm / 2) * MM;
    const rCase = rGrain + WALL * MM;
    const rCore = (g.core_d_mm / 2) * MM;
    const rt = (g.throat_d_mm / 2) * MM;
    const re = (g.exit_d_mm / 2) * MM;
    const segLen = g.length_mm * MM;
    const grainLen = g.segments * segLen + (g.segments - 1) * GAP * MM;
    const chamberLen = (BULKHEAD + FWD) * MM + grainLen + AFT * MM;
    const conv = rGrain - rt; // 45° convergent
    const div = g.divergent_length_mm * MM;
    const total = chamberLen + conv + div;

    const steel = this._material({ color: 0x9aa0a8, metalness: 0.85, roughness: 0.38 });
    const graphite = this._material({ color: 0x4c4944, metalness: 0.55, roughness: 0.6 });
    const fuel = this._material({ color: 0x3987e5, metalness: 0.05, roughness: 0.9 });

    // casing tube
    const casing = new THREE.Mesh(
      new THREE.CylinderGeometry(rCase, rCase, chamberLen, 64, 1, true), steel);
    casing.rotation.z = Math.PI / 2;
    casing.position.x = chamberLen / 2;
    group.add(casing);

    // forward bulkhead
    const cap = new THREE.Mesh(
      new THREE.CylinderGeometry(rCase, rCase, BULKHEAD * MM, 64), steel);
    cap.rotation.z = Math.PI / 2;
    cap.position.x = (BULKHEAD * MM) / 2;
    group.add(cap);

    // grain segments: true annulus, extruded; the hole is the core circle
    // fused with the slit wedges when slits are present
    const shape = new THREE.Shape();
    shape.absarc(0, 0, rGrain, 0, Math.PI * 2, false);
    const hole = new THREE.Path();
    if (g.slit_count > 0) {
      hole.setFromPoints(voidOutline(g).map(([x, y]) => new THREE.Vector2(x * MM, y * MM)));
    } else {
      hole.absarc(0, 0, rCore, 0, Math.PI * 2, true);
    }
    shape.holes.push(hole);
    const grainGeom = new THREE.ExtrudeGeometry(shape, { depth: segLen, bevelEnabled: false, curveSegments: 48 });
    grainGeom.rotateY(Math.PI / 2);
    for (let i = 0; i < g.segments; i++) {
      const seg = new THREE.Mesh(grainGeom, fuel);
      seg.position.x = (BULKHEAD + FWD) * MM + i * (segLen + GAP * MM);
      group.add(seg);
    }

    // nozzle: lathe profile (radius, axial) closed into a solid shell
    const profile = [
      new THREE.Vector2(rGrain, 0),
      new THREE.Vector2(rt, conv),
      new THREE.Vector2(re, conv + div),
      new THREE.Vector2(re + WALL * MM, conv + div),
      new THREE.Vector2(Math.max(rt + WALL * MM, re * 0.55 + WALL * MM), conv * 0.55),
      new THREE.Vector2(rCase, 0),
    ];
    const nozzle = new THREE.Mesh(new THREE.LatheGeometry(profile, 64), graphite);
    nozzle.rotation.z = -Math.PI / 2;
    nozzle.position.x = chamberLen;
    group.add(nozzle);

    group.position.x = -total / 2;
    this.scene.add(group);
    this.group = group;
    this.setCutaway(this.cutaway);

    this.viewDist = Math.max(total * 1.4, rCase * 7);
    this.grid.position.y = -(rCase + 0.004);
    this.grid.scale.setScalar(Math.max(total * 2.5, 0.25));
    if (!this._placed) {
      this.setView("iso");
      this._placed = true;
    }
  }

  setView(name) {
    const d = this.viewDist;
    const positions = {
      iso: [d * 0.75, d * 0.45, d * 0.9],
      front: [0, 0, d * 1.25],
      side: [d * 1.25, 0, 0.0001],
      top: [0.0001, d * 1.25, 0],
    };
    this.camera.position.set(...(positions[name] || positions.iso));
    this.controls.target.set(0, 0, 0);
    this.controls.update();
  }

  setCutaway(on) {
    this.cutaway = on;
    for (const m of this.materials) {
      m.clippingPlanes = on ? [this.clipPlane] : [];
      m.needsUpdate = true;
    }
  }

}
