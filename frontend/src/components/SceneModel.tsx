import { useRef, useEffect, useCallback, useMemo } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { useStore } from '../store';
import { DEFAULT_FRAME_ASPECT } from './CameraFrameOverlay';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { ShotSegment } from '../types';
import * as THREE from 'three';

/** 根据相机位置和目标点计算朝向（lookAt），用于 follow 段（TRACK_TO 约束）。glTF 为 Y-up，默认 up=(0,1,0)。 */
function lookAtQuaternion(
  position: [number, number, number],
  target: [number, number, number],
): THREE.Quaternion {
  const matrix = new THREE.Matrix4().lookAt(
    new THREE.Vector3(position[0], position[1], position[2]),
    new THREE.Vector3(target[0], target[1], target[2]),
    new THREE.Vector3(0, 1, 0),
  );
  return new THREE.Quaternion().setFromRotationMatrix(matrix);
}

/** 编辑段重建：简单段（S）重建为「首尾 2 个 pose + 插值」；复杂段（C）只读，保持深拷贝完整关键帧。 */
function applySegmentToClip(
  clip: THREE.AnimationClip,
  segment: ShotSegment,
  instanceLabel: string,
): void {
  if (segment.segment_type === 'C') return;

  // 诊断：输出重建该段用的完整基础配置数据（带实例标识 + JSON 纯文本，便于直接复制）
  console.log(
    '[rebuild]',
    instanceLabel,
    segment.segment_name,
    JSON.stringify({
      camera: segment.camera_name,
      type: segment.segment_type,
      start_time: segment.start_time,
      end_time: segment.end_time,
      start_pose: {
        position: Array.from(segment.start_pose.position),
        rotation: Array.from(segment.start_pose.rotation),
      },
      end_pose: {
        position: Array.from(segment.end_pose.position),
        rotation: Array.from(segment.end_pose.rotation),
      },
      interpolation: segment.interpolation ?? { position: 'LINEAR', rotation: 'LINEAR' },
    }),
  );

  const positionInterpolation = segment.interpolation?.position ?? 'LINEAR';
  const rotationInterpolation = segment.interpolation?.rotation ?? 'LINEAR';
  const startTime = segment.start_time;
  const endTime = segment.end_time;

  const hasPosition = clip.tracks.some((track) => track.name.endsWith('.position'));
  const hasQuaternion = clip.tracks.some((track) => track.name.endsWith('.quaternion'));
  const newTracks: THREE.KeyframeTrack[] = [];

  if (hasPosition) {
    const track = new THREE.VectorKeyframeTrack(
      `${segment.camera_name}.position`,
      [startTime, endTime],
      [...segment.start_pose.position, ...segment.end_pose.position],
    );
    track.setInterpolation(
      positionInterpolation === 'CONSTANT' ? THREE.InterpolateDiscrete : THREE.InterpolateLinear,
    );
    newTracks.push(track);
  }

  if (hasQuaternion) {
    const orientationMode =
      segment.orientation_mode ?? (segment.constraint?.rotation?.length ? 'follow' : 'interpolate');
    let startQuat: THREE.Quaternion;
    let endQuat: THREE.Quaternion;
    if (orientationMode === 'follow' && segment.target_position) {
      // follow：朝向 = lookAt 该段自己的目标点（每段独立），由段 target_position 派生
      startQuat = lookAtQuaternion(segment.start_pose.position, segment.target_position);
      endQuat = lookAtQuaternion(segment.end_pose.position, segment.target_position);
    } else {
      startQuat = new THREE.Quaternion().setFromEuler(
        new THREE.Euler(
          segment.start_pose.rotation[0],
          segment.start_pose.rotation[1],
          segment.start_pose.rotation[2],
          'XYZ',
        ),
      );
      endQuat = new THREE.Quaternion().setFromEuler(
        new THREE.Euler(
          segment.end_pose.rotation[0],
          segment.end_pose.rotation[1],
          segment.end_pose.rotation[2],
          'XYZ',
        ),
      );
    }
    const track = new THREE.QuaternionKeyframeTrack(
      `${segment.camera_name}.quaternion`,
      [startTime, endTime],
      [
        startQuat.x,
        startQuat.y,
        startQuat.z,
        startQuat.w,
        endQuat.x,
        endQuat.y,
        endQuat.z,
        endQuat.w,
      ],
    );
    track.setInterpolation(
      rotationInterpolation === 'CONSTANT' ? THREE.InterpolateDiscrete : THREE.InterpolateLinear,
    );
    newTracks.push(track);
  }

  clip.tracks = newTracks;
}

