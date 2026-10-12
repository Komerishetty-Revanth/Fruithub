import * as THREE from "three";

const S = (o) => o.segments;
const coat = (o, amount = 0.6) => (o.physical ? { clearcoat: amount, clearcoatRoughness: 0.25 } : {});
const mat = (opts, o) =>
  new (o.physical ? THREE.MeshPhysicalMaterial : THREE.MeshStandardMaterial)({ envMapIntensity: 0.55, ...opts });

function addMesh(group, geo, material, pos = [0, 0, 0], rot = [0, 0, 0], scale = [1, 1, 1]) {
  const m = new THREE.Mesh(geo, material);
  m.position.set(...pos);
  m.rotation.set(...rot);
  m.scale.set(...scale);
  m.castShadow = true;
  group.add(m);
  return m;
}

function canvasTexture(w, h, draw, srgb) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  return t;
}

const stemMat = (o) => mat({ color: 0x4a3320, roughness: 0.9 }, o);
const leafMat = (o) => mat({ color: 0x3f8f3a, roughness: 0.6 }, o);

function apple(o) {
  const g = new THREE.Group();
  const geo = new THREE.SphereGeometry(1, S(o), S(o));
  const p = geo.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), z = p.getZ(i);
    let y = p.getY(i) * 0.9;
    const r = Math.hypot(x, z);
    if (y > 0) y -= Math.max(0, 0.5 - r) * 0.55;      // dimple at the top
    else y += Math.max(0, 0.35 - r) * 0.3;            // dimple at the bottom
    const k = 1 + 0.06 * y;                           // slightly wider shoulders
    p.setXYZ(i, x * k, y, z * k);
  }
  geo.computeVertexNormals();
  addMesh(g, geo, mat({ color: 0xc4262e, roughness: 0.38, ...coat(o) }, o));
  addMesh(g, new THREE.CylinderGeometry(0.035, 0.05, 0.34, 8), stemMat(o), [0, 0.68, 0], [0, 0, 0.12]);
  addMesh(g, new THREE.SphereGeometry(0.2, 12, 8), leafMat(o), [0.22, 0.8, 0], [0, 0, 0.5], [1, 0.12, 0.55]);
  return g;
}

function mango(o) {
  const g = new THREE.Group();
  const geo = new THREE.SphereGeometry(1, S(o), S(o));
  const p = geo.attributes.position;
  const colors = new Float32Array(p.count * 3);
  const green = new THREE.Color(0xb9c53b), orange = new THREE.Color(0xf2802c), c = new THREE.Color();
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    const t = (x + 1) / 2;
    const taper = 1 - 0.25 * t * t;                   // narrower toward the tip
    p.setXYZ(i, x * 0.95, y * 0.8 * taper, z * 0.68 * taper);
    c.copy(green).lerp(orange, THREE.MathUtils.clamp(t * 1.1 + y * 0.15, 0, 1));
    colors[i * 3] = c.r;
    colors[i * 3 + 1] = c.g;
    colors[i * 3 + 2] = c.b;
  }
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  geo.computeVertexNormals();
  const inner = new THREE.Group();
  addMesh(inner, geo, mat({ vertexColors: true, roughness: 0.5, ...coat(o, 0.3) }, o));
  addMesh(inner, new THREE.CylinderGeometry(0.03, 0.045, 0.22, 8), stemMat(o), [-0.8, 0.42, 0], [0, 0, 0.9]);
  inner.rotation.z = 0.35;
  g.add(inner);
  return g;
}

function orange(o) {
  const g = new THREE.Group();
  const bump = canvasTexture(256, 128, (ctx, w, h) => {
    ctx.fillStyle = "#808080";
    ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 2200; i++) {
      const v = 100 + Math.floor(Math.random() * 80);
      ctx.fillStyle = `rgb(${v},${v},${v})`;
      ctx.beginPath();
      ctx.arc(Math.random() * w, Math.random() * h, 1.2, 0, Math.PI * 2);
      ctx.fill();
    }
  }, false);
  addMesh(g, new THREE.SphereGeometry(1, S(o), S(o)), mat({ color: 0xff8a1c, roughness: 0.55, bumpMap: bump, bumpScale: 0.6 }, o));
  addMesh(g, new THREE.SphereGeometry(0.1, 10, 8), leafMat(o), [0, 0.98, 0], [0, 0, 0], [1, 0.5, 1]);
  return g;
}

