import { useEffect, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { TransformControls } from '@react-three/drei';
import { useStore } from '../store';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import * as THREE from 'three';

interface SelectionControlsProperties {
  gltfData: GLTF;
  selectedObject: THREE.Object3D | null;
  onSelect: (object: THREE.Object3D | null) => void;
  transformMode: 'translate' | 'rotate';
  onTransformModeChange: (mode: 'translate' | 'rotate') => void;
  infoDisplayReference: React.RefObject<HTMLSpanElement | null>;
}

/** Finds the armature root (character container) that drives a skinned
 *  mesh: walk up the skeleton's bone chain, then take the bone's parent. */
function findArmatureRoot(mesh: THREE.SkinnedMesh): THREE.Object3D {
  const bones = mesh.skeleton.bones;
  if (bones.length === 0) return mesh;
  let rootBone: THREE.Object3D = bones[0];
  while (rootBone.parent && (rootBone.parent as THREE.Bone).isBone) {
    rootBone = rootBone.parent;
  }
  return rootBone.parent ?? mesh;
}

/** Click-to-select characters (skinned meshes) in the Free View,
 *  then manipulate them with a TransformControls gizmo:
 *  - W = translate, E = rotate, Esc = deselect
 *  - selected character gets an emissive highlight
 *  - position/rotation values stream to the top toolbar via DOM */
export function SelectionControls({
  gltfData,
  selectedObject,
  onSelect,
  transformMode,
  onTransformModeChange,
  infoDisplayReference,
}: SelectionControlsProperties) {
  const { camera, gl } = useThree();
  const raycasterReference = useRef(new THREE.Raycaster());
  const pointerReference = useRef(new THREE.Vector2());
  const draggingReference = useRef(false);
  const previousMaterialsReference = useRef<
    Map<THREE.Mesh, { emissive: THREE.Color; emissiveIntensity: number }>
  >(new Map());

  // Click to select a character (skinned mesh); click empty space to deselect
  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (draggingReference.current) return; // ignore click after gizmo drag

      const rect = gl.domElement.getBoundingClientRect();
      pointerReference.current.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointerReference.current.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      raycasterReference.current.setFromCamera(pointerReference.current, camera);
      // Only test the model scene — gizmo handles & grid are excluded,
      // so clicking them never deselects.
      const intersects = raycasterReference.current.intersectObjects([gltfData.scene], true);
      const characterHit = intersects.find(
        (intersection) => (intersection.object as THREE.SkinnedMesh).isSkinnedMesh,
      );
      onSelect(characterHit ? findArmatureRoot(characterHit.object as THREE.SkinnedMesh) : null);
    };

    gl.domElement.addEventListener('click', handleClick);
    return () => gl.domElement.removeEventListener('click', handleClick);
  }, [camera, gl, gltfData.scene, onSelect]);

  // Keyboard shortcuts: W = move, E = rotate, Esc = deselect
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'w' || event.key === 'W') onTransformModeChange('translate');
      if (event.key === 'e' || event.key === 'E') onTransformModeChange('rotate');
      if (event.key === 'Escape') onSelect(null);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onSelect, onTransformModeChange]);

  // Emissive highlight on the selected character; restore on change/deselect
  useEffect(() => {
    for (const [mesh, original] of previousMaterialsReference.current) {
      const material = mesh.material as THREE.MeshStandardMaterial;
      material.emissive.copy(original.emissive);
      material.emissiveIntensity = original.emissiveIntensity;
    }
    previousMaterialsReference.current.clear();

    if (selectedObject) {
      selectedObject.traverse((node) => {
        if ((node as THREE.Mesh).isMesh) {
          const mesh = node as THREE.Mesh;
          const material = mesh.material as THREE.MeshStandardMaterial;
          if (material && material.emissive) {
            previousMaterialsReference.current.set(mesh, {
              emissive: material.emissive.clone(),
              emissiveIntensity: material.emissiveIntensity,
            });
            material.emissive.set('#ff8c42');
            material.emissiveIntensity = 0.35;
          }
        }
      });
    }
  }, [selectedObject]);

  // Stream position/rotation to the toolbar every frame (direct DOM write)
  useFrame(() => {
    if (!selectedObject || !infoDisplayReference.current) return;
    const toDegrees = (radians: number) => ((radians * 180) / Math.PI).toFixed(1);
    const position = selectedObject.position;
    const rotation = selectedObject.rotation;
    infoDisplayReference.current.textContent =
      `位置 (${position.x.toFixed(2)}, ${position.y.toFixed(2)}, ${position.z.toFixed(2)})  ` +
      `旋转 (${toDegrees(rotation.x)}°, ${toDegrees(rotation.y)}°, ${toDegrees(rotation.z)}°)`;
  });

  /** Writes the current transform to the shared store so the OTHER
   *  viewport (Camera View's scene copy) stays in sync. */
  const publishTransform = () => {
    if (!selectedObject) return;
    const position = selectedObject.position;
    const quaternion = selectedObject.quaternion;
    useStore.getState().setCharacterTransform(
      selectedObject.name,
      [position.x, position.y, position.z],
      [quaternion.x, quaternion.y, quaternion.z, quaternion.w],
    );
  };

  return (
    <>
      {selectedObject && (
        <TransformControls
          object={selectedObject}
          mode={transformMode}
          onChange={publishTransform}
          onMouseDown={() => {
            draggingReference.current = true;
          }}
          onMouseUp={() => {
            draggingReference.current = false;
            publishTransform();
          }}
        />
      )}
    </>
  );
}
