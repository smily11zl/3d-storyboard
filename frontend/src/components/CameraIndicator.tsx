import { useEffect, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { useStore, isCameraActive } from '../store';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import * as THREE from 'three';

interface CameraIndicatorProperties {
  gltfData: GLTF;
}

/** Frustum wireframe length limit (meters). The original camera far
 *  plane is often 1000m — way too long for a wireframe hint. */
const FRUSTUM_DISPLAY_FAR = 6;

/** 生效（当前时间点在段内）→ 蓝；未生效（待机）→ 红。 */
const ACTIVE_COLOR = '#2f7bff';
const INACTIVE_COLOR = '#ff4d4f';

interface CameraVisualization {
  cameraNode: THREE.PerspectiveCamera;
  helperCamera: THREE.PerspectiveCamera;
  frustumLines: THREE.LineSegments;
  frustumPositions: Float32Array;
  bodyMaterial: THREE.MeshBasicMaterial;
  frustumMaterial: THREE.LineDashedMaterial;
}

/** Shows Blender-style camera objects in the Free View:
 *  - semi-transparent cone body at the camera position
 *  - shortened frustum wireframe pointing along the camera direction
 *  Both follow the camera's animation automatically.
 *
 *  颜色区分「生效/未生效」：生效蓝、未生效红。
 *  线型区分「选中/未选中」：选中实线、未选中虚线。
 *
 *  The frustum is drawn manually (12 lines: near/far rectangles + 4
 *  connectors) instead of using CameraHelper, because:
 *  - CameraHelper draws its own cone + up line → duplicate cone shapes
 *  - CameraHelper reads a stale matrixWorld in useFrame → jitter while paused */
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
        const bodyMaterial = new THREE.MeshBasicMaterial({
          color: INACTIVE_COLOR,
          transparent: true,
          opacity: 0.5,
          depthWrite: false,
        });
        const body = new THREE.Mesh(new THREE.ConeGeometry(0.18, 0.4, 12), bodyMaterial);
        body.rotation.x = -Math.PI / 2;
        cameraNode.add(body);

        // 2. Shortened frustum wireframe (self-drawn, 12 lines).
        // Clone the camera with a small far plane so the wireframe
        // doesn't extend hundreds of meters.
        const helperCamera = cameraNode.clone() as THREE.PerspectiveCamera;
        helperCamera.far = FRUSTUM_DISPLAY_FAR;
        helperCamera.updateProjectionMatrix();

        const frustumPositions = new Float32Array(24 * 3); // 24 vertices
        const frustumGeometry = new THREE.BufferGeometry();
        frustumGeometry.setAttribute('position', new THREE.BufferAttribute(frustumPositions, 3));
        const frustumMaterial = new THREE.LineDashedMaterial({
          color: INACTIVE_COLOR,
          dashSize: 0.15,
          gapSize: 0.12,
        });
        const frustumLines = new THREE.LineSegments(frustumGeometry, frustumMaterial);
        gltfData.scene.add(frustumLines);

        visualizations.push({
          cameraNode,
          helperCamera,
          frustumLines,
          frustumPositions,
          bodyMaterial,
          frustumMaterial,
        });
      }
    });

    visualizationsReference.current = visualizations;
    return () => {
      for (const visualization of visualizations) {
        visualization.cameraNode.remove(
          ...visualization.cameraNode.children.filter(
            (child) => child instanceof THREE.Mesh && child.material instanceof THREE.MeshBasicMaterial,
          ),
        );
        visualization.frustumLines.geometry.dispose();
        visualization.frustumLines.material.dispose();
        visualization.frustumLines.parent?.remove(visualization.frustumLines);
      }
      visualizationsReference.current = [];
    };
  }, [gltfData]);

  // Recompute frustum vertices each frame from the CURRENT camera
  // transform, and update color/dash from the current state.
  useFrame(() => {
    const store = useStore.getState();
    const activeCameraName = store.activeCameraName;
    const currentTime = store.currentTime;

    for (const visualization of visualizationsReference.current) {
      const {
        cameraNode,
        helperCamera,
        frustumLines,
        frustumPositions,
        bodyMaterial,
        frustumMaterial,
      } = visualization;

      cameraNode.updateWorldMatrix(true, false);
      helperCamera.matrixWorld.copy(cameraNode.matrixWorld);

      // 生效/未生效（颜色）：有段看段覆盖，无段看该相机是否有动画。
      const cameraName = cameraNode.name;
      const isActive = isCameraActive(store.shot, cameraName, currentTime);
      const color = isActive ? ACTIVE_COLOR : INACTIVE_COLOR;
      bodyMaterial.color.set(color);
      frustumMaterial.color.set(color);

      // 选中/未选中（线型）：选中实线，未选中虚线。
      // dashSize 远大于线长时整体显示为实线。
      const isSelected = cameraName === activeCameraName;
      if (isSelected) {
        frustumMaterial.dashSize = 10000;
        frustumMaterial.gapSize = 0;
      } else {
        frustumMaterial.dashSize = 0.15;
        frustumMaterial.gapSize = 0.12;
      }

      // 8 frustum corners: NDC (±1, ±1, ±1) → world
      const corner = new THREE.Vector3();
      const writeCorner = (sx: number, sy: number, sz: number, offset: number) => {
        corner.set(sx, sy, sz).unproject(helperCamera);
        frustumPositions[offset] = corner.x;
        frustumPositions[offset + 1] = corner.y;
        frustumPositions[offset + 2] = corner.z;
      };

      // near rectangle (z = -1): vertices 0..3, far rectangle (z = +1): vertices 4..7
      writeCorner(-1, -1, -1, 0);
      writeCorner(1, -1, -1, 3);
      writeCorner(1, 1, -1, 6);
      writeCorner(-1, 1, -1, 9);
      writeCorner(-1, -1, 1, 12);
      writeCorner(1, -1, 1, 15);
      writeCorner(1, 1, 1, 18);
      writeCorner(-1, 1, 1, 21);

      // 12 lines:
      // near edges (0-1, 1-2, 2-3, 3-0), far edges (4-5, 5-6, 6-7, 7-4),
      // connectors (0-4, 1-5, 2-6, 3-7)
      const lineIndices = [
        0, 1, 1, 2, 2, 3, 3, 0,
        4, 5, 5, 6, 6, 7, 7, 4,
        0, 4, 1, 5, 2, 6, 3, 7,
      ];
      const linePositions = new Float32Array(lineIndices.length * 3);
      for (let i = 0; i < lineIndices.length; i++) {
        const vertexIndex = lineIndices[i];
        linePositions[i * 3] = frustumPositions[vertexIndex * 3];
        linePositions[i * 3 + 1] = frustumPositions[vertexIndex * 3 + 1];
        linePositions[i * 3 + 2] = frustumPositions[vertexIndex * 3 + 2];
      }

      const positionAttribute = frustumLines.geometry.getAttribute('position') as THREE.BufferAttribute;
      positionAttribute.array.set(linePositions);
      positionAttribute.needsUpdate = true;

      // 虚线需要每帧重算线距离（顶点变了长度也变）
      frustumLines.computeLineDistances();
    }
  });

  return null;
}
