import * as THREE from "three";

export function createLighting(scene, tier) {
  const hemi = new THREE.HemisphereLight(0xfff1dd, 0x120a04, 0.55);

  const key = new THREE.DirectionalLight(0xfff0d8, 2.4); // warm main light
  key.position.set(4, 7, 5);
  key.castShadow = tier.shadows;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.camera.left = -8;
  key.shadow.camera.right = 8;
  key.shadow.camera.top = 8;
  key.shadow.camera.bottom = -8;
  key.shadow.camera.near = 1;
  key.shadow.camera.far = 25;
  key.shadow.bias = -0.0005;
  key.shadow.radius = 4;

  const rim = new THREE.DirectionalLight(0xffa24a, 1.5); // orange edge light from behind
  rim.position.set(-5, 2, -4);

  const fill = new THREE.DirectionalLight(0x9fb7ff, 0.45); // soft cool fill from the front
  fill.position.set(0, 1, 8);

  scene.add(hemi, key, rim, fill);

  return {
    setShadows(on) {
      key.castShadow = on;
    },
  };
}