/** 按播放头时间调度各段 action 的 weight（首/末段边界开放，按相机分组）。 */
function scheduleSegmentWeights(
  mixer: THREE.AnimationMixer,
  actions: Record<string, THREE.AnimationAction | null>,
  segments: ShotSegment[],
  cameraNodeNames: Set<string>,
): void {
  const disableCameraAction = (action: THREE.AnimationAction) => {
    const clip = action.getClip();
    const isCameraClip = clip.tracks.some((track) => cameraNodeNames.has(track.name.split('.')[0]));
    if (isCameraClip) {
      action.weight = 0;
      action.enabled = false;
    }
  };
  if (segments.length === 0) {
    for (const action of Object.values(actions)) {
      if (action) disableCameraAction(action);
    }
    return;
  }
  const cameraSegments = new Map<string, ShotSegment[]>();
  for (const segment of segments) {
    const list = cameraSegments.get(segment.camera_name) ?? [];
    list.push(segment);
    cameraSegments.set(segment.camera_name, list);
  }
  for (const [name, action] of Object.entries(actions)) {
    if (!action) continue;
    const segment = segments.find((candidate) => candidate.segment_name === name);
    if (!segment) {
      // 段已删除：只禁用残留的「相机段」action，角色骨骼动画保持 active
      disableCameraAction(action);
      continue;
    }
    const cameraList = cameraSegments.get(segment.camera_name) ?? [segment];
    const cameraStart = Math.min(...cameraList.map((item) => item.start_time));
    const cameraEnd = Math.max(...cameraList.map((item) => item.end_time));
    const isFirstSegment = segment.start_time === cameraStart;
    const isLastSegment = segment.end_time === cameraEnd;
    const lowerBound = isFirstSegment ? -Infinity : segment.start_time;
    const upperBound = isLastSegment ? Infinity : segment.end_time;
    const isActive = mixer.time >= lowerBound && mixer.time < upperBound;
    action.weight = isActive ? 1 : 0;
    action.enabled = true;
  }
}

interface SceneModelProperties {
  gltfData: GLTF;
  cameraName: string | null;
  lockedCamera: boolean;
}