function banana(o) {
  const g = new THREE.Group();
  const curve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-1.1, 0.35, 0),
    new THREE.Vector3(-0.6, -0.3, 0),
    new THREE.Vector3(0.1, -0.55, 0),
    new THREE.Vector3(0.75, -0.3, 0),
    new THREE.Vector3(1.15, 0.3, 0),
  ]);
  const tub = Math.max(16, S(o)), rad = 6;
  const geo = new THREE.TubeGeometry(curve, tub, 0.19, rad, false);
  const p = geo.attributes.position;
  const v = new THREE.Vector3();
  for (let i = 0; i <= tub; i++) {                    // thinner at both ends
    const u = i / tub;
    const ctr = curve.getPointAt(u);
    const f = 0.55 + 0.45 * Math.pow(Math.sin(Math.PI * u), 0.4);
    for (let j = 0; j <= rad; j++) {
      const idx = i * (rad + 1) + j;
      v.set(p.getX(idx), p.getY(idx), p.getZ(idx)).sub(ctr).multiplyScalar(f).add(ctr);
      p.setXYZ(idx, v.x, v.y, v.z);
    }
  }
  geo.computeVertexNormals();
  addMesh(g, geo, mat({ color: 0xf3cf3a, roughness: 0.5 }, o), [0, 0.1, 0]);
  const tip = new THREE.SphereGeometry(0.09, 10, 8);
  const brown = mat({ color: 0x3a2a18, roughness: 0.8 }, o);
  const a = curve.getPointAt(0), b = curve.getPointAt(1);
  addMesh(g, tip, brown, [a.x, a.y + 0.1, a.z]);
  addMesh(g, tip, brown, [b.x, b.y + 0.1, b.z]);
  return g;
}

function grapes(o) {
  const g = new THREE.Group();
  const geo = new THREE.SphereGeometry(0.2, Math.max(10, S(o) >> 1), Math.max(8, S(o) >> 2));
  const m = mat({ color: 0x5b2a86, roughness: 0.28, ...coat(o, 0.5) }, o);
  const rows = [[7, 0.5, 0.55], [6, 0.44, 0.28], [5, 0.36, 0.02], [4, 0.26, -0.24], [2, 0.14, -0.5], [1, 0, -0.72]];
  rows.forEach(([n, r, y], ri) => {
    for (let k = 0; k < n; k++) {
      const a = (k / n) * Math.PI * 2 + ri * 0.6;
      const j = Math.sin(k * 12.9 + ri * 7.1) * 0.03;
      addMesh(g, geo, m, [Math.cos(a) * r + j, y + j, Math.sin(a) * r - j]);
    }
  });
  addMesh(g, new THREE.CylinderGeometry(0.03, 0.045, 0.5, 8), stemMat(o), [0, 0.88, 0], [0, 0, 0.15]);
  return g;
}

function watermelon(o) {
  const g = new THREE.Group();
  const tex = canvasTexture(512, 256, (ctx, w, h) => {
    ctx.fillStyle = "#2f8f46";
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = "#17592b";
    const n = 12;
    for (let i = 0; i < n; i++) {
      const x = (i + 0.5) * (w / n);
      ctx.beginPath();
      ctx.moveTo(x - 14, 0);
      for (let y = 0; y <= h; y += 16) ctx.lineTo(x - 14 + Math.sin(y * 0.05 + i) * 8, y);
      for (let y = h; y >= 0; y -= 16) ctx.lineTo(x + 14 + Math.sin(y * 0.05 + i) * 8, y);
      ctx.closePath();
      ctx.fill();
    }
  }, true);
  addMesh(g, new THREE.SphereGeometry(1, S(o), S(o)), mat({ map: tex, roughness: 0.45 }, o), [0, 0, 0], [0, 0, 0], [1.15, 0.92, 0.92]);
  addMesh(g, new THREE.CylinderGeometry(0.04, 0.06, 0.18, 8), stemMat(o), [0, 0.9, 0]);
  return g;
}

