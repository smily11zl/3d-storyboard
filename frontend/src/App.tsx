import { useEffect, useState, useMemo } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { Pose, ShotSegment } from './types';
import { UploadZone } from './components/UploadZone';
import { CameraView } from './components/CameraView';
import { FreeView } from './components/FreeView';
import { Timeline } from './components/Timeline';
import { TopBar } from './components/TopBar';
import { EditToolbar } from './components/EditToolbar';
import { EditTimeline } from './components/EditTimeline';
import { SegmentSidebar } from './components/SegmentSidebar';
import { ChatPanel } from './components/ChatPanel';
import { ConfirmDialog } from './components/ConfirmDialog';
import { SettingsModal } from './components/SettingsModal';
import { useStore } from './store';
import { clone as cloneSkeleton } from 'three/examples/jsm/utils/SkeletonUtils.js';
import styles from './App.module.css';

function computeAnimationStartTime(gltf: GLTF): number {
  // Blender frame 1 = 1/fps seconds — animations don't start at time 0.
  // Find the earliest keyframe time across all animation tracks.
  let minimumTime = Infinity;
  for (const clip of gltf.animations) {
    for (const track of clip.tracks) {
      if (track.times.length > 0) {
        minimumTime = Math.min(minimumTime, track.times[0]);
      }
    }
  }
  return Number.isFinite(minimumTime) ? minimumTime : 0;
}

/** 从 glTF clips 预计算每段首尾 pose（glTF Y-up 坐标），作为编辑态的编辑载体。 */
function extractSegmentPoses(
  gltf: GLTF,
): Record<string, Record<string, { start_pose: Pose; end_pose: Pose }>> {
  const poses: Record<string, Record<string, { start_pose: Pose; end_pose: Pose }>> = {};
  for (const clip of gltf.animations) {
    const positionTrack = clip.tracks.find((track) => track.name.endsWith('.position'));
    const quaternionTrack = clip.tracks.find((track) => track.name.endsWith('.quaternion'));
    if (!positionTrack || !quaternionTrack) continue;
    const nodeName = positionTrack.name.slice(0, -'.position'.length);
    const startPosition: [number, number, number] = [
      positionTrack.values[0],
      positionTrack.values[1],
      positionTrack.values[2],
    ];
    const endPositionIndex = positionTrack.values.length - 3;
    const endPosition: [number, number, number] = [
      positionTrack.values[endPositionIndex],
      positionTrack.values[endPositionIndex + 1],
      positionTrack.values[endPositionIndex + 2],
    ];
    const startQuaternion = new THREE.Quaternion(
      quaternionTrack.values[0],
      quaternionTrack.values[1],
      quaternionTrack.values[2],
      quaternionTrack.values[3],
    );
    const endQuaternionIndex = quaternionTrack.values.length - 4;
    const endQuaternion = new THREE.Quaternion(
      quaternionTrack.values[endQuaternionIndex],
      quaternionTrack.values[endQuaternionIndex + 1],
      quaternionTrack.values[endQuaternionIndex + 2],
      quaternionTrack.values[endQuaternionIndex + 3],
    );
    const startEuler = new THREE.Euler().setFromQuaternion(startQuaternion);
    const endEuler = new THREE.Euler().setFromQuaternion(endQuaternion);
    (poses[nodeName] ??= {})[clip.name] = {
      start_pose: {
        position: startPosition,
        rotation: [startEuler.x, startEuler.y, startEuler.z],
      },
      end_pose: {
        position: endPosition,
        rotation: [endEuler.x, endEuler.y, endEuler.z],
      },
    };
  }
  return poses;
}

/** 采样 VectorKeyframeTrack 在 time 处的值（线性插值，越界取端点）。 */
function sampleVectorTrack(
  track: THREE.VectorKeyframeTrack,
  time: number,
): [number, number, number] {
  const times = track.times;
  const values = track.values as Float32Array;
  const stride = track.getValueSize();
  if (times.length === 0) return [0, 0, 0];
  if (time <= times[0]) return [values[0], values[1], values[2]];
  if (time >= times[times.length - 1]) {
    const offset = (times.length - 1) * stride;
    return [values[offset], values[offset + 1], values[offset + 2]];
  }
  for (let i = 0; i < times.length - 1; i++) {
    if (time >= times[i] && time <= times[i + 1]) {
      const t = (time - times[i]) / (times[i + 1] - times[i]);
      const a = i * stride;
      const b = (i + 1) * stride;
      return [
        values[a] + (values[b] - values[a]) * t,
        values[a + 1] + (values[b + 1] - values[a + 1]) * t,
        values[a + 2] + (values[b + 2] - values[a + 2]) * t,
      ];
    }
  }
  const offset = (times.length - 1) * stride;
  return [values[offset], values[offset + 1], values[offset + 2]];
}

