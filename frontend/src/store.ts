import * as THREE from 'three';
import { create } from 'zustand';
import type { SessionSummary, ShotMetadata, ShotSegment, BlendVersion, Pose, PositionKeyframe, RotationKeyframe, CameraInfo } from './types';
import { clampSegmentTimes } from './lib/segmentTiming';
import {
  exportBlendToDirectory,
  startExportMp4,
  fetchExportStatus,
} from './lib/exportApi';
import { writeFilesToDirectory } from './lib/exportFiles';

export interface ExportProgress {
  taskId: string;
  status: 'rendering' | 'composing' | 'done' | 'error' | 'cancelled';
  completedFiles: number;
  totalFiles: number;
  currentFile: string | null;
  currentFrame: number;
  currentTotalFrames: number;
  error: string | null;
}

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
  /** 编辑态相机列表（含增删的相机轴）；null 表示未进入编辑态，回退 shot.cameras。 */
  editingCameras: CameraInfo[] | null;
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

  /** V7 导出：导出当前 shot 为 MP4（给定分辨率）/ 复制 blend 到用户所选目录。 */
  exportMp4: (resolution: string) => Promise<void>;
  exportBlend: () => Promise<void>;
  /** V7 异步导出的进度状态（进度条用）。 */
  exportProgress: ExportProgress | null;
  /** 导出相关弹窗提示（自定义 Modal 显示）。 */
  exportAlert: string | null;
  setExportAlert: (message: string | null) => void;
  /** 刷新后恢复进行中的导出进度（目录句柄需重新选）。 */
  restoreExportTask: () => Promise<void>;
  /** 关闭/清除导出进度条。 */
  clearExportProgress: () => void;
  /** 取消当前导出（kill 后端任务 + Blender 子进程）。 */
  cancelExport: () => Promise<void>;

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

  /** 段拖动：整体平移（shift）、S 段拖边缘（re-time）、C 段拖边缘（trim）。 */
  shiftSegment: (cameraName: string, segmentName: string, deltaTime: number) => void;
  retimeSegment: (cameraName: string, segmentName: string, which: 'start' | 'end', newTime: number) => void;
  trimSegment: (cameraName: string, segmentName: string, which: 'start' | 'end', newTime: number) => void;
  /** 改段的原始时长上限（Duration）。 */
  setSegmentOriginalDuration: (cameraName: string, segmentName: string, duration: number) => void;

  /** 新增相机轴（机位）：新建 cam_0N + 初始 3s 段 + 自动选中。 */
  addCamera: () => void;
  /** 删除相机轴：删除该相机的所有段；删除活跃相机则切到剩余第一个。 */
  deleteCamera: (cameraName: string) => void;

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

function pickDirectory(): Promise<FileSystemDirectoryHandle | null> {
  const picker = (window as unknown as {
    showDirectoryPicker?: () => Promise<FileSystemDirectoryHandle>;
  }).showDirectoryPicker;
  if (!picker) {
    return Promise.resolve(null);
  }
  return picker();
}