function pomegranate(o) {
  const g = new THREE.Group();
  addMesh(g, new THREE.SphereGeometry(1, S(o), S(o)), mat({ color: 0x9a1b30, roughness: 0.4, ...coat(o, 0.4) }, o), [0, 0, 0], [0, 0, 0], [1, 0.95, 1]);
  const crown = mat({ color: 0x7d1426, roughness: 0.6 }, o);
  addMesh(g, new THREE.CylinderGeometry(0.1, 0.17, 0.2, 8), crown, [0, 0.95, 0]);
  for (let i = 0; i < 5; i++) {
    const a = (i / 5) * Math.PI * 2;
    addMesh(g, new THREE.ConeGeometry(0.05, 0.22, 6), crown,
      [Math.cos(a) * 0.12, 1.07, Math.sin(a) * 0.12],
      [Math.sin(a) * 0.35, 0, -Math.cos(a) * 0.35]);
  }
  return g;
}

function juice(o) {
  const g = new THREE.Group();
  const glass = mat({ color: 0xf28c28, roughness: 0.24, metalness: 0.04 }, o);
  const cap = mat({ color: 0xf1eee6, roughness: 0.35 }, o);
  addMesh(g, new THREE.CylinderGeometry(0.42, 0.33, 1.25, S(o)), glass, [0, -0.05, 0]);
  addMesh(g, new THREE.CylinderGeometry(0.34, 0.34, 0.12, S(o)), cap, [0, 0.64, 0]);
  addMesh(g, new THREE.CylinderGeometry(0.24, 0.24, 0.23, S(o)), cap, [0, 0.79, 0]);
  addMesh(g, new THREE.CylinderGeometry(0.2, 0.2, 0.035, S(o)), stemMat(o), [0, 0.92, 0]);
  return g;
}

