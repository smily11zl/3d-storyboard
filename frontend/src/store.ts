import * as THREE from 'three';
import { create } from 'zustand';
import type { SessionSummary, ShotMetadata, ShotSegment, BlendVersion, Pose, PositionKeyframe, RotationKeyframe } from './types';

interface StoreState {
  shot: ShotMetadata | null;
  isLoading: boolean;
  errorMessage: string | null;
  activeCameraName: string | null;
  isPlaying: boolean;
  currentTime: number;
  durationSeconds: number;
  framesPerSecond: number;
  animationStartTime: number;

  /** V3 session state — which historical chat session is active. */
  currentSessionId: string | null;
  sessionList: SessionSummary[];
  newChatToken: number;
  setCurrentSessionId: (id: string | null) => void;
  setSessionList: (list: SessionSummary[]) => void;
  requestNewChat: () => void;

  sidebarCollapsed: boolean;
  toggleSidebar: () => void;

  /** V5 edit-mode state — entered via the top-bar Edit button. */
  editMode: boolean;
  /** Whether the current edit has unsaved changes (drives the Save button). */
  dirty: boolean;
  setEditMode: (editing: boolean) => void;
  setDirty: (dirty: boolean) => void;

  /** The currently selected segment in edit mode (by camera + segment name). */
  selectedSegment: { camera_name: string; segment_name: string } | null;
  setSelectedSegment: (segment: { camera_name: string; segment_name: string } | null) => void;

  /** 编辑态的段副本（进入编辑时深拷贝 shot.segments，编辑直接改副本，保存写回，放弃丢弃）。 */
  editingSegments: ShotSegment[] | null;
  /** 从 glTF clips 预计算的每段 pose（glTF Y-up 坐标），编辑态用它做编辑载体。 */
  gltfSegmentPoses: Record<string, Record<string, { start_pose: Pose; end_pose: Pose }>>;
  setGltfSegmentPoses: (
    poses: Record<string, Record<string, { start_pose: Pose; end_pose: Pose }>>,
  ) => void;
  /** 每段 follow 目标点位置（glTF Y-up），从 aim_target 位置动画按段提取；编辑态塞进段 target_position。 */
  segmentTargets: Record<string, Record<string, [number, number, number]>>;
  /** glTF 完整动画 clips（播放层数据引用；保存 C 段时现读完整采样点）。 */
  gltfAnimations: THREE.AnimationClip[] | null;
  setGltfAnimations: (animations: THREE.AnimationClip[]) => void;
  saveEdit: () => Promise<void>;

  /** blend 版本列表（当前 shot 目录下的 .blend）。 */
  blendVersions: BlendVersion[];
  loadBlendVersions: (exportHash: string) => Promise<void>;
  switchBlend: (blendHash: string) => Promise<void>;

  setSegmentPose: (
    key: string,
    which: 'start' | 'end',
    position: [number, number, number],
    rotation: [number, number, number],
  ) => void;
  setSegmentTarget: (key: string, targetPosition: [number, number, number]) => void;
  setOrientationMode: (key: string, mode: 'interpolate' | 'follow') => void;
  setInterpolation: (key: string, channel: 'position' | 'rotation', value: string) => void;

  /** Add a segment at the end of a camera track (default still 3s). */
  addSegment: (cameraName: string) => void;
  /** Remove a segment (leaves a gap — no reflow). */
  deleteSegment: (cameraName: string, segmentName: string) => void;
  /** Change a segment's end time (duration). */
  setSegmentDuration: (cameraName: string, segmentName: string, endTime: number) => void;

  /** glTF node positions by name (for resolving TRACK_TO target positions). */
  targetNodePositions: Record<string, [number, number, number]>;
  setTargetNodePositions: (positions: Record<string, [number, number, number]>) => void;

  /** Character (armature root) transforms set by the Free View gizmo.
   *  Keyed by node name; both viewports apply them every frame so the
   *  Camera View reflects character moves made in the Free View. */
  characterTransforms: Record<
    string,
    { position: [number, number, number]; quaternion: [number, number, number, number] }
  >;
  setCharacterTransform: (
    nodeName: string,
    position: [number, number, number],
    quaternion: [number, number, number, number],
  ) => void;

  uploadFile: (file: File, force: boolean = false) => Promise<void>;
  clearError: () => void;
  setActiveCamera: (cameraName: string) => void;
  setPlaying: (playing: boolean) => void;
  setCurrentTime: (time: number) => void;
  reset: () => void;
}