async function pollExportTask(
  taskId: string,
  directoryHandle: FileSystemDirectoryHandle,
  folderName: string,
): Promise<void> {
  const written = new Set<string>();
  for (;;) {
    let status;
    try {
      status = await fetchExportStatus(taskId);
    } catch (error) {
      useStore.setState((current) => ({
        exportProgress: current.exportProgress
          ? { ...current.exportProgress, error: error instanceof Error ? error.message : 'Export status fetch failed' }
          : null,
      }));
      localStorage.removeItem('export_task');
      return;
    }
    useStore.setState({
      exportProgress: {
        taskId,
        status: status.status as ExportProgress['status'],
        completedFiles: status.progress.completed_files,
        totalFiles: status.progress.total_files,
        currentFile: status.progress.current_file,
        currentFrame: status.progress.current_frame,
        currentTotalFrames: status.progress.current_total_frames,
        error: status.error,
      },
    });
    for (const file of status.files) {
      if (written.has(file.filename)) continue;
      await writeFilesToDirectory(
        directoryHandle,
        [{ filename: file.filename, contentBase64: file.content_base64 }],
        folderName,
      );
      written.add(file.filename);
    }
    if (
      status.status === 'done' ||
      status.status === 'error' ||
      status.status === 'cancelled'
    ) {
      localStorage.removeItem('export_task');
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

function buildEditingSegments(
  segments: ShotSegment[],
  gltfSegmentPoses: Record<string, Record<string, { start_pose: Pose; end_pose: Pose }>>,
  segmentTargets: Record<string, Record<string, [number, number, number]>>,
  targetNodePositions: Record<string, [number, number, number]>,
  gltfAnimations: THREE.AnimationClip[] | null,
): ShotSegment[] {
  return segments.map((segment) => {
    const pose = gltfSegmentPoses[segment.camera_name]?.[segment.segment_name];
    // 每段 target：优先从 aim_target 动画提取的 segmentTargets；无动画（静态 target）回退到静态快照
    const targetName = segment.constraint?.rotation?.[0]?.target ?? null;
    const targetPosition =
      segmentTargets[segment.camera_name]?.[segment.segment_name] ??
      (targetName ? targetNodePositions[targetName] : undefined);
    // C 段：进入编辑态就现读完整采样点（keyframes），拖动/裁剪/平移都作用在 keyframes 上
    const complexKeyframes =
      segment.segment_type === 'C'
        ? extractComplexSegmentKeyframes(gltfAnimations, segment.segment_name)
        : null;
    return {
      ...segment,
      ...(complexKeyframes ? complexKeyframes : {}),
      orientation_mode:
        segment.orientation_mode ??
        (segment.constraint?.rotation?.length ? 'follow' : 'interpolate'),
      start_pose: pose?.start_pose ?? segment.start_pose,
      end_pose: pose?.end_pose ?? segment.end_pose,
      ...(targetPosition ? { target_position: targetPosition } : {}),
      original_duration: segment.original_duration ?? (segment.end_time - segment.start_time),
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
  exportProgress: null,
  exportAlert: null,
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
  editingCameras: null,
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
      editingCameras: editing ? (state.shot?.cameras ?? []) : null,
      editingSegments: editing
        ? buildEditingSegments(
            state.shot?.segments ?? [],
            state.gltfSegmentPoses,
            state.segmentTargets,
            state.targetNodePositions,
            state.gltfAnimations,
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
    // C 段 keyframes 完整保留（非破坏性），保存前按段范围裁到 [start_time, end_time] 再传后端。
    const segments = state.editingSegments.map((segment) => {
      if (segment.segment_type !== 'C') return segment;
      const inRange = (keyframe: { time: number }) =>
        keyframe.time >= segment.start_time && keyframe.time <= segment.end_time;
      return {
        ...segment,
        position_keyframes: segment.position_keyframes?.filter(inRange),
        rotation_keyframes: segment.rotation_keyframes?.filter(inRange),
      };
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
  exportMp4: async (resolution: string) => {
    const state = get();
    const shot = state.shot;
    if (!shot) return;
    const currentProgress = state.exportProgress;
    if (
      currentProgress &&
      currentProgress.status !== 'done' &&
      currentProgress.status !== 'error' &&
      currentProgress.status !== 'cancelled'
    ) {
      set({
        exportAlert:
          'An export is already in progress. Wait for it to finish or cancel it first.',
      });
      return;
    }
    try {
      const directoryHandle = await pickDirectory();
      if (!directoryHandle) {
        set({ errorMessage: 'Directory picker is not supported in this browser' });
        return;
      }
      const session = state.sessionList.find((item) => item.id === state.currentSessionId);
      const chatName = session?.folder_name || '';
      const latestBlend = [...state.blendVersions].sort((a, b) => b.mtime - a.mtime)[0];
      const blendPrefix = latestBlend ? latestBlend.filename.replace(/\.blend$/, '') : 'shot';
      const folderName = chatName ? `${chatName}_${blendPrefix}` : blendPrefix;
      const taskId = await startExportMp4(shot.export_hash, chatName, blendPrefix, resolution);
      localStorage.setItem(
        'export_task',
        JSON.stringify({ taskId, exportHash: shot.export_hash, folderName }),
      );
      set({
        errorMessage: null,
        exportProgress: {
          taskId,
          status: 'rendering',
          completedFiles: 0,
          totalFiles: 0,
          currentFile: null,
          currentFrame: 0,
          currentTotalFrames: 0,
          error: null,
        },
      });
      void pollExportTask(taskId, directoryHandle, folderName);
    } catch (error) {
      set({ errorMessage: error instanceof Error ? error.message : 'Export MP4 failed' });
    }
  },
  restoreExportTask: async () => {
    const raw = localStorage.getItem('export_task');
    if (!raw) return;
    let stored: { taskId: string; exportHash: string; folderName: string };
    try {
      stored = JSON.parse(raw);
    } catch {
      localStorage.removeItem('export_task');
      return;
    }
    try {
      const status = await fetchExportStatus(stored.taskId);
      set({
        exportProgress: {
          taskId: stored.taskId,
          status: status.status as ExportProgress['status'],
          completedFiles: status.progress.completed_files,
          totalFiles: status.progress.total_files,
          currentFile: status.progress.current_file,
          currentFrame: status.progress.current_frame,
          currentTotalFrames: status.progress.current_total_frames,
          error: status.error,
        },
      });
      if (status.status === 'done' || status.status === 'error') {
        localStorage.removeItem('export_task');
      }
    } catch {
      localStorage.removeItem('export_task');
    }
  },
  clearExportProgress: () => set({ exportProgress: null }),
  setExportAlert: (message) => set({ exportAlert: message }),
  cancelExport: async () => {
    const progress = get().exportProgress;
    if (!progress) return;
    try {
      const response = await fetch(`/api/shots/export-cancel/${progress.taskId}`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Cancel export failed');
      }
    } catch (error) {
      set({ errorMessage: error instanceof Error ? error.message : 'Cancel export failed' });
    }
  },
  exportBlend: async () => {
    const state = get();
    const shot = state.shot;
    if (!shot) return;
    try {
      const directoryHandle = await pickDirectory();
      if (!directoryHandle) {
        set({ errorMessage: 'Directory picker is not supported in this browser' });
        return;
      }
      const session = state.sessionList.find((item) => item.id === state.currentSessionId);
      const chatName = session?.folder_name || '';
      await exportBlendToDirectory(shot.export_hash, chatName, directoryHandle);
    } catch (error) {
      set({ errorMessage: error instanceof Error ? error.message : 'Export Blend failed' });
    }
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
        original_duration: 3,
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
  shiftSegment: (cameraName, segmentName, deltaTime) =>
    set((state) => {
      if (!state.editingSegments) return {};
      return {
        dirty: true,
        editingSegments: state.editingSegments.map((segment) => {
          if (segment.camera_name !== cameraName || segment.segment_name !== segmentName) return segment;
          const { start_time, end_time } = clampSegmentTimes(
            segment, state.editingSegments!, 'shift', deltaTime, state.framesPerSecond,
          );
          // C 段：烘焙关键帧的 time 跟着整体平移（保存后 blend 关键帧也正确）
          const actualDelta = start_time - segment.start_time;
          const position_keyframes = segment.position_keyframes
            ? segment.position_keyframes.map((keyframe) => ({ ...keyframe, time: keyframe.time + actualDelta }))
            : undefined;
          const rotation_keyframes = segment.rotation_keyframes
            ? segment.rotation_keyframes.map((keyframe) => ({ ...keyframe, time: keyframe.time + actualDelta }))
            : undefined;
          return { ...segment, start_time, end_time, position_keyframes, rotation_keyframes };
        }),
      };
    }),
  retimeSegment: (cameraName, segmentName, which, newTime) =>
    set((state) => {
      if (!state.editingSegments) return {};
      return {
        dirty: true,
        editingSegments: state.editingSegments.map((segment) => {
          if (segment.camera_name !== cameraName || segment.segment_name !== segmentName) return segment;
          const { start_time, end_time } = clampSegmentTimes(
            segment, state.editingSegments!, which, newTime, state.framesPerSecond,
          );
          return { ...segment, start_time, end_time };
        }),
      };
    }),
  trimSegment: (cameraName, segmentName, which, newTime) =>
    set((state) => {
      if (!state.editingSegments) return {};
      return {
        dirty: true,
        editingSegments: state.editingSegments.map((segment) => {
          if (segment.camera_name !== cameraName || segment.segment_name !== segmentName) return segment;
          const { start_time, end_time } = clampSegmentTimes(
            segment, state.editingSegments!, which, newTime, state.framesPerSecond,
          );
          // 非破坏性：keyframes 保留完整采样，裁剪只改时间段；渲染/保存时按段范围裁（拖回来能恢复）
          return { ...segment, start_time, end_time };
        }),
      };
    }),
  setSegmentOriginalDuration: (cameraName, segmentName, duration) =>
    set((state) => {
      if (!state.editingSegments) return {};
      return {
        dirty: true,
        editingSegments: state.editingSegments.map((segment) =>
          segment.camera_name === cameraName && segment.segment_name === segmentName
            ? { ...segment, original_duration: Math.max(1, duration) }
            : segment,
        ),
      };
    }),
  addCamera: () =>
    set((state) => {
      if (!state.editingSegments) return {};
      const existingNames = new Set(
        (state.editingCameras ?? []).map((camera) => camera.camera_name),
      );
      let maxN = 0;
      for (const name of existingNames) {
        const match = /^cam_(\d+)$/.exec(name);
        if (match) maxN = Math.max(maxN, parseInt(match[1], 10));
      }
      const cameraName = `cam_${String(maxN + 1).padStart(2, '0')}`;
      const segmentName = `${cameraName}_seg_01`;
      const newSegment: ShotSegment = {
        camera_name: cameraName,
        segment_name: segmentName,
        start_time: 0,
        end_time: 3,
        start_pose: { position: [0, 0, 0], rotation: [0, 0, 0] },
        end_pose: { position: [0, 0, 0], rotation: [0, 0, 0] },
        segment_type: 'S',
        orientation_mode: 'interpolate',
        original_duration: 3,
      };
      return {
        dirty: true,
        activeCameraName: cameraName,
        selectedSegment: { camera_name: cameraName, segment_name: segmentName },
        editingCameras: [...(state.editingCameras ?? []), { camera_name: cameraName }],
        editingSegments: [...state.editingSegments, newSegment],
      };
    }),
  deleteCamera: (cameraName) =>
    set((state) => {
      if (!state.editingSegments) return {};
      const remaining = state.editingSegments.filter(
        (segment) => segment.camera_name !== cameraName,
      );
      let activeCameraName = state.activeCameraName;
      if (state.activeCameraName === cameraName) {
        const remainingCameras = Array.from(
          new Set(remaining.map((segment) => segment.camera_name)),
        );
        activeCameraName = remainingCameras[0] ?? null;
      }
      const selectedSegment =
        state.selectedSegment?.camera_name === cameraName ? null : state.selectedSegment;
      return {
        dirty: true,
        activeCameraName,
        selectedSegment,
        editingCameras: (state.editingCameras ?? []).filter(
          (camera) => camera.camera_name !== cameraName,
        ),
        editingSegments: remaining,
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
      exportProgress: null,
      exportAlert: null,
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
