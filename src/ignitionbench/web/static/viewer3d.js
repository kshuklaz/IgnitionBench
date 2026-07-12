// Interactive 3D motor model built with Three.js (MIT-licensed, vendored).
// Dimensions arrive in mm; the scene works in metres.
//
// The section view is real geometry, not a clipping plane: every part is
// built as a 270° solid with capped cut faces (extruded sector outlines;
// the nozzle is a partial lathe plus two profile caps), so the interior
// reads like a CAD quarter-section instead of a hollow shell.

import * as THREE from "three";
import { OrbitControls } from "./vendor/OrbitControls.js";

const MM = 1 / 1000;
const WALL = 3, BULKHEAD = 10, FWD = 6, AFT = 5, GAP = 3; // mm, visual construction
const SWEEP_START = Math.PI; // kept sector 180°→450°: the +y/+z quadrant is removed
const SWEEP = Math.PI * 1.5;

// Distance from the axis to the void boundary along the ray at theta (mm).
// Mirrors the exact wedge math used by the STL exporter.
function innerRadiusAt(g, theta) {
  const rc = g.core_d_mm / 2;
  if (!g.slit_count) return rc;
  const mouthHalf = g.slit_width_mm / 2;
  const tipHalf = mouthHalf * (g.slit_taper ?? 0);
  const narrowing = (mouthHalf - tipHalf) / g.slit_depth_mm;
  let best = rc;
  for (let k = 0; k < g.slit_count; k++) {
    const axis = (2 * Math.PI * k) / g.slit_count - Math.PI / 2;
    const delta = Math.atan2(Math.sin(theta - axis), Math.cos(theta - axis));
    const cosD = Math.cos(delta), sinD = Math.abs(Math.sin(delta));
    if (cosD <= 0) continue;
    const denom = sinD + narrowing * cosD;
    if (denom > 0) {
      const rWall = (mouthHalf + narrowing * rc) / denom;
      const depthAt = rWall * cosD - rc;
      if (depthAt >= 0 && depthAt <= g.slit_depth_mm) {
        best = Math.max(best, rWall);
        continue;
      }
    }
    const rTip = (rc + g.slit_depth_mm) / cosD;
    if (rTip * sinD <= tipHalf) best = Math.max(best, rTip);
  }
  return best;
}

// Full-circle void outline (mm) for the uncut grain's extrude hole.
function voidOutline(g) {
  const points = [];
  for (let i = 0; i < 360; i++) {
    const a = (2 * Math.PI * i) / 360;
    const r = innerRadiusAt(g, a);
    points.push([r * Math.cos(a), r * Math.sin(a)]);
  }
  return points;
}

function ringSectorShape(rIn, rOut, cut) {
  const shape = new THREE.Shape();
  if (!cut) {
    shape.absarc(0, 0, rOut, 0, Math.PI * 2, false);
    const hole = new THREE.Path();
    hole.absarc(0, 0, rIn, 0, Math.PI * 2, true);
    shape.holes.push(hole);
    return shape;
  }
  const a0 = SWEEP_START, a1 = SWEEP_START + SWEEP;
  shape.absarc(0, 0, rOut, a0, a1, false);
  shape.lineTo(rIn * Math.cos(a1), rIn * Math.sin(a1));
  shape.absarc(0, 0, rIn, a1, a0, true);
  shape.closePath();
  return shape;
}

function discSectorShape(r, cut) {
  const shape = new THREE.Shape();
  if (!cut) {
    shape.absarc(0, 0, r, 0, Math.PI * 2, false);
    return shape;
  }
  shape.moveTo(0, 0);
  shape.absarc(0, 0, r, SWEEP_START, SWEEP_START + SWEEP, false);
  shape.closePath();
  return shape;
}

// Grain cross-section (mm): outer arc, then the void boundary walked back,
// so slits appear as notches in the cut faces.
function grainShape(g, rOuter, cut) {
  if (!cut) {
    const shape = new THREE.Shape();
    shape.absarc(0, 0, rOuter, 0, Math.PI * 2, false);
    const hole = new THREE.Path();
    hole.setFromPoints(voidOutline(g).map(([x, y]) => new THREE.Vector2(x, y)));
    shape.holes.push(hole);
    return shape;
  }
  const a0 = SWEEP_START, a1 = SWEEP_START + SWEEP;
  const shape = new THREE.Shape();
  shape.absarc(0, 0, rOuter, a0, a1, false);
  const samples = 270;
  for (let i = 0; i <= samples; i++) {
    const a = a1 - (SWEEP * i) / samples;
    const r = innerRadiusAt(g, a);
    shape.lineTo(r * Math.cos(a), r * Math.sin(a));
  }
  shape.closePath();
  return shape;
}

export class MotorViewer {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.setClearColor(0x141413);

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

    this.grid = new THREE.GridHelper(1, 40, 0x33322f, 0x232221);
    this.scene.add(this.grid);

    this.group = null;
    this.cutaway = true;
    this.lastGeometry = null;
    this.viewDist = 0.45;

