import { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { Environment, Lightformer, OrbitControls, Grid } from '@react-three/drei';
import { SceneModel } from './SceneModel';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import styles from './FreeView.module.css';

interface FreeViewProperties {
  gltfData: GLTF;
}

export function FreeView({ gltfData }: FreeViewProperties) {
  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.label}>Free View</span>
      </div>
      <div className={styles.canvasContainer}>
        <Canvas
          shadows
          camera={{ position: [5, 4, 8], fov: 50 }}
          gl={{ antialias: true }}
          onCreated={({ camera }) => camera.lookAt(0, 0, 0)}
        >
          <color attach="background" args={['#121212']} />
          {/* Locally-generated environment light (no CDN, no directional
              shadows): soft studio lighting that reveals material colors
              and gives depth without hard shadows. */}
          <Environment resolution={256}>
            <Lightformer intensity={2.0} position={[0, 5, 0]} rotation-x={Math.PI / 2} scale={[10, 10, 1]} />
            <Lightformer intensity={1.0} position={[-5, 1, -5]} rotation-y={Math.PI / 4} scale={[8, 1, 1]} />
            <Lightformer intensity={1.0} position={[5, 1, 5]} rotation-y={-Math.PI / 4} scale={[8, 1, 1]} />
          </Environment>
          <Suspense fallback={null}>
            <Grid
              position={[0, 0, 0]}
              args={[20, 20]}
              cellColor="#333333"
              sectionColor="#222222"
              fadeDistance={30}
              infiniteGrid
            />
            <SceneModel
              gltfData={gltfData}
              cameraName={null}
              lockedCamera={false}
            />
            <OrbitControls makeDefault />
          </Suspense>
        </Canvas>
      </div>
    </div>
  );
}
