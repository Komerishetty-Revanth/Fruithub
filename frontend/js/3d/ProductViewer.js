import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { FpsMonitor, TIERS } from "./PerformanceManager.js";

const RELIEF = 0.9;      // how far the middle of the fruit pushes toward you
const BUMP = 1.5;        // strength of the light shading on the relief

// Shows one product as a lit depth-relief made from the cutout and depth map.
export class ProductViewer {
  constructor(container, canvas, { cutoutUrl, depthUrl, tierName = "medium", onFail } = {}) {
    this.container = container;
    this.canvas = canvas;
    this.tier = TIERS[tierName] || TIERS.medium;
    this.onFail = onFail;
    this.t = 0;
    this.idle = true;
    this.disposed = false;
    this._inView = true;
    this.pointer = new THREE.Vector2(0, 0);
    this.smooth = new THREE.Vector2(0, 0);
    this.clock = new THREE.Clock();

    this.renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: this.tier.antialias });
    this.renderer.setClearColor(0x000000, 0);
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(35, 1, 0.1, 50);
    this.camera.position.set(0, 0, 9);

    if (this.tier.env) {
      const pmrem = new THREE.PMREMGenerator(this.renderer);
      this.envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
      pmrem.dispose();
      this.scene.environment = this.envTex;
    }
    this.scene.add(new THREE.HemisphereLight(0xfff1dd, 0x120a04, 0.7));
    this.key = new THREE.DirectionalLight(0xfff0d8, 2.2);   // follows the pointer
    this.key.position.set(2, 3, 6);
    this.rim = new THREE.DirectionalLight(0xffa24a, 1.1);
    this.rim.position.set(-4, 1, -3);
    this.scene.add(this.key, this.rim);

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enablePan = false;
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.minDistance = 4;
    this.controls.maxDistance = 13;
    this.controls.minAzimuthAngle = -1.05;     // limited, because this is a relief of one photo
    this.controls.maxAzimuthAngle = 1.05;
    this.controls.minPolarAngle = 1.0;
    this.controls.maxPolarAngle = 2.2;
    this.controls.saveState();

    let idleTimer = null;
    this.controls.addEventListener("start", () => {
      this.idle = false;
      clearTimeout(idleTimer);
    });
    this.controls.addEventListener("end", () => {
      idleTimer = setTimeout(() => (this.idle = true), 3000);
    });

    this._onMove = (e) => {
      const r = container.getBoundingClientRect();
      this.pointer.set(((e.clientX - r.left) / r.width) * 2 - 1, ((e.clientY - r.top) / r.height) * 2 - 1);
    };
    container.addEventListener("pointermove", this._onMove);

    this._ro = new ResizeObserver(() => this.resize());
    this._ro.observe(container);
    this._io = new IntersectionObserver(([e]) => (this._inView = e.isIntersecting));
    this._io.observe(canvas);
    this._onLost = (e) => {
      e.preventDefault();
      this.dispose();
      if (this.onFail) this.onFail();
    };
    canvas.addEventListener("webglcontextlost", this._onLost);

    this.fps = new FpsMonitor(() => {
      this.tier = { ...this.tier, pixelRatio: 1 };
      this.resize();
    });

    this.resize();
    this.ready = this._load(cutoutUrl, depthUrl);
    this._loop = this._loop.bind(this);
    this.raf = requestAnimationFrame(this._loop);
  }

  async _load(cutoutUrl, depthUrl) {
    const loader = new THREE.TextureLoader();
    loader.setCrossOrigin("anonymous");
    const [cut, depth] = await Promise.all([loader.loadAsync(cutoutUrl), loader.loadAsync(depthUrl)]);
    if (this.disposed) return;

    cut.colorSpace = THREE.SRGBColorSpace;
    cut.anisotropy = Math.min(4, this.renderer.capabilities.getMaxAnisotropy());

    const h = 4;
    const w = h * (cut.image.width / cut.image.height);
    const seg = Math.min(160, this.tier.segments * 3);
    this.mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(w, h, seg, seg),
      new THREE.MeshStandardMaterial({
        map: cut,
        displacementMap: depth, displacementScale: RELIEF, displacementBias: -RELIEF / 2,
        bumpMap: depth, bumpScale: BUMP,
        roughness: 0.45, metalness: 0, envMapIntensity: 0.5,
        transparent: true, alphaTest: 0.04, side: THREE.DoubleSide,
      })
    );
    this.scene.add(this.mesh);
  }

  resize() {
    const w = this.container.clientWidth || 400;
    const h = this.container.clientHeight || 400;
    this.renderer.setPixelRatio(Math.min(devicePixelRatio || 1, this.tier.pixelRatio));
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.fov = w / h < 0.9 ? 45 : 35;
    this.camera.updateProjectionMatrix();
  }

  reset() {
    this.controls.reset();
    this.idle = true;
  }

  zoom(factor) {
    const dir = this.camera.position.clone().sub(this.controls.target);
    const len = THREE.MathUtils.clamp(dir.length() * factor, this.controls.minDistance, this.controls.maxDistance);
    this.camera.position.copy(this.controls.target).add(dir.setLength(len));
    this.controls.update();
  }

  _loop() {
    if (this.disposed) return;
    this.raf = requestAnimationFrame(this._loop);
    if (document.hidden || !this._inView) {
      this.clock.getDelta();
      return;
    }
    const dt = Math.min(this.clock.getDelta(), 0.05);
    this.t += dt;

    this.smooth.lerp(this.pointer, 1 - Math.exp(-dt * 4));
    this.key.position.set(this.smooth.x * 4, 3 - this.smooth.y * 3, 6);   // the light follows the pointer

    if (this.mesh) {
      const targetY = this.idle ? Math.sin(this.t * 0.8) * 0.35 : 0;
      this.mesh.rotation.y += (targetY - this.mesh.rotation.y) * (1 - Math.exp(-dt * 3));
      this.mesh.position.y = Math.sin(this.t * 1.1) * 0.08;
    }
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    this.fps.tick(dt);
  }

  dispose() {
    if (this.disposed) return;
    this.disposed = true;
    cancelAnimationFrame(this.raf);
    this.container.removeEventListener("pointermove", this._onMove);
    this.canvas.removeEventListener("webglcontextlost", this._onLost);
    this._ro.disconnect();
    this._io.disconnect();
    this.controls.dispose();
    if (this.mesh) {
      this.mesh.geometry.dispose();
      const m = this.mesh.material;
      if (m.map) m.map.dispose();
      if (m.displacementMap) m.displacementMap.dispose();
      m.dispose();
    }
    if (this.envTex) this.envTex.dispose();
    this.renderer.dispose();
  }
}