export function SceneModel({ gltfData, cameraName, lockedCamera }: SceneModelProperties) {
  const editMode = useStore((state) => state.editMode);
  const editingSegments = useStore((state) => state.editingSegments);
  // 所有相机节点名（用于区分「相机段 clip」与「角色骨骼动画 clip」），由 configureMixerActions 收集
  const cameraNodeNamesRef = useRef<Set<string>>(new Set());

  // 编辑态：深拷贝 clips 作为编辑副本。这和「切换 blend 换一份 clips」是同一件事——
  // 只是喂给 useAnimations 的 clips 不同，mixer / 每帧驱动 / 配置全部复用，不再新建 mixer。
  // 编辑段的插值设置 apply 到对应 clip 的 track 上（未编辑段在 editingSegments 里仍是原始值，apply 后不变）。
  const editClips = useMemo(() => {
    if (!editMode) return null;
    const clips = gltfData.animations.map((clip) => clip.clone());
    // 诊断：打印原始 clips 的 seg_01 position track 首尾值，确认编辑是否污染了原始数据
    const originalSeg01 = gltfData.animations.find((candidate) => candidate.name === 'seg_01');
    if (originalSeg01) {
      const positionTrack = originalSeg01.tracks.find((track) => track.name.endsWith('.position'));
      if (positionTrack) {
        console.log(
          '[original]',
          lockedCamera ? 'CameraView' : 'FreeView',
          'seg_01 position first/last =',
          Array.from(positionTrack.values.slice(0, 3)),
          Array.from(positionTrack.values.slice(-3)),
        );
      }
    }
    if (editingSegments) {
      for (const segment of editingSegments) {
        let clip = clips.find((candidate) => candidate.name === segment.segment_name);
        if (!clip) {
          // 新段：glTF 没有对应 clip，新建占位 clip（position + quaternion track），
          // 交给 applySegmentToClip 重建为首尾 pose（静止段首尾相同）。
          clip = new THREE.AnimationClip(
            segment.segment_name,
            segment.end_time,
            [
              new THREE.VectorKeyframeTrack(
                `${segment.camera_name}.position`,
                [segment.start_time, segment.end_time],
                [0, 0, 0, 0, 0, 0],
              ),
              new THREE.QuaternionKeyframeTrack(
                `${segment.camera_name}.quaternion`,
                [segment.start_time, segment.end_time],
                [0, 0, 0, 1, 0, 0, 0, 1],
              ),
            ],
          );
          clips.push(clip);
        }
        applySegmentToClip(clip, segment, lockedCamera ? 'CameraView' : 'FreeView');
      }
    }
    return clips;
  }, [editMode, gltfData.animations, editingSegments]);

  // 完全隔离：查看态和编辑态各用独立的 mixer + actions，互不污染。
  // 两个 mixer 都绑定同一个 scene，但只在各自模式（editMode 切换）下激活。
  const viewMixerReference = useRef<THREE.AnimationMixer | null>(null);
  if (viewMixerReference.current === null) {
    viewMixerReference.current = new THREE.AnimationMixer(gltfData.scene);
  }
  const viewMixer = viewMixerReference.current;
  const viewActionsReference = useRef<Record<string, THREE.AnimationAction>>({});

  const editMixerReference = useRef<THREE.AnimationMixer | null>(null);
  if (editMixerReference.current === null) {
    editMixerReference.current = new THREE.AnimationMixer(gltfData.scene);
  }
  const editMixer = editMixerReference.current;
  const editActionsReference = useRef<Record<string, THREE.AnimationAction>>({});

  // 当前活跃的 mixer + actions（根据 editMode 切换）
  const mixer = editMode ? editMixer : viewMixer;
  const actionsReference = editMode ? editActionsReference : viewActionsReference;
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
    const segments =
      store.editMode && store.editingSegments
        ? store.editingSegments
        : (store.shot?.segments ?? []);
    // 有效时长：编辑态用 editingSegments 最大 end_time（新增段后总时长要跟着变），
    // 查看态用后端导出的 durationSeconds。
    const effectiveDuration =
      store.editMode && store.editingSegments && store.editingSegments.length > 0
        ? Math.max(...store.editingSegments.map((segment) => segment.end_time))
        : store.durationSeconds;

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

    if (!mixer || !store.shot || effectiveDuration === 0) return;

    // 检测播放开始（isPlaying false→true）：重置所有 clip 的 paused。
    // LoopOnce + clampWhenFinished 在段结束后 paused=true；mixer.setTime（seek）
    // 只归零时间、不清 paused，paused 的 action 采样停在 0 → 输出段起点值恒定，
    // 看起来就是"位置只跳变、段内不插值"。
    const wasPlaying = previousIsPlayingReference.current;
    previousIsPlayingReference.current = store.isPlaying;
    if (store.isPlaying && !wasPlaying) {
      for (const action of Object.values(actionsReference.current)) {
        if (action) action.paused = false;
      }
    }

    // Advance animation
    if (store.isPlaying) {
      mixer.update(delta);
      // 诊断：编辑态播放时确认 action 状态（weight/enabled/time）
      if (store.editMode && lockedCamera) {
        if ((window as any).__editActionLog === undefined) (window as any).__editActionLog = 0;
        const now = Math.floor(mixer.time * 2);
        if (now !== (window as any).__editActionLog) {
          (window as any).__editActionLog = now;
          for (const [name, action] of Object.entries(actionsReference.current)) {
            if (action) {
              console.log(
                '[editAction]',
                name,
                'weight=',
                action.weight,
                'enabled=',
                action.enabled,
                'time=',
                Number(action.time.toFixed(2)),
              );
            }
          }
        }
      }
      // 诊断：编辑态播放时确认 mixer 是否推进 + 相机是否被驱动
      if (store.editMode && lockedCamera && animatedCameraNode.current) {
        const diagnosticPosition = new THREE.Vector3();
        animatedCameraNode.current.getWorldPosition(diagnosticPosition);
        if ((window as any).__editPlayLog === undefined) (window as any).__editPlayLog = [];
        const lastEntry = (window as any).__editPlayLog[(window as any).__editPlayLog.length - 1];
        if (!lastEntry || mixer.time - lastEntry.t >= 0.5) {
          const entry = {
            t: Number(mixer.time.toFixed(2)),
            pos: diagnosticPosition.toArray().map((value) => Number(value.toFixed(2))),
          };
          (window as any).__editPlayLog.push(entry);
          console.log('[editPlay]', JSON.stringify(entry));
        }
      }
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
      if (mixer.time >= effectiveDuration) {
        const restartTime = store.animationStartTime;
        // LoopOnce 结束后每个 clip 进入 paused（clampWhenFinished 保持末值）。
        // mixer.setTime 只归零时间，不清 paused —— 不重置的话下次播放
        // mixer.update 不会推进这些 clip，相机就停在原地不动。
        for (const action of Object.values(actionsReference.current)) {
          if (action) action.reset();
        }
        mixer.setTime(restartTime);
        // setTime 采样用的还是「上一帧」的 weight（最后一段=1），会导致回第一帧时
        // 采样到末段首值。这里按 restartTime 重新调度 weight 再 update(0) 重采样。
        scheduleSegmentWeights(mixer, actionsReference.current, segments, cameraNodeNamesRef.current);
        mixer.update(0);
        // 同步 threeCamera（画面）到第一帧的位置——相机跟踪只在播放态执行，
        // 这里 setPlaying(false) 之前手动同步一次，否则画面停在最后一帧。
        if (lockedCamera && animatedCameraNode.current) {
          const worldPosition = new THREE.Vector3();
          const worldQuaternion = new THREE.Quaternion();
          animatedCameraNode.current.getWorldPosition(worldPosition);
          animatedCameraNode.current.getWorldQuaternion(worldQuaternion);
          threeCamera.position.copy(worldPosition);
          threeCamera.quaternion.copy(worldQuaternion);
        }
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
        for (const action of Object.values(actionsReference.current)) {
          if (action) action.paused = false;
        }
        mixer.setTime(storeTime);
        // 重采样：setTime 只改 mixer 时间、不更新 action 采样；
        // 需按新 time 重新调度 weight 再 update(0)，画面才真正跳到新 pose。
        scheduleSegmentWeights(mixer, actionsReference.current, segments, cameraNodeNamesRef.current);
        mixer.update(0);
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
    // the playhead drives the camera. Runs every frame (playback AND seek)
    // so the active segment always matches mixer.time.
    scheduleSegmentWeights(mixer, actionsReference.current, segments, cameraNodeNamesRef.current);

    // Track animated camera position every frame when locked AND playing
    if (lockedCamera && animatedCameraNode.current && store.isPlaying) {
      const worldPosition = new THREE.Vector3();
      const worldQuaternion = new THREE.Quaternion();
      animatedCameraNode.current.getWorldPosition(worldPosition);
      animatedCameraNode.current.getWorldQuaternion(worldQuaternion);

      threeCamera.position.copy(worldPosition);
      threeCamera.quaternion.copy(worldQuaternion);
    }

    // 编辑态相机位置/朝向由「编辑 clip 喂 mixer」驱动（上方 weight scheduling + mixer 采样），
    // 不再手动摆相机——查看态/编辑态共用同一套 mixer 播放器。
  });

  // 给某个 mixer 配置一组 clips 的 action：清空旧 action + 重新 clipAction + 配置 + weight 调度 + 采样。
  const configureMixerActions = useCallback(
    (
      targetMixer: THREE.AnimationMixer,
      targetClips: THREE.AnimationClip[],
      targetActionsReference: { current: Record<string, THREE.AnimationAction> },
    ) => {
      if (!targetMixer || !gltfData.scene) return;
      targetMixer.stopAllAction();
      const existingActions = [
        ...(targetMixer as unknown as { _actions: THREE.AnimationAction[] })._actions,
      ];
      for (const action of existingActions) {
        targetMixer.uncacheAction(action.getClip(), gltfData.scene);
      }
      // 收集所有相机节点名（存 ref，供 useFrame 每帧调度复用），区分「相机段 clip」和「角色骨骼动画 clip」
      cameraNodeNamesRef.current = new Set<string>();
      gltfData.scene.traverse((node) => {
        if ((node as THREE.PerspectiveCamera).isCamera && node.name) cameraNodeNamesRef.current.add(node.name);
      });
      const cameraNodeNames = cameraNodeNamesRef.current;
      const nextActions: Record<string, THREE.AnimationAction> = {};
      const cameraActions: Record<string, THREE.AnimationAction> = {};
      for (const clip of targetClips) {
        const action = targetMixer.clipAction(clip, gltfData.scene);
        action.setLoop(THREE.LoopOnce, 1);
        action.clampWhenFinished = true;
        action.play();
        nextActions[clip.name] = action;
        // 只有 track 节点是相机的 clip 才参与段调度；角色骨骼动画始终 active
        const isCameraClip = clip.tracks.some((track) => cameraNodeNames.has(track.name.split('.')[0]));
        if (isCameraClip) cameraActions[clip.name] = action;
      }
      targetActionsReference.current = nextActions;
      window.__actions = nextActions;
      window.__mixer = targetMixer;
      const storeState = useStore.getState();
      const segments =
        storeState.editMode && storeState.editingSegments
          ? storeState.editingSegments
          : storeState.shot?.segments ?? [];
      scheduleSegmentWeights(targetMixer, cameraActions, segments, cameraNodeNames);
      const currentTime = useStore.getState().currentTime;
      targetMixer.setTime(currentTime);
      targetMixer.update(0);
      // 采样后同步 threeCamera（暂停态也要同步，否则切换聊天/编辑后画面停在旧位置）
      if (lockedCamera && cameraName) {
        let cameraNode: THREE.Object3D | null = null;
        gltfData.scene.traverse((node) => {
          if (node.name === cameraName && (node as THREE.PerspectiveCamera).isCamera) cameraNode = node;
        });
        if (cameraNode) {
          const worldPosition = new THREE.Vector3();
          const worldQuaternion = new THREE.Quaternion();
          cameraNode.getWorldPosition(worldPosition);
          cameraNode.getWorldQuaternion(worldQuaternion);
          threeCamera.position.copy(worldPosition);
          threeCamera.quaternion.copy(worldQuaternion);
        }
      }
      // 诊断：打印 mixer 里当前所有 action 的 clip name + uuid，确认退出编辑态后是否切回原始 clips
      console.log(
        '[mixer-actions]',
        Object.values(nextActions).map((action) => {
          const actionClip = action.getClip();
          return `${actionClip.name}#${actionClip.uuid.slice(0, 8)}`;
        }),
      );
      // 诊断：打印 threeCamera（画面实际渲染相机）的位置，对比 [rebuild] 的 pose（数据层）
      console.log(
        '[sample]',
        JSON.stringify({
          camera: cameraName,
          t: currentTime,
          threeCamera: threeCamera.position.toArray().map((value) => Number(value.toFixed(3))),
        }),
      );
      // 诊断：打印 seg_01 的 action 状态，确认 mixer 是否激活/驱动
      const seg01Action = nextActions['seg_01'];
      if (seg01Action) {
        console.log(
          '[action-state]',
          'seg_01',
          'weight=',
          seg01Action.weight,
          'enabled=',
          seg01Action.enabled,
          'paused=',
          seg01Action.paused,
        );
      }
    },
    [gltfData.scene, cameraName, threeCamera, lockedCamera],
  );

  // 完全隔离的切换：editMode 或 clips 变化时，停止旧 mixer 的 action、配置新 mixer 的 action。
  useEffect(() => {
    if (!gltfData.scene) return;
    if (editMode) {
      // 编辑态：停止 viewMixer，配置 editMixer（深拷贝 clips）
      viewMixer.stopAllAction();
      if (editClips) {
        configureMixerActions(editMixer, editClips, editActionsReference);
      }
    } else {
      // 查看态：停止 editMixer，配置 viewMixer（原始 clips）
      editMixer.stopAllAction();
      configureMixerActions(viewMixer, gltfData.animations, viewActionsReference);
    }
  }, [
    editMode,
    editClips,
    gltfData.animations,
    gltfData.scene,
    viewMixer,
    editMixer,
    configureMixerActions,
  ]);

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
