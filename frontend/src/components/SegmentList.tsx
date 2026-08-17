import { useStore } from '../store';
import type { ShotSegment } from '../types';
import styles from './SegmentList.module.css';

function segmentLabel(segment: ShotSegment, index: number): string {
  const typeLabel = segment.segment_type === 'S' ? 'Simple' : 'Complex';
  return (
    `${segment.camera_name} · Shot ${index + 1} · ` +
    `${typeLabel} (${segment.start_time.toFixed(1)}–${segment.end_time.toFixed(1)}s)`
  );
}

/** 段切换下拉框：一个相机一个轨道，按相机 optgroup 分组。
 *  无段的相机（纯静态零动画）补一个虚拟整段（0~总时长），保持展示统一。 */
export function SegmentList() {
  const shot = useStore((state) => state.shot);
  const currentTime = useStore((state) => state.currentTime);
  const activeCameraName = useStore((state) => state.activeCameraName);
  const cameras = shot?.cameras ?? [];
  const segments = shot?.segments ?? [];
  const duration = shot?.duration_seconds ?? 0;

  // 构造完整段列表：有段用段，无段相机补一个虚拟整段（0~duration）
  const allSegments: ShotSegment[] = [...segments];
  const segmentedCameraNames = new Set(segments.map((segment) => segment.camera_name));
  for (const camera of cameras) {
    if (segmentedCameraNames.has(camera.camera_name)) continue;
    allSegments.push({
      camera_name: camera.camera_name,
      segment_name: `${camera.camera_name}_full`,
      start_time: 0,
      end_time: duration,
      start_pose: { position: [0, 0, 0], rotation: [0, 0, 0] },
      end_pose: { position: [0, 0, 0], rotation: [0, 0, 0] },
      segment_type: 'S',
    });
  }

  if (allSegments.length === 0) return null;

  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const index = Number(event.target.value);
    const segment = allSegments[index];
    if (!segment) return;
    const store = useStore.getState();
    store.setActiveCamera(segment.camera_name);
    store.setCurrentTime(segment.start_time);
  };

  // 当前播放/选中段。只在当前激活相机的段里找，避免下拉框停在另一个相机的段名上。
  const activeSegments = allSegments.filter(
    (segment) => segment.camera_name === activeCameraName,
  );
  const activeIndex = activeSegments.findIndex(
    (segment) => currentTime >= segment.start_time && currentTime < segment.end_time,
  );
  const currentSegment =
    activeIndex >= 0 ? activeSegments[activeIndex] : (activeSegments[0] ?? null);
  const selectedValue = currentSegment ? allSegments.indexOf(currentSegment) : 0;

  // 一个相机一个轨道：按 camera_name 分组 optgroup
  const groups = new Map<string, number[]>();
  allSegments.forEach((segment, index) => {
    const indices = groups.get(segment.camera_name) ?? [];
    indices.push(index);
    groups.set(segment.camera_name, indices);
  });
  return (
    <select className={styles.select} value={selectedValue} onChange={handleChange}>
      {Array.from(groups.entries()).map(([cameraName, indices]) => (
        <optgroup key={cameraName} label={cameraName}>
          {indices.map((index) => (
            <option key={index} value={index}>
              {segmentLabel(allSegments[index], index)}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
