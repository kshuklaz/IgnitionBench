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

// Distance from the axis to the void boundary along the ray at theta (mm),
// for the cross-section at kerf scale s (1 at the face, slit_taper where the
// cut ends, 0 past it). Mirrors grain3d.segment_mesh exactly.
function innerRadiusAt(g, theta, scale) {
  const rc = g.core_d_mm / 2;
  const w2 = (g.slit_width_mm / 2) * scale;
  if (!g.slit_count || w2 <= 0) return rc;
  const tip = rc + g.slit_depth_mm * scale;
  let best = rc;
  for (let k = 0; k < g.slit_count; k++) {
    const axis = (2 * Math.PI * k) / g.slit_count - Math.PI / 2;
    const delta = Math.atan2(Math.sin(theta - axis), Math.cos(theta - axis));
    const c = Math.cos(delta), s = Math.abs(Math.sin(delta));
    if (c <= 0) continue;
    if (tip * s <= w2) best = Math.max(best, tip / c); // exits the flat end wall
    else if (w2 / s > rc) best = Math.max(best, w2 / s); // exits a side wall
  }
  return best;
}

// (z, scale) mesh rings for one segment whose forward face sits offsetMm
// along the single cut that runs aft from the motor front; the duplicate-z
// pair marks the flat wall where the cut ends inside this segment, while a
// cut that carries through leaves an open mouth on the aft face.
function ringList(g, offsetMm) {
  const L = g.length_mm;
  const Lc = g.slit_length_mm || 0;
  if (!g.slit_count || offsetMm >= Lc) return [[0, 0], [L, 0]];
  const taper = g.slit_taper ?? 0;
  const scale = (along) => 1 - (along / Lc) * (1 - taper);
  const local = Math.min(L, Lc - offsetMm);
  const steps = 12;
  const rings = [];
  for (let j = 0; j <= steps; j++) {
    const z = (local * j) / steps;
    rings.push([z, scale(offsetMm + z)]);
  }
  if (local < L) rings.push([local, 0], [L, 0]);
  return rings;
}

// Grain segment as a triangle soup (mm): inner surface with tapered slit
// pockets, end faces, outer wall, and — when cut — capped section profiles.
function grainGeometry(g, rOuter, cut, offsetMm) {
  const rings = ringList(g, offsetMm);
  const a0 = cut ? SWEEP_START : 0;
  const span = cut ? SWEEP : Math.PI * 2;
  const M = cut ? 216 : 256;
  const rIn = rings.map(([, s]) => {
    const row = new Float64Array(M + 1);
    for (let i = 0; i <= M; i++) row[i] = innerRadiusAt(g, a0 + (span * i) / M, s);
    return row;
  });
  const cos = new Float64Array(M + 1), sin = new Float64Array(M + 1);
  for (let i = 0; i <= M; i++) {
    cos[i] = Math.cos(a0 + (span * i) / M);
    sin[i] = Math.sin(a0 + (span * i) / M);
  }

  const pos = [];
  const tri = (a, b, c) => pos.push(...a, ...b, ...c);
  const quad = (a, b, c, d) => { tri(a, b, c); tri(a, c, d); };
  const P = (j, i) => [rIn[j][i] * cos[i], rIn[j][i] * sin[i], rings[j][0]];
  const O = (i, z) => [rOuter * cos[i], rOuter * sin[i], z];
  const L = g.length_mm;

  for (let i = 0; i < M; i++) {
    for (let j = 0; j < rings.length - 1; j++) {
      if (rings[j + 1][0] > rings[j][0]) {
        quad(P(j, i), P(j + 1, i), P(j + 1, i + 1), P(j, i + 1)); // wall band
      } else if (
        Math.abs(rIn[j][i] - rIn[j + 1][i]) > 1e-9 ||
        Math.abs(rIn[j][i + 1] - rIn[j + 1][i + 1]) > 1e-9
      ) {
        quad(P(j, i), P(j, i + 1), P(j + 1, i + 1), P(j + 1, i)); // cut-end wall
      }
    }
    const jl = rings.length - 1;
    quad(P(0, i), P(0, i + 1), O(i + 1, 0), O(i, 0)); // near face
    quad(P(jl, i), O(i, L), O(i + 1, L), P(jl, i + 1)); // far face
    quad(O(i, 0), O(i + 1, 0), O(i + 1, L), O(i, L)); // outer wall
  }

  if (cut) {
    // capped section profile at each cut plane: outer wall down the length,
    // then the inner boundary walked back with its slit steps
    for (const phi of [a0, a0 + span]) {
      const pts = [new THREE.Vector2(rOuter, 0), new THREE.Vector2(rOuter, L)];
      for (let j = rings.length - 1; j >= 0; j--) {
        pts.push(new THREE.Vector2(innerRadiusAt(g, phi, rings[j][1]), rings[j][0]));
      }
      const faces = THREE.ShapeUtils.triangulateShape(pts, []);
      const c = Math.cos(phi), s = Math.sin(phi);
      for (const [ia, ib, ic] of faces) {
        tri(
          [pts[ia].x * c, pts[ia].x * s, pts[ia].y],
          [pts[ib].x * c, pts[ib].x * s, pts[ib].y],
          [pts[ic].x * c, pts[ic].x * s, pts[ic].y],
        );
      }
    }
  }

  const geom = new THREE.BufferGeometry();
  geom.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  geom.computeVertexNormals();
  return geom;
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

    // grain segments: parametric surface with the slit pockets. The single
    // cut runs aft from the motor front, so each segment gets its own
    // geometry at its offset along the cut. (Triangle soup — skip the edge
    // overlay, it would outline every facet.)
    for (let i = 0; i < g.segments; i++) {
      const grainGeom = grainGeometry(
        g, (g.outer_d_mm / 2) * 0.998, cut, i * g.length_mm);
      grainGeom.scale(MM, MM, MM);
      grainGeom.rotateY(Math.PI / 2);
      const seg = new THREE.Mesh(grainGeom, fuel);
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