/** 从 aim_target 位置动画里，按段提取每段 TRACK_TO 目标点位置（glTF Y-up）。 */
function extractSegmentTargets(
  gltf: GLTF,
  segments: ShotSegment[],
): Record<string, Record<string, [number, number, number]>> {
  const result: Record<string, Record<string, [number, number, number]>> = {};

  const targetNames = new Set<string>();
  for (const segment of segments) {
    const targetName = segment.constraint?.rotation?.[0]?.target ?? null;
    const mode =
      segment.orientation_mode ?? (segment.constraint?.rotation?.length ? 'follow' : 'interpolate');
    if (mode === 'follow' && targetName) targetNames.add(targetName);
  }
  if (targetNames.size === 0) return result;

  const targetTracks = new Map<string, THREE.VectorKeyframeTrack>();
  for (const clip of gltf.animations) {
    const positionTrack = clip.tracks.find((track) => track.name.endsWith('.position'));
    if (!positionTrack) continue;
    const nodeName = positionTrack.name.slice(0, -'.position'.length);
    if (targetNames.has(nodeName) && !targetTracks.has(nodeName)) {
      targetTracks.set(nodeName, positionTrack as THREE.VectorKeyframeTrack);
    }
  }

  for (const segment of segments) {
    const targetName = segment.constraint?.rotation?.[0]?.target ?? null;
    if (!targetName) continue;
    const mode =
      segment.orientation_mode ?? (segment.constraint?.rotation?.length ? 'follow' : 'interpolate');
    if (mode !== 'follow') continue;
    const track = targetTracks.get(targetName);
    if (!track) continue;
    // 用段中点采样（段起点正好是前一段的终点关键帧，会采到前一段的 target）
    const midTime = (segment.start_time + segment.end_time) / 2;
    const position = sampleVectorTrack(track, midTime);
    (result[segment.camera_name] ??= {})[segment.segment_name] = position;
  }

  return result;
}

function cloneGLTF(source: GLTF): GLTF {
  // Each Canvas needs its own scene copy — Three.js objects can only have one parent.
  // SkeletonUtils.clone properly clones skinned meshes (skeleton/bone references),
  // unlike scene.clone(true) which leaves SkinnedMesh.skeleton pointing at the
  // ORIGINAL bones → NaN skinning matrices → black/invisible meshes.
  const clonedScene = cloneSkeleton(source.scene);
  return {
    scene: clonedScene,
    animations: source.animations,
    cameras: source.cameras,
    parser: source.parser,
    userData: source.userData,
  };
}

