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
  const previousIsPlayingReference = useRef(false);
  const animatedCameraNode = useRef<THREE.Object3D | null>(null);
  const baseYfovReference = useRef<number | null>(null);
  // Name → node lookup for applying shared character transforms
  const nodesByNameReference = useRef<Map<string, THREE.Object3D>>(new Map());

  // Build name → node lookup once per scene copy
  useEffect(() => {
    const nameMap = new Map<string, THREE.Object3D>();
    const cameraNodes: Array<{ name: string; type: string; pos: number[] }> = [];
    gltfData.scene.traverse((node) => {
      if (node.name) nameMap.set(node.name, node);
      if ((node as THREE.PerspectiveCamera).isCamera) {
        cameraNodes.push({
          name: node.name,
          type: node.type,
          pos: node.position.toArray().map((value) => Number(value.toFixed(2))),
        });
      }
    });
    nodesByNameReference.current = nameMap;
    window.__cameras = cameraNodes;
    console.log('[cameras]', JSON.stringify(cameraNodes));
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

    // 检测播放开始（isPlaying false→true）：重置所有 clip 的 paused。
    // LoopOnce + clampWhenFinished 在段结束后 paused=true；mixer.setTime（seek）
    // 只归零时间、不清 paused，paused 的 action 采样停在 0 → 输出段起点值恒定，
    // 看起来就是"位置只跳变、段内不插值"。
    const wasPlaying = previousIsPlayingReference.current;
    previousIsPlayingReference.current = store.isPlaying;
    if (store.isPlaying && !wasPlaying) {
      for (const action of Object.values(actions)) {
        if (action) action.paused = false;
      }
    }

    // Advance animation
    if (store.isPlaying) {
      mixer.update(delta);
      // DEBUG: 记录全时段相机位置 + 朝向（每 0.1s 一条），供用户打印诊断
      if (animatedCameraNode.current) {
        const debugPosition = new THREE.Vector3();
        const debugQuaternion = new THREE.Quaternion();
        animatedCameraNode.current.getWorldPosition(debugPosition);
        animatedCameraNode.current.getWorldQuaternion(debugQuaternion);
        const debugEuler = new THREE.Euler().setFromQuaternion(debugQuaternion);
        if (window.__camLog === undefined) window.__camLog = [];
        const lastSample = window.__camLog[window.__camLog.length - 1];
        if (!lastSample || mixer.time - lastSample.t >= 0.1) {
          const entry = {
            t: Number(mixer.time.toFixed(2)),
            pos: debugPosition.toArray().map((value) => Number(value.toFixed(2))),
            euler: [debugEuler.x, debugEuler.y, debugEuler.z].map(
              (value) => Number(((value * 180) / Math.PI).toFixed(1)),
            ),
          };
          window.__camLog.push(entry);
          console.log('[cam]', JSON.stringify(entry));
        }
      }
      if (mixer.time >= store.durationSeconds) {
        const restartTime = store.animationStartTime;
        // LoopOnce 结束后每个 clip 进入 paused（clampWhenFinished 保持末值）。
        // mixer.setTime 只归零时间，不清 paused —— 不重置的话下次播放
        // mixer.update 不会推进这些 clip，相机就停在原地不动。
        for (const action of Object.values(actions)) {
          if (action) action.reset();
        }
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
        // seek 前重置 paused，否则已 clamp 的 clip 采样停在 0（段起点）
        for (const action of Object.values(actions)) {
          if (action) action.paused = false;
        }
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

    // Segment weight scheduling: only the clip whose time window contains
    // the playhead drives the camera. Others get weight 0 so their clamped
    // tail values don't blend in and pollute the result. Runs every frame
    // (playback AND seek) so the active segment always matches mixer.time.
    const segments = store.shot?.segments ?? [];
    if (segments.length > 0) {
      // 按相机分组判断首/末段。parallel 模式下两相机时间轴重叠（如 seg_01 与
      // seg_04 都从 0 开始），不能用全局段列表的 index + 下一段 start_time 判断
      // 边界——那会让 start_time 相同的首段 weight 恒为 0。
      const cameraSegments = new Map<string, typeof segments>();
      for (const segment of segments) {
        const list = cameraSegments.get(segment.camera_name) ?? [];
        list.push(segment);
        cameraSegments.set(segment.camera_name, list);
      }

      for (const [name, action] of Object.entries(actions)) {
        if (!action) continue;
        const segment = segments.find((candidate) => candidate.segment_name === name);
        if (!segment) continue;

        const cameraList = cameraSegments.get(segment.camera_name) ?? [segment];
        const cameraStart = Math.min(...cameraList.map((item) => item.start_time));
        const cameraEnd = Math.max(...cameraList.map((item) => item.end_time));

        // 首/末段边界开放（按相机）：时间轴最左/最右时仍让该相机的首/末段
        // 保持 weight=1，采样其起点/终点值，避免 weight 全 0 时相机回落到
        // glTF 节点初始 pose。
        const isFirstSegment = segment.start_time === cameraStart;
        const isLastSegment = segment.end_time === cameraEnd;
        const lowerBound = isFirstSegment ? -Infinity : segment.start_time;
        const upperBound = isLastSegment ? Infinity : segment.end_time;
        const isActive = mixer.time >= lowerBound && mixer.time < upperBound;
        action.weight = isActive ? 1 : 0;
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

  // Play each segment clip on the global timeline. glTF animation inputs are
  // absolute time (matching the global mixer time), so each clip samples
  // correctly on its own. LoopOnce + clampWhenFinished holds the pose at the
  // segment boundary; per-frame weight scheduling (in useFrame) keeps only the
  // current segment's clip active so clamped tails don't blend in.
  useEffect(() => {
    if (actions && mixer) {
      window.__actions = actions;
      window.__mixer = mixer;
      const segments = useStore.getState().shot?.segments ?? [];
      for (const [name, action] of Object.entries(actions)) {
        if (!action) continue;
        const segment = segments.find((candidate) => candidate.segment_name === name);
        if (segment) {
          action.setLoop(THREE.LoopOnce, 1);
          action.clampWhenFinished = true;
        }
        action.play();
      }
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
