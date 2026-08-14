import { useRef, useEffect, useCallback } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { useAnimations } from '@react-three/drei';
import { useStore } from '../store';
import { DEFAULT_FRAME_ASPECT } from './CameraFrameOverlay';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import * as THREE from 'three';

interface SceneModelProperties {
  gltfData: GLTF;
  cameraName: string | null;
  lockedCamera: boolean;
}

export function SceneModel({ gltfData, cameraName, lockedCamera }: SceneModelProperties) {
  const { actions, mixer } = useAnimations(gltfData.animations, gltfData.scene);
  const threeCamera = useThree((state) => state.camera);
  const size = useThree((state) => state.size);
  const previousTimeReference = useRef(0);
  const animatedCameraNode = useRef<THREE.Object3D | null>(null);
  const baseYfovReference = useRef<number | null>(null);
  // Name → node lookup for applying shared character transforms
  const nodesByNameReference = useRef<Map<string, THREE.Object3D>>(new Map());

  // Build name → node lookup once per scene copy
  useEffect(() => {
    const nameMap = new Map<string, THREE.Object3D>();
    gltfData.scene.traverse((node) => {
      if (node.name) nameMap.set(node.name, node);
    });
    nodesByNameReference.current = nameMap;
  }, [gltfData]);

  // Find and cache the camera node once
  const findCameraNode = useCallback(() => {
    if (!cameraName) return null;
    let found: THREE.Object3D | null = null;
    gltfData.scene.traverse((node) => {
      if (node.name === cameraName && (node as THREE.PerspectiveCamera).isCamera) {
        found = node;
      }
    });
    return found;
  }, [gltfData, cameraName]);

  // Animation sync + camera tracking — runs every frame
  useFrame((_, delta) => {
    const store = useStore.getState();

    // Apply shared character transforms (set by Free View gizmo) so this
    // scene copy matches the other viewport.
    for (const [nodeName, transform] of Object.entries(store.characterTransforms)) {
      const node = nodesByNameReference.current.get(nodeName);
      if (node) {
        node.position.set(transform.position[0], transform.position[1], transform.position[2]);
        node.quaternion.set(
          transform.quaternion[0],
          transform.quaternion[1],
          transform.quaternion[2],
          transform.quaternion[3],
        );
      }
    }

    if (!mixer || !store.shot || store.durationSeconds === 0) return;

    // Advance animation
    if (store.isPlaying) {
      mixer.update(delta);
      if (mixer.time >= store.durationSeconds) {
        const restartTime = store.animationStartTime;
        mixer.setTime(restartTime);
        store.setCurrentTime(restartTime);
        store.setPlaying(false);
        return;
      }
      const currentMixerTime = mixer.time;
      if (Math.abs(currentMixerTime - previousTimeReference.current) > 0.05) {
        previousTimeReference.current = currentMixerTime;
        store.setCurrentTime(currentMixerTime);
      }
    } else {
      const storeTime = store.currentTime;
      if (Math.abs(mixer.time - storeTime) > 0.02) {
        mixer.setTime(storeTime);
        // Snap camera immediately after seeking
        if (lockedCamera && animatedCameraNode.current) {
          const worldPosition = new THREE.Vector3();
          const worldQuaternion = new THREE.Quaternion();
          animatedCameraNode.current.getWorldPosition(worldPosition);
          animatedCameraNode.current.getWorldQuaternion(worldQuaternion);
          threeCamera.position.copy(worldPosition);
          threeCamera.quaternion.copy(worldQuaternion);
        }
      }
    }

    // Track animated camera position every frame when locked AND playing
    if (lockedCamera && animatedCameraNode.current && store.isPlaying) {
      const worldPosition = new THREE.Vector3();
      const worldQuaternion = new THREE.Quaternion();
      animatedCameraNode.current.getWorldPosition(worldPosition);
      animatedCameraNode.current.getWorldQuaternion(worldQuaternion);

      threeCamera.position.copy(worldPosition);
      threeCamera.quaternion.copy(worldQuaternion);
    }
  });

  // Play all animations on mount, then force first frame pose
  useEffect(() => {
    if (actions && mixer) {
      for (const action of Object.values(actions)) {
        action.play();
        action.reset(); // Reset to start of clip
      }
      // Start at the animation's first keyframe (frame 1 pose),
      // NOT time 0 which is the T-pose bind state.
      const startTime = useStore.getState().animationStartTime;
      mixer.setTime(startTime);
      mixer.update(0);
    }
  }, [actions, mixer]);

  // Remove glTF scene lights entirely — Blender sun (日光) creates heavy
  // directional shadows that look bad in Web. The frontend provides
  // uniform skylight (hemisphereLight) instead, like Blender's
  // Material Preview mode.
  useEffect(() => {
    if (!gltfData?.scene) return;
    // Collect lights first, then remove — mutating the tree while
    // traversing can corrupt the iterator.
    const lightsToRemove: THREE.Light[] = [];
    gltfData.scene.traverse((node) => {
      if ((node as THREE.Light).isLight) {
        lightsToRemove.push(node as THREE.Light);
      }
    });
    for (const light of lightsToRemove) {
      light.parent?.remove(light);
    }
  }, [gltfData]);

  // Cache camera node + base yfov when cameraName changes
  useEffect(() => {
    animatedCameraNode.current = findCameraNode();

    if (lockedCamera && animatedCameraNode.current) {
      const perspectiveCamera = animatedCameraNode.current as THREE.PerspectiveCamera;
      if (perspectiveCamera.fov !== undefined) {
        baseYfovReference.current = perspectiveCamera.fov;
        applyCameraFit();
      }
    }
  }, [findCameraNode, lockedCamera, threeCamera]);

  // Zoom the locked camera out (scale FOV uniformly) so the full camera frame
  // (16:9) fits inside the canvas — keeps proportions, never distorts. When the
  // canvas is wider than 16:9 no zoom is needed (frame already fits).
  const applyCameraFit = () => {
    if (lockedCamera && animatedCameraNode.current && baseYfovReference.current !== null) {
      const perspectiveCamera = threeCamera as THREE.PerspectiveCamera;
      const canvasAspect = size.width / size.height;
      const frameAspect = useStore.getState().shot?.frame_aspect ?? DEFAULT_FRAME_ASPECT;
      const fitScale = Math.max(1, frameAspect / canvasAspect);
      const targetFov = baseYfovReference.current * fitScale;
      if (Math.abs(perspectiveCamera.fov - targetFov) > 0.01) {
        perspectiveCamera.fov = targetFov;
        perspectiveCamera.updateProjectionMatrix();
      }
    }
  };

  // Re-apply the fit on every frame (canvas resize changes the aspect ratio)
  useFrame(applyCameraFit);

  return <primitive object={gltfData.scene} />;
}