function buildEditingSegments(
  segments: ShotSegment[],
  gltfSegmentPoses: Record<string, Record<string, { start_pose: Pose; end_pose: Pose }>>,
  segmentTargets: Record<string, Record<string, [number, number, number]>>,
  targetNodePositions: Record<string, [number, number, number]>,
): ShotSegment[] {
  return segments.map((segment) => {
    const pose = gltfSegmentPoses[segment.camera_name]?.[segment.segment_name];
    // 每段 target：优先从 aim_target 动画提取的 segmentTargets；无动画（静态 target）回退到静态快照
    const targetName = segment.constraint?.rotation?.[0]?.target ?? null;
    const targetPosition =
      segmentTargets[segment.camera_name]?.[segment.segment_name] ??
      (targetName ? targetNodePositions[targetName] : undefined);
    return {
      ...segment,
      orientation_mode:
        segment.orientation_mode ??
        (segment.constraint?.rotation?.length ? 'follow' : 'interpolate'),
      start_pose: pose?.start_pose ?? segment.start_pose,
      end_pose: pose?.end_pose ?? segment.end_pose,
      ...(targetPosition ? { target_position: targetPosition } : {}),
    };
  });
}

function extractComplexSegmentKeyframes(
  animations: THREE.AnimationClip[] | null,
  segmentName: string,
): { position_keyframes: PositionKeyframe[]; rotation_keyframes: RotationKeyframe[] } | null {
  if (!animations) return null;
  const clip = animations.find((animation) => animation.name === segmentName);
  if (!clip) return null;

  const positionTrack = clip.tracks.find((track) => track.name.endsWith('.position'));
  const quaternionTrack = clip.tracks.find((track) => track.name.endsWith('.quaternion'));

  const position_keyframes: PositionKeyframe[] = [];
  if (positionTrack) {
    for (let index = 0; index < positionTrack.times.length; index++) {
      position_keyframes.push({
        time: positionTrack.times[index],
        position: [
          positionTrack.values[index * 3],
          positionTrack.values[index * 3 + 1],
          positionTrack.values[index * 3 + 2],
        ],
      });
    }
  }

  const rotation_keyframes: RotationKeyframe[] = [];
  if (quaternionTrack) {
    for (let index = 0; index < quaternionTrack.times.length; index++) {
      const quaternion = new THREE.Quaternion(
        quaternionTrack.values[index * 4],
        quaternionTrack.values[index * 4 + 1],
        quaternionTrack.values[index * 4 + 2],
        quaternionTrack.values[index * 4 + 3],
      );
      const euler = new THREE.Euler().setFromQuaternion(quaternion);
      rotation_keyframes.push({
        time: quaternionTrack.times[index],
        rotation: [euler.x, euler.y, euler.z],
      });
    }
  }

  return { position_keyframes, rotation_keyframes };
}

