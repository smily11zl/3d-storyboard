import { useEffect, useState, useMemo } from 'react';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { UploadZone } from './components/UploadZone';
import { CameraView } from './components/CameraView';
import { FreeView } from './components/FreeView';
import { Timeline } from './components/Timeline';
import { TopBar } from './components/TopBar';
import { Sidebar } from './components/Sidebar';
import { ChatPanel } from './components/ChatPanel';
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
  return minimumTime === Infinity ? 0 : minimumTime;
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

/** AI 生成模式主内容区：查看器保持当前场景；无场景时提示。 */
function GenerateContent({
  hasContent,
  showViewports,
  gltfForCamera,
  gltfForFree,
  sceneLoading,
}: {
  hasContent: boolean;
  showViewports: boolean;
  gltfForCamera: GLTF | null;
  gltfForFree: GLTF | null;
  sceneLoading: boolean;
}) {
  if (showViewports) {
    return (
      <>
        <div className={styles.viewportArea}>
          <CameraView gltfData={gltfForCamera} />
          <FreeView gltfData={gltfForFree} />
        </div>
        <Timeline />
      </>
    );
  }
  if (hasContent) {
    return (
      <div className={styles.loadingOverlay}>
        <span>{sceneLoading ? 'Loading 3D scene...' : 'Converting...'}</span>
      </div>
    );
  }
  return (
    <div className={styles.generatePlaceholder}>
      <span className={styles.generateTitle}>AI 场景生成</span>
      <span className={styles.generateHint}>
        在左侧输入场景描述，生成或上传后在此查看 3D 场景
      </span>
    </div>
  );
}

function App() {
  const shot = useStore((state) => state.shot);
  const isLoading = useStore((state) => state.isLoading);
  const sidebarMode = useStore((state) => state.sidebarMode);
  const sidebarCollapsed = useStore((state) => state.sidebarCollapsed);
  const [gltfOriginal, setGltfOriginal] = useState<GLTF | null>(null);
  const [sceneLoading, setSceneLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Settings modal can be requested from anywhere (e.g. the generate placeholder)
  useEffect(() => {
    const openSettings = () => setSettingsOpen(true);
    window.addEventListener('open-settings', openSettings);
    return () => window.removeEventListener('open-settings', openSettings);
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
        useStore.setState({
          animationStartTime: startTime,
          currentTime: startTime,
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

  // Clone separate scene copies for each Canvas (Three.js objects can only have one parent)
  const gltfForCamera = useMemo(
    () => (gltfOriginal ? cloneGLTF(gltfOriginal) : null),
    [gltfOriginal],
  );
  const gltfForFree = useMemo(
    () => (gltfOriginal ? cloneGLTF(gltfOriginal) : null),
    [gltfOriginal],
  );

  const hasContent = shot || isLoading;
  const showViewports = hasContent && gltfForCamera && gltfForFree && !sceneLoading;

  return (
    <div className={styles.appContainer}>
      <TopBar onOpenSettings={() => setSettingsOpen(true)} />
      <div className={styles.mainArea}>
        {!sidebarCollapsed &&
          (sidebarMode === 'generate' ? (
            <ChatPanel onBack={() => useStore.getState().setSidebarMode('upload')} />
          ) : (
            <Sidebar />
          ))}
        <div className={styles.contentArea}>
          {sidebarMode === 'upload' ? (
            <>
              <UploadZone />
              {hasContent && !gltfOriginal && (
                <div className={styles.loadingOverlay}>
                  <span>{sceneLoading ? 'Loading 3D scene...' : 'Converting...'}</span>
                </div>
              )}
              {showViewports && (
                <div className={styles.viewportArea}>
                  <CameraView gltfData={gltfForCamera} />
                  <FreeView gltfData={gltfForFree} />
                </div>
              )}
              <Timeline />
            </>
          ) : (
            <GenerateContent
              hasContent={hasContent}
              showViewports={showViewports}
              gltfForCamera={gltfForCamera}
              gltfForFree={gltfForFree}
              sceneLoading={sceneLoading}
            />
          )}
        </div>
      </div>
      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}

export default App;
