import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

// Soft reflections, a shadow-catching floor, and slowly drifting golden dust.
export function createEnvironment(renderer, scene, tier) {
  let envTex = null;
  if (tier.env) {
    const pmrem = new THREE.PMREMGenerator(renderer);
    envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
    scene.environment = envTex;
  }

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(40, 40),
    new THREE.ShadowMaterial({ opacity: 0.45 })
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -2.3;
  ground.receiveShadow = true;
  ground.visible = tier.shadows;
  scene.add(ground);

  let points = null;
  if (tier.particles > 0) {
    const pos = new Float32Array(tier.particles * 3);
    for (let i = 0; i < tier.particles; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 16;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 9;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 8 - 1;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    points = new THREE.Points(
      geo,
      new THREE.PointsMaterial({ color: 0xffb02e, size: 0.045, transparent: true, opacity: 0.55, depthWrite: false })
    );
    scene.add(points);
  }

  return {
    update(t) {
      if (points) {
        points.rotation.y = t * 0.02;
        points.position.y = Math.sin(t * 0.3) * 0.15;
      }
    },
    apply(newTier) {
      ground.visible = newTier.shadows;
      if (points) points.visible = newTier.particles > 0;
      scene.environment = newTier.env ? envTex : null;
    },
    dispose() {
      ground.geometry.dispose();
      ground.material.dispose();
      if (points) {
        points.geometry.dispose();
        points.material.dispose();
      }
      if (envTex) envTex.dispose();
    },
  };
}