export const useStore = create<StoreState>((set, get) => ({
  shot: null,
  isLoading: false,
  errorMessage: null,
  activeCameraName: null,
  isPlaying: false,
  currentTime: 0,
  durationSeconds: 0,
  framesPerSecond: 24,
  animationStartTime: 0,
  currentSessionId: null,
  sessionList: [],
  newChatToken: 0,
  sidebarCollapsed: false,
  editMode: false,
  dirty: false,
  selectedSegment: null,
  editingSegments: null,
  gltfSegmentPoses: {},
  segmentTargets: {},
  gltfAnimations: null,
  blendVersions: [],
  targetNodePositions: {},
  characterTransforms: {},

  uploadFile: async (file: File, force: boolean = false) => {
    set({ isLoading: true, errorMessage: null });

    const formData = new FormData();
    formData.append('file', file);

    const queryString = force ? '?force=true' : '';

    try {
      const response = await fetch(`/api/shots${queryString}`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Upload failed (${response.status})`);
      }

      const metadata: ShotMetadata = await response.json();
      set({
        shot: metadata,
        isLoading: false,
        errorMessage: null,
        activeCameraName: metadata.cameras.length > 0 ? metadata.cameras[0].camera_name : null,
        durationSeconds: metadata.duration_seconds,
        framesPerSecond: metadata.frames_per_second,
        currentTime: 0,
        isPlaying: false,
        blendVersions: [],
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      set({ isLoading: false, errorMessage: message });
    }
  },

  clearError: () => set({ errorMessage: null }),
  setCurrentSessionId: (id) => set({ currentSessionId: id }),
  setSessionList: (list) => set({ sessionList: list }),
  requestNewChat: () =>
    set((state) => ({
      newChatToken: state.newChatToken + 1,
      currentSessionId: null,
      shot: null,
      blendVersions: [],
      gltfSegmentPoses: {},
      gltfAnimations: null,
      targetNodePositions: {},
      activeCameraName: null,
    })),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setEditMode: (editing) =>
    set((state) => ({
      editMode: editing,
      dirty: false,
      selectedSegment: null,
      editingSegments: editing
        ? buildEditingSegments(
            state.shot?.segments ?? [],
            state.gltfSegmentPoses,
            state.segmentTargets,
            state.targetNodePositions,
          )
        : null,
    })),
  setGltfSegmentPoses: (poses) => set({ gltfSegmentPoses: poses }),
  setGltfAnimations: (animations) => set({ gltfAnimations: animations }),
  setDirty: (dirty) => set({ dirty: dirty }),
  saveEdit: async () => {
    const state = get();
    const shot = state.shot;
    if (!shot || !state.editingSegments) return;
    // C 段只读：保存时从播放层（gltfAnimations）现读完整采样点，逐帧复刻。
    const segments = state.editingSegments.map((segment) => {
      if (segment.segment_type !== 'C') return segment;
      const keyframes = extractComplexSegmentKeyframes(
        state.gltfAnimations,
        segment.segment_name,
      );
      return keyframes ? { ...segment, ...keyframes } : segment;
    });
    const response = await fetch(`/api/shots/${shot.export_hash}/edit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        // target 位置已随每段 target_position 走，不再单独传全局 target_positions
        segments,
      }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => null);
      set({ errorMessage: error?.detail ?? 'Edit save failed' });
      return;
    }
    const newMetadata = await response.json();
    set({
      shot: newMetadata,
      dirty: false,
      editMode: false,
      selectedSegment: null,
      editingSegments: null,
      blendVersions: [],
      durationSeconds: newMetadata.duration_seconds,
      framesPerSecond: newMetadata.frames_per_second,
    });
  },
  loadBlendVersions: async (exportHash) => {
    const response = await fetch(`/api/shots/${exportHash}/blends`);
    if (!response.ok) {
      set({ blendVersions: [] });
      return;
    }
    const data = await response.json();
    set({ blendVersions: data.blends ?? [] });
  },
  switchBlend: async (blendHash) => {
    const response = await fetch(`/api/shots/${blendHash}`);
    if (!response.ok) {
      const error = await response.json().catch(() => null);
      set({ errorMessage: error?.detail ?? 'Blend load failed' });
      return;
    }
    const metadata = await response.json();
    set({
      shot: metadata,
      activeCameraName: metadata.cameras.length > 0 ? metadata.cameras[0].camera_name : null,
      durationSeconds: metadata.duration_seconds,
      framesPerSecond: metadata.frames_per_second,
    });
  },
  setSelectedSegment: (segment) => set({ selectedSegment: segment }),
  setSegmentPose: (key, which, position, rotation) =>
    set((state) => {
      if (!state.editingSegments) return {};
      const [cameraName, segmentName] = key.split(':');
      return {
        dirty: true,
        editingSegments: state.editingSegments.map((segment) =>
          segment.camera_name === cameraName && segment.segment_name === segmentName
            ? {
                ...segment,
                ...(which === 'start'
                  ? { start_pose: { position, rotation } }
                  : { end_pose: { position, rotation } }),
              }
            : segment,
        ),
      };
    }),
  setSegmentTarget: (key, targetPosition) =>
    set((state) => {
      if (!state.editingSegments) return {};
      const [cameraName, segmentName] = key.split(':');
      // 只改这一段的 target 位置（每段独立），不动其他段、不动全局 targetNodePositions
      return {
        dirty: true,
        editingSegments: state.editingSegments.map((segment) =>
          segment.camera_name === cameraName && segment.segment_name === segmentName
            ? { ...segment, target_position: targetPosition }
            : segment,
        ),
      };
    }),
  setOrientationMode: (key, mode) =>
    set((state) => {
      if (!state.editingSegments) return {};
      const [cameraName, segmentName] = key.split(':');
      return {
        dirty: true,
        editingSegments: state.editingSegments.map((segment) =>
          segment.camera_name === cameraName && segment.segment_name === segmentName
            ? { ...segment, orientation_mode: mode }
            : segment,
        ),
      };
    }),
  setInterpolation: (key, channel, value) =>
    set((state) => {
      if (!state.editingSegments) return {};
      const [cameraName, segmentName] = key.split(':');
      return {
        dirty: true,
        editingSegments: state.editingSegments.map((segment) =>
          segment.camera_name === cameraName && segment.segment_name === segmentName
            ? {
                ...segment,
                interpolation: {
                  position: segment.interpolation?.position ?? 'LINEAR',
                  rotation: segment.interpolation?.rotation ?? 'LINEAR',
                  [channel]: value,
                },
              }
            : segment,
        ),
      };
    }),
  setTargetNodePositions: (positions) => set({ targetNodePositions: positions }),
  addSegment: (cameraName) =>
    set((state) => {
      const segments = state.editingSegments;
      if (!segments) return {};
      const cameraSegments = segments.filter((segment) => segment.camera_name === cameraName);
      const lastEnd =
        cameraSegments.length > 0 ? Math.max(...cameraSegments.map((s) => s.end_time)) : 0;
      const lastSegment =
        cameraSegments.length > 0
          ? cameraSegments.reduce((a, b) => (a.end_time >= b.end_time ? a : b))
          : null;
      const endPose = lastSegment?.end_pose ?? { position: [0, 0, 0], rotation: [0, 0, 0] };
      const segmentName = `${cameraName}_seg_${cameraSegments.length + 1}`;
      const newSegment: ShotSegment = {
        camera_name: cameraName,
        segment_name: segmentName,
        start_time: lastEnd,
        end_time: lastEnd + 3,
        start_pose: { position: [...endPose.position], rotation: [...endPose.rotation] },
        end_pose: { position: [...endPose.position], rotation: [...endPose.rotation] },
        segment_type: 'S',
        constraint: lastSegment?.constraint,
        orientation_mode: lastSegment?.orientation_mode,
        // 继承上一段的 target 位置（follow 段），否则新段是 follow 但无 target，朝向退化成 identity（rotation 0）
        target_position: lastSegment?.target_position ? [...lastSegment.target_position] : undefined,
      };
      return {
        dirty: true,
        editingSegments: [...segments, newSegment],
      };
    }),
  deleteSegment: (cameraName, segmentName) =>
    set((state) => {
      if (!state.editingSegments) return {};
      return {
        dirty: true,
        selectedSegment:
          state.selectedSegment?.camera_name === cameraName &&
          state.selectedSegment?.segment_name === segmentName
            ? null
            : state.selectedSegment,
        editingSegments: state.editingSegments.filter(
          (segment) =>
            !(segment.camera_name === cameraName && segment.segment_name === segmentName),
        ),
      };
    }),
  setSegmentDuration: (cameraName, segmentName, endTime) =>
    set((state) => {
      if (!state.editingSegments) return {};
      return {
        dirty: true,
        editingSegments: state.editingSegments.map((segment) =>
          segment.camera_name === cameraName && segment.segment_name === segmentName
            ? { ...segment, end_time: endTime }
            : segment,
        ),
      };
    }),
  setActiveCamera: (cameraName) => set({ activeCameraName: cameraName }),
  setPlaying: (playing) =>
    set((state) => {
      // Restart from beginning if at/after the end
      if (playing && state.currentTime >= state.durationSeconds && state.durationSeconds > 0) {
        return { isPlaying: true, currentTime: state.animationStartTime };
      }
      return { isPlaying: playing };
    }),
  setCurrentTime: (time) => set({ currentTime: time }),
  setCharacterTransform: (nodeName, position, quaternion) =>
    set((state) => ({
      characterTransforms: {
        ...state.characterTransforms,
        [nodeName]: { position, quaternion },
      },
    })),
  reset: () =>
    set({
      shot: null,
      isLoading: false,
      errorMessage: null,
      activeCameraName: null,
      isPlaying: false,
      currentTime: 0,
      editMode: false,
      dirty: false,
      selectedSegment: null,
      editingSegments: null,
      gltfSegmentPoses: {},
      blendVersions: [],
      targetNodePositions: {},
      characterTransforms: {},
    }),
}));

/** 判断某相机在当前时间点是否「生效」：
 *  - 该相机有段：当前时间落在其某段 [start_time, end_time) 内 → 生效
 *  - 该相机无段（纯静态零动画）：整段兜底，视为整个时间轴生效
 */
export function isCameraActive(
  segments: ShotSegment[],
  cameraName: string | null,
  currentTime: number,
): boolean {
  if (!cameraName) return false;
  const cameraSegments = segments.filter(
    (segment) => segment.camera_name === cameraName,
  );
  if (cameraSegments.length > 0) {
    return cameraSegments.some(
      (segment) =>
        currentTime >= segment.start_time &&
        currentTime < segment.end_time,
    );
  }
  return true;
}
