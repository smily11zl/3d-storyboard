import { useMemo, useRef } from 'react';
import { TransformControls } from '@react-three/drei';
import { useStore } from '../store';
import type { ShotSegment } from '../types';
import type { GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import * as THREE from 'three';

interface CameraEditControlsProperties {
  gltfData: GLTF;
}

/** 编辑态下拖拽相机（线性段）或目标点（TRACK_TO 段）来改段 pose。 */
export function CameraEditControls({ gltfData }: CameraEditControlsProperties) {
  const editMode = useStore((state) => state.editMode);
  const selectedSegment = useStore((state) => state.selectedSegment);
  const editingSegments = useStore((state) => state.editingSegments);
  const setSegmentPose = useStore((state) => state.setSegmentPose);
  const setSegmentTarget = useStore((state) => state.setSegmentTarget);
  // TransformControls 在 attach 时会触发一次 onChange（值未变），
  // 用「上次值 ref」挡住它，避免选中段就误置 dirty=true。
  const lastTargetPosition = useRef<[number, number, number] | null>(null);
  const lastCameraPosition = useRef<[number, number, number] | null>(null);

  const { cameraNode, targetNode, segment } = useMemo<{
    cameraNode: THREE.Object3D | null;
    targetNode: THREE.Object3D | null;
    segment: ShotSegment | null;
  }>(() => {
    if (!editMode || !selectedSegment) {
      return { cameraNode: null, targetNode: null, segment: null };
    }
    const state = useStore.getState();
    const segments =
      state.editMode && state.editingSegments
        ? state.editingSegments
        : state.shot?.segments ?? [];
    const found = segments.find(
      (candidate) =>
        candidate.camera_name === selectedSegment.camera_name &&
        candidate.segment_name === selectedSegment.segment_name,
    );
    if (!found) return { cameraNode: null, targetNode: null, segment: null };
    const targetName = found.constraint?.rotation?.[0]?.target ?? null;
    let cameraNode: THREE.Object3D | null = null;
    let targetNode: THREE.Object3D | null = null;
    gltfData.scene.traverse((node) => {
      if (node.name === found.camera_name && (node as THREE.PerspectiveCamera).isCamera) {
        cameraNode = node;
      }
      if (targetName && node.name === targetName) {
        targetNode = node;
      }
    });
    return { cameraNode, targetNode, segment: found };
  }, [editMode, selectedSegment, editingSegments, gltfData]);

  if (!cameraNode || !segment) return null;

  const key = `${segment.camera_name}:${segment.segment_name}`;
  const dragTarget = targetNode ?? cameraNode;

  const handleChange = () => {
    if (targetNode) {
      const position = targetNode.position.toArray() as [number, number, number];
      if (lastTargetPosition.current === null) {
        lastTargetPosition.current = position;
        return;
      }
      if (
        position.every((value, index) => Math.abs(value - lastTargetPosition.current![index]) < 1e-6)
      ) {
        return;
      }
      lastTargetPosition.current = position;
      setSegmentTarget(key, position);
      return;
    }
    const currentTime = useStore.getState().currentTime;
    const toStart = Math.abs(currentTime - segment.start_time);
    const toEnd = Math.abs(currentTime - segment.end_time);
    const which = toStart <= toEnd ? 'start' : 'end';
    const position = cameraNode.position.toArray() as [number, number, number];
    const rotation = cameraNode.rotation.toArray() as [number, number, number];
    if (lastCameraPosition.current === null) {
      lastCameraPosition.current = position;
      return;
    }
    if (
      position.every((value, index) => Math.abs(value - lastCameraPosition.current![index]) < 1e-6)
    ) {
      return;
    }
    lastCameraPosition.current = position;
    setSegmentPose(key, which, position, rotation);
  };

  return <TransformControls object={dragTarget} mode="translate" onChange={handleChange} />;
}
