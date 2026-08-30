import { Suspense, useRef, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import {
  Environment,
  Lightformer,
  OrbitControls,
  GizmoHelper,
  GizmoViewport,
} from '@react-three/drei';
import { SceneModel } from './SceneModel';
import { CameraIndicator } from './CameraIndicator';
import { SelectionControls } from './SelectionControls';
import { BrowseControls } from './BrowseControls';
import { useStore } from '../store';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import * as THREE from 'three';
import styles from './FreeView.module.css';

interface FreeViewProperties {
  gltfData: GLTF;
  editGltfData?: GLTF | null;
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

export function FreeView({ gltfData, editGltfData }: FreeViewProperties) {
  const angleDisplayReference = useRef<HTMLSpanElement>(null);
  const transformInfoReference = useRef<HTMLSpanElement>(null);
  const [selectedObject, setSelectedObject] = useState<THREE.Object3D | null>(null);
  const [transformMode, setTransformMode] = useState<'translate' | 'rotate'>('translate');
  // 'browse' = game-style camera movement (WASD+QE); 'edit' = character gizmo (W/E)
  const [viewMode, setViewMode] = useState<'browse' | 'edit'>('browse');
  const editMode = useStore((state) => state.editMode);

  // 编辑态用独立 scene 副本，查看态用原始副本（新增相机等编辑态独有对象加在副本）。
  const activeGltf = editMode && editGltfData ? editGltfData : gltfData;

  // Tab toggles between browse and edit modes
  useEffect(() => {
    const handleTab = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return;
      // Let Tab work normally inside inputs/textarea (focus navigation)
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return;
      }
      event.preventDefault();
      setViewMode((mode) => (mode === 'browse' ? 'edit' : 'browse'));
      setSelectedObject(null); // clear character selection when switching
    };
    window.addEventListener('keydown', handleTab);
    return () => window.removeEventListener('keydown', handleTab);
  }, []);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span className={styles.label}>Free View</span>
        {/* Mode indicator + switch */}
        <div className={styles.modeSwitcher}>
          <button
            className={viewMode === 'browse' ? styles.modeButtonActive : styles.modeButton}
            onClick={() => {
              setViewMode('browse');
              setSelectedObject(null);
            }}
            title="Tab"
          >
            Browse
          </button>
          <button
            className={viewMode === 'edit' ? styles.modeButtonActive : styles.modeButton}
            onClick={() => {
              setViewMode('edit');
              setSelectedObject(null);
            }}
            title="Tab"
          >
            Edit
          </button>
        </div>
      </div>
      {/* Character transform toolbar — visible only while a character is selected */}
      {selectedObject && (
        <div className={styles.selectionBar}>
          <span className={styles.selectionName}>Character: {selectedObject.name}</span>
          <button
            className={transformMode === 'translate' ? styles.modeButtonActive : styles.modeButton}
            onClick={() => setTransformMode('translate')}
            title="W"
          >
            Move W
          </button>
          <button
            className={transformMode === 'rotate' ? styles.modeButtonActive : styles.modeButton}
            onClick={() => setTransformMode('rotate')}
            title="E"
          >
            Rotate E
          </button>
          <span ref={transformInfoReference} className={styles.selectionInfo}>
            Position (0.00, 0.00, 0.00)
          </span>
        </div>
      )}
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
            {/* No artificial Grid here — the scene's own ground plane is the
                floor. A second grid at y=0 caused z-fighting flicker while
                orbiting. */}
            <SceneModel
              gltfData={activeGltf}
              cameraName={null}
              lockedCamera={false}
            />
            {/* Blender-style camera wireframes, follow camera animation */}
            <CameraIndicator gltfData={activeGltf} />
            <AngleTracker displayReference={angleDisplayReference} />
            <SelectionControls
              gltfData={activeGltf}
              selectedObject={selectedObject}
              onSelect={setSelectedObject}
              transformMode={transformMode}
              onTransformModeChange={setTransformMode}
              infoDisplayReference={transformInfoReference}
              enabled={viewMode === 'edit'}
            />
            <BrowseControls enabled={viewMode === 'browse'} />
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
