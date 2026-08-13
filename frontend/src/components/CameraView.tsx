import { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { Environment, Lightformer } from '@react-three/drei';
import { SceneModel } from './SceneModel';
import { CameraFrameOverlay } from './CameraFrameOverlay';
import { useStore } from '../store';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import styles from './CameraView.module.css';

interface CameraViewProperties {
  gltfData: GLTF;
}

export function CameraView({ gltfData }: CameraViewProperties) {
  const shot = useStore((state) => state.shot);
  const activeCameraName = useStore((state) => state.activeCameraName);
  const cameras = shot?.cameras ?? [];

  if (!shot) return null;

  const handleCameraChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    useStore.getState().setActiveCamera(event.target.value);
  };

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.label}>Camera View</span>
        <select
          className={styles.cameraSelect}
          value={activeCameraName ?? ''}
          onChange={handleCameraChange}
        >
          {cameras.length === 0 ? (
            <option value="">Default View</option>
          ) : (
            cameras.map((camera) => (
              <option key={camera.camera_name} value={camera.camera_name}>
                {camera.camera_name}
              </option>
            ))
          )}
        </select>
      </div>
      <div className={styles.canvasContainer}>
        <Canvas
          camera={{ position: [3, 2, 5], fov: 50 }}
          gl={{ antialias: true }}
          onCreated={({ camera }) => camera.lookAt(0, 0, 0)}
        >
          <color attach="background" args={['#121212']} />
          {/* Locally-generated environment light (no CDN, no directional
              shadows): soft studio lighting that reveals material colors
              and gives depth without hard shadows. Outside Suspense so
              the scene renders even while the env map is generating. */}
          <Environment resolution={256}>
            <Lightformer intensity={2.0} position={[0, 5, 0]} rotation-x={Math.PI / 2} scale={[10, 10, 1]} />
            <Lightformer intensity={1.0} position={[-5, 1, -5]} rotation-y={Math.PI / 4} scale={[8, 1, 1]} />
            <Lightformer intensity={1.0} position={[5, 1, 5]} rotation-y={-Math.PI / 4} scale={[8, 1, 1]} />
          </Environment>
          <Suspense fallback={null}>
            <SceneModel
              gltfData={gltfData}
              cameraName={activeCameraName}
              lockedCamera
            />
          </Suspense>
        </Canvas>
        <CameraFrameOverlay />
      </div>
    </div>
  );
}
