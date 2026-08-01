import { useEffect, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import * as THREE from 'three';

interface CameraIndicatorProperties {
  gltfData: GLTF;
}

/** Shows Blender-style camera objects (body + frustum wireframe) in the
 *  scene. The helpers attach to the glTF camera nodes, so they follow
 *  camera animation automatically during playback. */
export function CameraIndicator({ gltfData }: CameraIndicatorProperties) {
  const helpersReference = useRef<THREE.CameraHelper[]>([]);

  useEffect(() => {
    const helpers: THREE.CameraHelper[] = [];

    gltfData.scene.traverse((node) => {
      if ((node as THREE.PerspectiveCamera).isCamera) {
        const cameraNode = node as THREE.PerspectiveCamera;
        const helper = new THREE.CameraHelper(cameraNode);
        // Default colors are already Blender-style: frustum #ffaa00,
        // cone #ff0000, up #00aaff.
        // IMPORTANT: attach to the scene ROOT, not the camera node —
        // CameraHelper.matrix = camera.matrixWorld, so attaching it to
        // the camera itself double-applies the transform (wrong direction).
        gltfData.scene.add(helper);
        helpers.push(helper);
      }
    });

    helpersReference.current = helpers;
    return () => {
      for (const helper of helpers) {
        helper.parent?.remove(helper);
      }
      helpersReference.current = [];
    };
  }, [gltfData]);

  // CameraHelper must re-read projection each frame to stay accurate
  useFrame(() => {
    for (const helper of helpersReference.current) {
      helper.update();
    }
  });

  return null;
}
