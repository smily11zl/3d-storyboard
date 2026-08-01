import { Suspense, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import {
  Environment,
  Lightformer,
  OrbitControls,
  Grid,
  GizmoHelper,
  GizmoViewport,
} from '@react-three/drei';
import { SceneModel } from './SceneModel';
import { CameraIndicator } from './CameraIndicator';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import styles from './FreeView.module.css';

interface FreeViewProperties {
  gltfData: GLTF;
}

/** Reads the orbit camera's azimuth/polar angles every frame and writes
 *  them directly to a DOM element (no React re-renders). */
function AngleTracker({ displayReference }: { displayReference: React.RefObject<HTMLSpanElement | null> }) {
  const controlsReference = useRef<any>(null);

  useFrame(() => {
    const controls = controlsReference.current;
    if (!controls || !displayReference.current) return;

    // azimuthAngle: -π..π around Y, polarAngle: 0..π from top
    let azimuthDegrees = (controls.azimuthAngle * 180) / Math.PI;
    azimuthDegrees = ((azimuthDegrees % 360) + 360) % 360; // normalize to 0..360
    const polarDegrees = (controls.polarAngle * 180) / Math.PI;

    displayReference.current.textContent =
      `Azimuth ${azimuthDegrees.toFixed(1)}°  Polar ${polarDegrees.toFixed(1)}°`;
  });

  return <OrbitControls ref={controlsReference} makeDefault />;
}

export function FreeView({ gltfData }: FreeViewProperties) {
  const angleDisplayReference = useRef<HTMLSpanElement>(null);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.label}>Free View</span>
      </div>
      <div className={styles.canvasContainer}>
        {/* Angle overlay — top-left, updated via DOM directly */}
        <div className={styles.angleOverlay}>
          <span ref={angleDisplayReference}>Azimuth 0.0°  Polar 0.0°</span>
        </div>
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
            {/* Blender-style camera wireframes, follow camera animation */}
            <CameraIndicator gltfData={gltfData} />
            <AngleTracker displayReference={angleDisplayReference} />
          </Suspense>
          {/* Blender-style XYZ rotation gizmo, bottom-right */}
          <GizmoHelper alignment="bottom-right" margin={[60, 60]}>
            <GizmoViewport
              axisColors={['#f3727f', '#1ed760', '#539df5']}
              labelColor="white"
            />
          </GizmoHelper>
        </Canvas>
      </div>
    </div>
  );
}
