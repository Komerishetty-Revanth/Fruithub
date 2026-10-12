import * as THREE from "three";

// Follows the mouse or finger, and frames the scene for landscape or portrait screens.
export class CameraController {
  constructor(camera) {
    this.camera = camera;
    this.target = new THREE.Vector2(0, 0);
    this.current = new THREE.Vector2(0, 0);
    this.base = new THREE.Vector3(0, 0.6, 9.5);
    this.introOffset = 0; // the camera glides in from further back after the intro

    const move = (x, y) => this.target.set((x / innerWidth) * 2 - 1, (y / innerHeight) * 2 - 1);
    this._pointer = (e) => move(e.clientX, e.clientY);
    this._touch = (e) => {
      const t = e.touches[0];
      if (t) move(t.clientX, t.clientY);
    };
    addEventListener("pointermove", this._pointer);
    addEventListener("touchstart", this._touch, { passive: true });
    addEventListener("touchmove", this._touch, { passive: true });
  }

  fit(width, height) {
    const aspect = width / height;
    const portrait = aspect < 1;
    this.camera.aspect = aspect;
    this.camera.fov = portrait ? 50 : 35;
    this.base.set(0, portrait ? 0.3 : 0.6, portrait ? 11 : 9.5);
    this.camera.updateProjectionMatrix();
  }

  update(dt) {
    this.current.lerp(this.target, 1 - Math.exp(-dt * 3));
    this.introOffset += (0 - this.introOffset) * (1 - Math.exp(-dt * 2.2));
    this.camera.position.set(
      this.base.x + this.current.x * 0.9,
      this.base.y - this.current.y * 0.6,
      this.base.z + this.introOffset
    );
    this.camera.lookAt(0, 0, 0);
  }

  dispose() {
    removeEventListener("pointermove", this._pointer);
    removeEventListener("touchstart", this._touch);
    removeEventListener("touchmove", this._touch);
  }
}