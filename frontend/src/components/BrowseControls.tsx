import { useEffect, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

interface BrowseControlsProperties {
  enabled: boolean;
}

/** Game-style camera movement for the Free View:
 *  - W/S: forward/back (horizontal, along camera facing)
 *  - A/D: strafe left/right
 *  - Q/E: move down/up
 *  The orbit target moves together with the camera, so orbiting still
 *  revolves around the new vantage point. */
export function BrowseControls({ enabled }: BrowseControlsProperties) {
  const camera = useThree((state) => state.camera);
  const controls = useThree((state) => state.controls) as unknown as {
    target: THREE.Vector3;
    update: () => void;
  } | null;
  const pressedKeys = useRef(new Set<string>());

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      pressedKeys.current.add(event.key.toLowerCase());
    };
    const handleKeyUp = (event: KeyboardEvent) => {
      pressedKeys.current.delete(event.key.toLowerCase());
    };
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  useFrame((_, delta) => {
    if (!enabled || !controls) return;

    const speed = 5 * delta; // meters per second

    // Forward = full camera facing direction (fly mode: includes pitch,
    // so looking up and pressing W moves the camera upward too)
    const forward = new THREE.Vector3();
    camera.getWorldDirection(forward);
    forward.normalize();

    const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize();

    const movement = new THREE.Vector3();
    if (pressedKeys.current.has('w')) movement.add(forward);
    if (pressedKeys.current.has('s')) movement.sub(forward);
    if (pressedKeys.current.has('d')) movement.add(right);
    if (pressedKeys.current.has('a')) movement.sub(right);
    if (pressedKeys.current.has('q')) movement.y -= 1;
    if (pressedKeys.current.has('e')) movement.y += 1;

    if (movement.lengthSq() > 0) {
      movement.normalize().multiplyScalar(speed);
      camera.position.add(movement);
      controls.target.add(movement);
      controls.update();
    }
  });

  return null;
}
