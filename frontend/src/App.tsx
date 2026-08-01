import { useEffect, useState, useMemo } from 'react';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { UploadZone } from './components/UploadZone';
import { CameraView } from './components/CameraView';
import { FreeView } from './components/FreeView';
import { Timeline } from './components/Timeline';
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

function App() {
  const shot = useStore((state) => state.shot);
  const isLoading = useStore((state) => state.isLoading);
  const [gltfOriginal, setGltfOriginal] = useState<GLTF | null>(null);
  const [sceneLoading, setSceneLoading] = useState(false);

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
    </div>
  );
}

export default App;
