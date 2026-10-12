import * as THREE from "three";
import { FpsMonitor, TIERS, lowerTier } from "./PerformanceManager.js";
import { createLighting } from "./Lighting.js";
import { createEnvironment } from "./Environment.js";
import { createFruit, disposeObject } from "./FruitModel.js";
import { CameraController } from "./CameraController.js";

// Put each product type near the front so reduced tiers still show the whole catalog.
const ORDER = ["mango", "juice", "apple", "dryfruits", "orange", "grapes", "banana", "watermelon", "pomegranate"];

const easeOutBack = (k) => {
  const c1 = 1.70158, c3 = c1 + 1;
  return 1 + c3 * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2);
};

export class FruitScene {
  constructor(canvas, tierName, { onFail } = {}) {
    this.canvas = canvas;
    this.tierName = tierName;
    this.tier = TIERS[tierName];
    this.onFail = onFail;
    this.t = 0;
    this.orbit = 0;
    this.revealAt = null;
    this.disposed = false;
    this._inView = true;
    this.clock = new THREE.Clock();

    this.renderer = new THREE.WebGLRenderer({
      canvas, alpha: true, antialias: this.tier.antialias, powerPreference: "high-performance",
    });
    this.renderer.setClearColor(0x000000, 0);       // transparent: the page stays black
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.renderer.shadowMap.enabled = this.tier.shadows;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
    this.controller = new CameraController(this.camera);
    this.lights = createLighting(this.scene, this.tier);
    this.env = createEnvironment(this.renderer, this.scene, this.tier);

    this.ring = new THREE.Group();
    this.ring.rotation.x = 0.2;
    this.scene.add(this.ring);

    this.fruits = ORDER.slice(0, this.tier.fruits).map((type, i) => {
      const holder = new THREE.Group();
      holder.add(createFruit(type, this.tier));
      holder.userData = { phase: i * 1.3, spin: 0.35 + (i % 3) * 0.12 };
      holder.scale.setScalar(0.0001);               // grows in when reveal() is called
      this.ring.add(holder);
      return holder;
    });

    this.fps = new FpsMonitor(() => this.downgrade());

    this._onResize = () => this.resize();
    addEventListener("resize", this._onResize);
    this._onLost = (e) => {
      e.preventDefault();
      this.dispose();
      if (this.onFail) this.onFail();
    };
    canvas.addEventListener("webglcontextlost", this._onLost);
    this._io = new IntersectionObserver(([entry]) => (this._inView = entry.isIntersecting));
    this._io.observe(canvas);

    this.resize();
    this._loop = this._loop.bind(this);
    this.raf = requestAnimationFrame(this._loop);
  }

  get active() {
    return !document.hidden && this._inView;
  }

  resize() {
    const w = this.canvas.clientWidth || innerWidth;
    const h = this.canvas.clientHeight || innerHeight;
    this.renderer.setPixelRatio(Math.min(devicePixelRatio || 1, this.tier.pixelRatio));
    this.renderer.setSize(w, h, false);
    this.controller.fit(w, h);
    this.layout(w / h);
  }

  // Places the visible fruits evenly on a wide, shallow ellipse.
  layout(aspect) {
    const portrait = aspect < 1;
    this.rx = portrait ? 1.8 : THREE.MathUtils.clamp(aspect * 2.6, 3.2, 4.4);
    this.rz = this.rx * (portrait ? 0.45 : 0.4);
    this.fruitScale = portrait ? 0.55 : 0.85;
    const shown = this.fruits.filter((h) => h.visible);
    shown.forEach((h, i) => {
      const a = (i / shown.length) * Math.PI * 2;
      h.position.set(Math.cos(a) * this.rx, 0, Math.sin(a) * this.rz);
    });
  }

  // Call once the intro is finished.
  reveal() {
    if (this.revealAt === null) {
      this.revealAt = this.t;
      this.controller.introOffset = 4.5;
    }
  }

  _loop() {
    if (this.disposed) return;
    this.raf = requestAnimationFrame(this._loop);
    if (!this.active) {
      this.clock.getDelta();                        // keep the clock current while paused
      return;
    }
    const dt = Math.min(this.clock.getDelta(), 0.05);
    this.t += dt;
    this.update(dt);
    this.renderer.render(this.scene, this.camera);
    this.fps.tick(dt);
  }

  update(dt) {
    const t = this.t;
    const c = this.controller.current;

    this.orbit += dt * 0.22;
    this.ring.rotation.y = this.orbit + c.x * 0.35;   // follows the pointer
    this.ring.rotation.x = 0.2 + c.y * 0.12;

    this.fruits.forEach((h, i) => {
      const u = h.userData;
      const k = this.revealAt === null ? 0 : THREE.MathUtils.clamp((t - this.revealAt - i * 0.12) / 0.9, 0, 1);
      h.scale.setScalar(Math.max(0.0001, this.fruitScale * easeOutBack(k)));
      h.position.y = Math.sin(t * 0.9 + u.phase) * 0.25;
      const model = h.children[0];
      model.rotation.y += dt * u.spin;
      model.rotation.z = Math.sin(t * 0.6 + u.phase) * 0.12;
    });

    this.controller.update(dt);
    this.env.update(t);
  }

  downgrade() {
    const next = lowerTier(this.tierName);
    if (next === "static") {
      this.dispose();
      if (this.onFail) this.onFail();
      return;
    }
    this.tierName = next;
    this.tier = TIERS[next];
    this.renderer.shadowMap.enabled = this.tier.shadows;
    this.lights.setShadows(this.tier.shadows);
    this.env.apply(this.tier);
    this.fruits.forEach((h, i) => (h.visible = i < this.tier.fruits));
    this.scene.traverse((o) => {
      if (o.material) o.material.needsUpdate = true;
    });
    this.resize();
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    removeEventListener("resize", this._onResize);
    this.canvas.removeEventListener("webglcontextlost", this._onLost);
    this._io.disconnect();
    this.controller.dispose();
    this.env.dispose();
    disposeObject(this.ring);
    this.renderer.dispose();
  }
}