import { useEffect, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import * as THREE from 'three';

interface CameraIndicatorProperties {
  gltfData: GLTF;
}

/** Frustum wireframe length limit (meters). The original camera far
 *  plane is often 1000m — way too long for a wireframe hint. */
const FRUSTUM_DISPLAY_FAR = 6;

interface CameraVisualization {
  helperCamera: THREE.PerspectiveCamera;
  helper: THREE.CameraHelper;
  cameraNode: THREE.PerspectiveCamera;
}

/** Shows Blender-style camera objects in the Free View:
 *  - semi-transparent cone body at the camera position
 *  - shortened frustum wireframe pointing along the camera direction
 *  Both follow the camera's animation automatically. */
export function CameraIndicator({ gltfData }: CameraIndicatorProperties) {
  const visualizationsReference = useRef<CameraVisualization[]>([]);

  useEffect(() => {
    const visualizations: CameraVisualization[] = [];

    gltfData.scene.traverse((node) => {
      if ((node as THREE.PerspectiveCamera).isCamera) {
        const cameraNode = node as THREE.PerspectiveCamera;

        // 1. Semi-transparent cone body at the camera position.
        // Cone geometry points +Y by default; rotate so the tip points
        // -Z (the camera's forward direction), like Blender's camera.
        const body = new THREE.Mesh(
          new THREE.ConeGeometry(0.18, 0.4, 12),
          new THREE.MeshBasicMaterial({
            color: '#ff8c42',
            transparent: true,
            opacity: 0.5,
            depthWrite: false,
          }),
        );
        body.rotation.x = -Math.PI / 2;
        cameraNode.add(body);

        // 2. Shortened frustum wireframe.
        // Clone the camera with a small far plane so the wireframe
        // doesn't extend hundreds of meters. The helper must be attached
        // to the scene ROOT (CameraHelper.matrix = camera.matrixWorld,
        // attaching to the camera node would double-apply the transform).
        const helperCamera = cameraNode.clone() as THREE.PerspectiveCamera;
        helperCamera.far = FRUSTUM_DISPLAY_FAR;
        helperCamera.updateProjectionMatrix();

        const helper = new THREE.CameraHelper(helperCamera);
        gltfData.scene.add(helper);

        visualizations.push({ helperCamera, helper, cameraNode });
      }
    });

    visualizationsReference.current = visualizations;
    return () => {
      for (const visualization of visualizations) {
        visualization.helperCamera.parent?.remove(visualization.helperCamera);
        visualization.helper.parent?.remove(visualization.helper);
        visualization.cameraNode.remove(
          ...visualization.cameraNode.children.filter(
            (child) => child instanceof THREE.Mesh && child.material instanceof THREE.MeshBasicMaterial,
          ),
        );
      }
      visualizationsReference.current = [];
    };
  }, [gltfData]);

  // Sync the clone's world transform with the real camera node each frame
  // (the clone is not part of the scene graph, so it won't update itself).
  useFrame(() => {
    for (const visualization of visualizationsReference.current) {
      visualization.helperCamera.matrixWorld.copy(visualization.cameraNode.matrixWorld);
      visualization.helper.update();
    }
  });

  return null;
}
