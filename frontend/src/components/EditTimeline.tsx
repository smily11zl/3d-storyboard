import { useEffect, useMemo, useRef, useState } from 'react';
import { useStore } from '../store';
import type { ShotSegment } from '../types';
import styles from './EditTimeline.module.css';

interface ContextMenuState {
  camera_name: string;
  segment_name: string;
  x: number;
  y: number;
}

/** 标签列宽度：眼睛(20) + 相机名(110) + 加段按钮(20+4)。 */
const LABEL_WIDTH = 154;

/** 编辑态底部时间轴：左侧播放控制 + 时间刻度 + 段轨道 + 播放头（竖线 + 三角形）。 */
export function EditTimeline() {
  const shot = useStore((state) => state.shot);
  const currentTime = useStore((state) => state.currentTime);
  const setCurrentTime = useStore((state) => state.setCurrentTime);
  const selectedSegment = useStore((state) => state.selectedSegment);
  const setSelectedSegment = useStore((state) => state.setSelectedSegment);
  const addSegment = useStore((state) => state.addSegment);
  const deleteSegment = useStore((state) => state.deleteSegment);
  const isPlaying = useStore((state) => state.isPlaying);
  const setPlaying = useStore((state) => state.setPlaying);
  const activeCameraName = useStore((state) => state.activeCameraName);
  const setActiveCamera = useStore((state) => state.setActiveCamera);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const rulerReference = useRef<HTMLDivElement | null>(null);
  const [rulerWidth, setRulerWidth] = useState(0);
  const editingSegments = useStore((state) => state.editingSegments);
  const segments = editingSegments ?? shot?.segments ?? [];
  const duration =
    editingSegments && editingSegments.length > 0
      ? Math.max(shot?.duration_seconds ?? 0, ...editingSegments.map((s) => s.end_time))
      : (shot?.duration_seconds ?? 0);
  const cameras = shot?.cameras ?? [];

  // 无段相机补虚拟整段（与 SegmentList 一致）
  const allSegments = useMemo(() => {
    const result: ShotSegment[] = [...segments];
    const segmentedCameraNames = new Set(segments.map((segment) => segment.camera_name));
    for (const camera of cameras) {
      if (segmentedCameraNames.has(camera.camera_name)) continue;
      result.push({
        camera_name: camera.camera_name,
        segment_name: `${camera.camera_name}_full`,
        start_time: 0,
        end_time: duration,
        start_pose: { position: [0, 0, 0], rotation: [0, 0, 0] },
        end_pose: { position: [0, 0, 0], rotation: [0, 0, 0] },
        segment_type: 'S',
      });
    }
    return result;
  }, [segments, cameras, duration]);

  // 右键菜单：点击任意处关闭
  useEffect(() => {
    if (!contextMenu) return;
    const close = () => setContextMenu(null);
    window.addEventListener('mousedown', close);
    return () => window.removeEventListener('mousedown', close);
  }, [contextMenu]);

  // 空格键：播放 / 暂停（编辑态，对标剪辑器）
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.code !== 'Space') return;
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
      ) {
        return;
      }
      event.preventDefault();
      const { isPlaying, setPlaying } = useStore.getState();
      setPlaying(!isPlaying);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // 测量刻度区宽度（播放头 left 用像素计算，避免 CSS calc 百分比乘数字的兼容问题）
  useEffect(() => {
    const measure = () => {
      if (rulerReference.current) {
        const rect = rulerReference.current.getBoundingClientRect();
        setRulerWidth(rect.width);
      }
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [duration]);

  if (duration <= 0) return null;

  const playheadPercent = (currentTime / duration) * 100;
  const playheadLeft = LABEL_WIDTH + (rulerWidth * playheadPercent) / 100;

  // 播放头拖动/点击：在时间刻度轴上操作（拖动三角形 + 点击刻度轴）
  const handleTimelineMouseDown = (event: React.MouseEvent<HTMLDivElement>) => {
    const ruler = rulerReference.current;
    if (!ruler) return;
    setPlaying(false);
    const rect = ruler.getBoundingClientRect();
    const updateTime = (clientX: number) => {
      const ratio = (clientX - rect.left) / rect.width;
      const target = Math.max(0, Math.min(duration, ratio * duration));
      setCurrentTime(target);
    };
    updateTime(event.clientX);
    const handleMouseMove = (moveEvent: MouseEvent) => updateTime(moveEvent.clientX);
    const handleMouseUp = () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  const handleSegmentClick = (camera_name: string, segment_name: string) => {
    setSelectedSegment({ camera_name, segment_name });
  };

  const handleSegmentContextMenu = (
    event: React.MouseEvent,
    camera_name: string,
    segment_name: string,
  ) => {
    event.preventDefault();
    event.stopPropagation();
    setContextMenu({ camera_name, segment_name, x: event.clientX, y: event.clientY });
  };

  // 时间刻度（每 1 秒一个，最多约 10 个）
  const tickCount = Math.min(10, Math.max(2, Math.floor(duration)));
  const ticks = Array.from({ length: tickCount + 1 }, (_, index) => (index / tickCount) * duration);

  return (
    <div className={styles.container}>
      <div className={styles.leftControls}>
        <button
          className={styles.playButton}
          onClick={() => setPlaying(!isPlaying)}
          title={isPlaying ? 'Pause' : 'Play'}
          aria-label={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? '⏸' : '▶'}
        </button>
      </div>
      <div className={styles.timelineBody}>
        <div className={styles.playhead} style={{ left: `${playheadLeft}px` }}>
          <div className={styles.playheadLine} />
          <div
            className={styles.playheadTriangle}
            onMouseDown={(event) => {
              event.stopPropagation();
              handleTimelineMouseDown(event);
            }}
            title="Drag to move playhead"
          />
        </div>
        <div className={styles.trackArea}>
          {cameras.map((camera) => (
            <div key={camera.camera_name} className={styles.track}>
              <button
                className={`${styles.eyeButton} ${
                  activeCameraName === camera.camera_name ? styles.eyeActive : ''
                }`}
                onClick={() => setActiveCamera(camera.camera_name)}
                title={`Show ${camera.camera_name} in Camera View`}
                aria-label={`Show ${camera.camera_name} in Camera View`}
              >
                👁
              </button>
              <span className={styles.trackLabel}>{camera.camera_name}</span>
              <button
                className={styles.addButton}
                onClick={() => addSegment(camera.camera_name)}
                title={`Add segment to ${camera.camera_name}`}
              >
                +
              </button>
              <div className={styles.trackLane}>
                {allSegments
                  .filter((segment) => segment.camera_name === camera.camera_name)
                  .map((segment) => {
                    const isSelected =
                      selectedSegment?.camera_name === segment.camera_name &&
                      selectedSegment?.segment_name === segment.segment_name;
                    return (
                      <div
                        key={`${segment.camera_name}-${segment.segment_name}`}
                        className={`${styles.segmentBlock} ${
                          segment.segment_type === 'S' ? styles.segmentSimple : styles.segmentComplex
                        } ${isSelected ? styles.segmentSelected : ''}`}
                        style={{
                          left: `${(segment.start_time / duration) * 100}%`,
                          width: `${((segment.end_time - segment.start_time) / duration) * 100}%`,
                        }}
                        title={`${segment.segment_name} · ${
                          segment.segment_type === 'S' ? 'Simple' : 'Complex'
                        }`}
                        onMouseDown={(event) => event.stopPropagation()}
                        onClick={() => handleSegmentClick(segment.camera_name, segment.segment_name)}
                        onContextMenu={(event) =>
                          handleSegmentContextMenu(event, segment.camera_name, segment.segment_name)
                        }
                      >
                        {segment.segment_name}
                      </div>
                    );
                  })}
              </div>
            </div>
          ))}
        </div>
        <div className={styles.timeScale}>
          <div className={styles.timeScaleSpacer} />
          <div
            className={styles.timeScaleRuler}
            ref={rulerReference}
            onMouseDown={handleTimelineMouseDown}
          >
            {ticks.map((tick) => (
              <span
                key={tick}
                className={styles.tickLabel}
                style={{ left: `${(tick / duration) * 100}%` }}
              >
                {tick.toFixed(1)}s
              </span>
            ))}
          </div>
        </div>
      </div>
      {contextMenu && (
        <div
          className={styles.contextMenu}
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onMouseDown={(event) => event.stopPropagation()}
        >
          <button
            className={styles.contextMenuItem}
            onMouseDown={(event) => {
              event.stopPropagation();
              setSelectedSegment({
                camera_name: contextMenu.camera_name,
                segment_name: contextMenu.segment_name,
              });
              setContextMenu(null);
            }}
          >
            Edit
          </button>
          <button
            className={styles.contextMenuItem}
            onMouseDown={(event) => {
              event.stopPropagation();
              if (window.confirm(`Delete segment "${contextMenu.segment_name}"?`)) {
                deleteSegment(contextMenu.camera_name, contextMenu.segment_name);
              }
              setContextMenu(null);
            }}
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}