    this._resize();
    window.__ibViewer = this; // debug handle
    new ResizeObserver(() => this._resize()).observe(canvas.parentElement);
    this.renderer.setAnimationLoop(() => {
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
    });
  }

  _resize() {
    const w = this.canvas.parentElement.clientWidth - 2;
    const h = 380;
    if (w <= 0) return; // hidden tab — a zero/negative size corrupts the projection
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  _mesh(geometry, material) {
    const mesh = new THREE.Mesh(geometry, material);
    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(geometry, 30),
      new THREE.LineBasicMaterial({ color: 0x101010, transparent: true, opacity: 0.6 }),
    );
    mesh.add(edges);
    return mesh;
  }

  rebuild(g) {
    // NaN or a missing field would propagate silently through the scene and
    // blank the whole viewer (nothing renders, no error) — refuse it instead
    const dims = [g.outer_d_mm, g.core_d_mm, g.length_mm, g.segments,
      g.throat_d_mm, g.exit_d_mm, g.divergent_length_mm];
    if (!dims.every(Number.isFinite)) {
      console.warn("MotorViewer: skipped rebuild, non-finite geometry", g);
      return;
    }
    if (this.group) {
      this.scene.remove(this.group);
      this.group.traverse((o) => {
        o.geometry?.dispose();
        o.material?.dispose();
      });
    }
    this.lastGeometry = g;
    const cut = this.cutaway;
    const group = new THREE.Group();

    const rGrain = (g.outer_d_mm / 2) * MM;
    const rCase = rGrain + WALL * MM;
    const rt = (g.throat_d_mm / 2) * MM;
    const re = (g.exit_d_mm / 2) * MM;
    const segLen = g.length_mm * MM;
    const grainLen = g.segments * segLen + (g.segments - 1) * GAP * MM;
    const chamberLen = (BULKHEAD + FWD) * MM + grainLen + AFT * MM;
    const conv = rGrain - rt; // 45° convergent
    const div = g.divergent_length_mm * MM;
    const total = chamberLen + conv + div;

    const steel = new THREE.MeshStandardMaterial({ color: 0x9aa0a8, metalness: 0.85, roughness: 0.38, side: THREE.DoubleSide });
    const graphite = new THREE.MeshStandardMaterial({ color: 0x4c4944, metalness: 0.55, roughness: 0.6, side: THREE.DoubleSide });
    const fuel = new THREE.MeshStandardMaterial({ color: 0x3f8ce8, metalness: 0.05, roughness: 0.88, side: THREE.DoubleSide });

    const extrudeOpts = (depth) => ({ depth, bevelEnabled: false, curveSegments: 56 });

    // casing: true wall thickness, quarter-sectioned when cut
    const casingGeom = new THREE.ExtrudeGeometry(
      ringSectorShape(rGrain / MM, rCase / MM, cut), extrudeOpts(chamberLen / MM));
    casingGeom.scale(MM, MM, MM);
    casingGeom.rotateY(Math.PI / 2);
    group.add(this._mesh(casingGeom, steel));

    // forward bulkhead: solid disc filling the bore
    const capGeom = new THREE.ExtrudeGeometry(
      discSectorShape((rGrain / MM) * 0.999, cut), extrudeOpts(BULKHEAD));
    capGeom.scale(MM, MM, MM);
    capGeom.rotateY(Math.PI / 2);
    group.add(this._mesh(capGeom, steel));

    // grain segments
    const grainGeom = new THREE.ExtrudeGeometry(
      grainShape(g, (g.outer_d_mm / 2) * 0.998, cut), extrudeOpts(g.length_mm));
    grainGeom.scale(MM, MM, MM);
    grainGeom.rotateY(Math.PI / 2);
    for (let i = 0; i < g.segments; i++) {
      const seg = this._mesh(grainGeom.clone(), fuel);
      seg.position.x = (BULKHEAD + FWD) * MM + i * (segLen + GAP * MM);
      group.add(seg);
    }

    // nozzle: partial lathe plus profile caps on the cut planes
    // closed, non-self-intersecting profile: inlet → throat → exit along the
    // flow contour, then back along the outer shell (wall-offset from the
    // 45° convergent) to the casing radius
    const profile = [
      new THREE.Vector2(rGrain, 0),
      new THREE.Vector2(rt, conv),
      new THREE.Vector2(re, conv + div),
      new THREE.Vector2(re + WALL * MM, conv + div),
      new THREE.Vector2(rGrain - conv * 0.55 + WALL * MM, conv * 0.55),
      new THREE.Vector2(rCase, 0),
    ];
    const nozzleGroup = new THREE.Group();
    const lathe = new THREE.LatheGeometry(profile, 72, 0, cut ? SWEEP : Math.PI * 2);
    nozzleGroup.add(this._mesh(lathe, graphite));
    if (cut) {
      const capShape = new THREE.Shape(profile);
      const cap0 = new THREE.ShapeGeometry(capShape);
      cap0.rotateY(-Math.PI / 2); // lathe φ = 0 plane
      nozzleGroup.add(this._mesh(cap0, graphite));
      const cap1 = new THREE.ShapeGeometry(capShape);
      cap1.rotateY(Math.PI); // lathe φ = 270° plane
      nozzleGroup.add(this._mesh(cap1, graphite));
    }
    nozzleGroup.rotation.z = -Math.PI / 2;
    nozzleGroup.position.x = chamberLen;
    group.add(nozzleGroup);

    group.position.x = -total / 2;
    this.scene.add(group);
    this.group = group;

    this.viewDist = Math.max(total * 1.55, rCase * 8);
    // clamp orbit zoom: unbounded, one scroll gesture can carry the camera
    // past the far plane (or inside the model) and the scene goes blank
    this.controls.minDistance = rCase * 2.5;
    this.controls.maxDistance = Math.min(this.viewDist * 5, this.camera.far * 0.9);
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
    if (this.lastGeometry) this.rebuild(this.lastGeometry);
  }
}
