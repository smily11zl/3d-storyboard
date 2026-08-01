import { useRef, useEffect, useCallback } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { useAnimations } from '@react-three/drei';
import { useStore } from '../store';
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
  const previousTimeReference = useRef(0);
  const animatedCameraNode = useRef<THREE.Object3D | null>(null);

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

  // Cache camera node + initial FOV when cameraName changes
  useEffect(() => {
    animatedCameraNode.current = findCameraNode();

    if (lockedCamera && animatedCameraNode.current) {
      const perspectiveCamera = animatedCameraNode.current as THREE.PerspectiveCamera;
      if (perspectiveCamera.fov !== undefined) {
        (threeCamera as THREE.PerspectiveCamera).fov = perspectiveCamera.fov;
        threeCamera.updateProjectionMatrix();
      }
    }
  }, [findCameraNode, lockedCamera, threeCamera]);

  return <primitive object={gltfData.scene} />;
}