function dryfruits(o) {
  const g = new THREE.Group();
  const segments = Math.max(12, S(o));
  const bowlMat = mat({ color: 0x70401f, roughness: 0.62, ...coat(o, 0.18) }, o);
  const insideMat = mat({ color: 0x352013, roughness: 0.9 }, o);
  const almondMat = mat({ color: 0xa96532, roughness: 0.68 }, o);
  const cashewMat = mat({ color: 0xe2bd78, roughness: 0.72 }, o);
  const pistachioMat = mat({ color: 0xc3a56a, roughness: 0.78 }, o);
  const kernelMat = mat({ color: 0x789044, roughness: 0.78 }, o);
  const walnutMat = mat({ color: 0x80512e, roughness: 0.82 }, o);
  const raisinMat = mat({ color: 0x452436, roughness: 0.42 }, o);

  addMesh(g, new THREE.CylinderGeometry(0.68, 0.5, 0.32, segments, 1, true),
    bowlMat, [0, -0.27, 0]);
  addMesh(g, new THREE.CylinderGeometry(0.52, 0.43, 0.025, segments),
    insideMat, [0, -0.105, 0]);
  addMesh(g, new THREE.TorusGeometry(0.68, 0.035, 6, segments),
    bowlMat, [0, -0.1, 0]);
  addMesh(g, new THREE.CylinderGeometry(0.46, 0.46, 0.07, segments),
    bowlMat, [0, -0.45, 0]);

  const almondGeometry = new THREE.SphereGeometry(0.19, segments, Math.max(8, segments >> 1));
  const almondPositions = almondGeometry.attributes.position;
  for (let i = 0; i < almondPositions.count; i++) {
    const y = almondPositions.getY(i);
    const taper = 0.68 + 0.32 * (1 - Math.abs(y) ** 1.5);
    almondPositions.setX(i, almondPositions.getX(i) * taper);
    almondPositions.setZ(i, almondPositions.getZ(i) * taper);
  }
  almondGeometry.computeVertexNormals();
  [
    [-0.38, 0.14, 0.04, -0.55],
    [0.05, 0.22, 0.24, 0.8],
    [0.42, 0.12, 0.08, -0.2],
  ].forEach(([x, y, z, rotation]) => {
    addMesh(g, almondGeometry, almondMat, [x, y, z], [0.15, 0, rotation], [0.78, 1.45, 0.78]);
  });

  const cashewCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-0.12, 0.04, 0),
    new THREE.Vector3(-0.2, 0.15, 0),
    new THREE.Vector3(-0.08, 0.28, 0),
    new THREE.Vector3(0.13, 0.25, 0),
    new THREE.Vector3(0.18, 0.1, 0),
  ]);
  const cashewGeometry = new THREE.TubeGeometry(cashewCurve, 18, 0.075, 8, false);
  [
    [-0.36, 0.11, -0.28, 0.1],
    [0.35, 0.13, -0.3, -0.7],
  ].forEach(([x, y, z, rotation]) => {
    addMesh(g, cashewGeometry, cashewMat, [x, y, z], [0, 0, rotation]);
  });

  [
    [-0.05, 0.12, -0.23, 0.45],
    [0.18, 0.2, 0.05, -0.5],
  ].forEach(([x, y, z, rotation]) => {
    const shell = new THREE.Group();
    addMesh(shell, new THREE.SphereGeometry(0.19, segments, Math.max(8, segments >> 1)),
      pistachioMat, [0, 0, 0], [0, 0, rotation], [0.72, 1.05, 0.48]);
    addMesh(shell, new THREE.SphereGeometry(0.12, segments, Math.max(8, segments >> 1)),
      kernelMat, [0.045, 0.015, 0.09], [0, 0, rotation], [0.62, 0.83, 0.35]);
    shell.position.set(x, y, z);
    g.add(shell);
  });

  const walnutGeometry = new THREE.SphereGeometry(0.18, segments, Math.max(8, segments >> 1));
  const walnutPositions = walnutGeometry.attributes.position;
  for (let i = 0; i < walnutPositions.count; i++) {
    const x = walnutPositions.getX(i), y = walnutPositions.getY(i), z = walnutPositions.getZ(i);
    const ridge = 1 + 0.075 * Math.sin(Math.atan2(z, x) * 9 + y * 5);
    walnutPositions.setXYZ(i, x * ridge, y * ridge, z * ridge);
  }
  walnutGeometry.computeVertexNormals();
  addMesh(g, walnutGeometry, walnutMat, [0.02, 0.13, 0.33], [0.2, 0.25, 0.4], [1.05, 0.88, 0.8]);

  const raisinGeometry = new THREE.SphereGeometry(0.11, segments, Math.max(8, segments >> 1));
  [
    [-0.42, 0.11, 0.31], [-0.24, 0.17, 0.36], [0.36, 0.12, 0.34],
  ].forEach(([x, y, z], i) => {
    addMesh(g, raisinGeometry, raisinMat, [x, y, z], [0, i * 0.8, i * 0.35], [0.8, 1.18, 0.76]);
  });
  return g;
}

const BUILDERS = { apple, mango, orange, banana, grapes, watermelon, pomegranate, juice, dryfruits };
const BASE_SCALE = {
  apple: 1, mango: 1.05, orange: 0.95, banana: 1, grapes: 1.1,
  watermelon: 1.25, pomegranate: 0.9, juice: 1.1, dryfruits: 1.2,
};

export function createFruit(type, tierSettings) {
  const g = BUILDERS[type](tierSettings);
  g.scale.setScalar(BASE_SCALE[type]);
  g.userData.type = type;
  return g;
}

export function disposeObject(obj) {
  obj.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    if (o.material) {
      (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => {
        if (m.map) m.map.dispose();
        if (m.bumpMap) m.bumpMap.dispose();
        m.dispose();
      });
    }
  });
}