function App() {
  const shot = useStore((state) => state.shot);
  const isLoading = useStore((state) => state.isLoading);
  const sidebarCollapsed = useStore((state) => state.sidebarCollapsed);
  const editMode = useStore((state) => state.editMode);
  const exportAlert = useStore((state) => state.exportAlert);
  const setExportAlert = useStore((state) => state.setExportAlert);
  const [gltfOriginal, setGltfOriginal] = useState<GLTF | null>(null);
  const [sceneLoading, setSceneLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Settings modal can be requested from anywhere (e.g. the generate placeholder)
  useEffect(() => {
    const openSettings = () => setSettingsOpen(true);
    window.addEventListener('open-settings', openSettings);
    return () => window.removeEventListener('open-settings', openSettings);
  }, []);

  // 刷新后恢复进行中的导出进度
  useEffect(() => {
    void useStore.getState().restoreExportTask();
  }, []);

  // Load GLTF once, outside Canvas
  useEffect(() => {
    if (!shot?.gltf_output_url) {
      setGltfOriginal(null);
      setSceneLoading(false);
      return;
    }

    setSceneLoading(true);
    const loader = new GLTFLoader();

    loader.load(
      shot.gltf_output_url,
      (loadedData) => {
        // Store the earliest animation keyframe time so the viewer can
        // start at frame 1 (pose) instead of time 0 (T-pose bind)
        const startTime = computeAnimationStartTime(loadedData);
        // 预读取所有节点位置（target Empty 用于 TRACK_TO 目标点编辑）
        const targetNodePositions: Record<string, [number, number, number]> = {};
        loadedData.scene.traverse((node) => {
          if (node.name) {
            const worldPosition = new THREE.Vector3();
            node.getWorldPosition(worldPosition);
            targetNodePositions[node.name] = [worldPosition.x, worldPosition.y, worldPosition.z];
          }
        });
        useStore.setState({
          animationStartTime: startTime,
          currentTime: startTime,
          targetNodePositions,
          gltfSegmentPoses: extractSegmentPoses(loadedData),
          segmentTargets: extractSegmentTargets(loadedData, shot.segments ?? []),
          gltfAnimations: loadedData.animations,
        });
        setGltfOriginal(loadedData);
        setSceneLoading(false);
      },
      undefined,
      (error) => {
        console.error('GLTF load error:', error);
        setSceneLoading(false);
      },
    );
  }, [shot?.gltf_output_url]);

  // 加载 blend 版本列表（版本切换由用户在聊天框下拉手动选择，不自动跳到最新）
  useEffect(() => {
    const exportHash = shot?.export_hash;
    if (!exportHash) return;
    const { loadBlendVersions } = useStore.getState();
    void loadBlendVersions(exportHash);
  }, [shot?.export_hash]);

  // Clone separate scene copies for each Canvas (Three.js objects can only have one parent)
  const gltfForCamera = useMemo(
    () => (gltfOriginal ? cloneGLTF(gltfOriginal) : null),
    [gltfOriginal],
  );
  const gltfForFree = useMemo(
    () => (gltfOriginal ? cloneGLTF(gltfOriginal) : null),
    [gltfOriginal],
  );
  // 编辑态独立 scene 副本：新增相机等编辑态独有场景对象加在副本里，查看态用原始副本，彻底隔离。
  const gltfForCameraEdit = useMemo(
    () => (editMode && gltfOriginal ? cloneGLTF(gltfOriginal) : null),
    [editMode, gltfOriginal],
  );
  const gltfForFreeEdit = useMemo(
    () => (editMode && gltfOriginal ? cloneGLTF(gltfOriginal) : null),
    [editMode, gltfOriginal],
  );

  const hasContent = shot || isLoading;
  const showViewports = hasContent && gltfForCamera && gltfForFree && !sceneLoading;

  return (
    <div className={styles.appContainer}>
      {editMode ? (
        <EditToolbar />
      ) : (
        <TopBar onOpenSettings={() => setSettingsOpen(true)} />
      )}
      <div className={styles.mainArea}>
        {/* Keep ChatPanel mounted (CSS-hidden when collapsed or editing) so the
            chat history survives toggling the sidebar AND entering/exiting edit mode */}
        <div className={(sidebarCollapsed || editMode) ? styles.hidden : undefined}>
          <ChatPanel />
        </div>
        <div className={styles.contentArea}>
          {!editMode && <UploadZone />}
          {hasContent && !gltfOriginal && (
            <div className={styles.loadingOverlay}>
              <span>{sceneLoading ? 'Loading 3D scene...' : 'Converting...'}</span>
            </div>
          )}
          <div className={styles.editBody}>
            {showViewports && (
              <div className={styles.viewportArea}>
                <CameraView gltfData={gltfForCamera} editGltfData={gltfForCameraEdit} />
                <FreeView gltfData={gltfForFree} editGltfData={gltfForFreeEdit} />
              </div>
            )}
            {editMode && <SegmentSidebar />}
          </div>
          {editMode ? <EditTimeline /> : <Timeline />}
        </div>
      </div>
      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
      {exportAlert && (
        <ConfirmDialog
          title="Export in progress"
          message={exportAlert}
          confirmLabel="OK"
          onConfirm={() => setExportAlert(null)}
          onClose={() => setExportAlert(null)}
        />
      )}
    </div>
  );
}

export default App;
