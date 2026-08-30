import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store';
import type { ShotSegment } from '../types';
import { PX_PER_SECOND, TIMELINE_TOTAL, effectiveEnd, hitZone, segmentPixels } from '../lib/timeline';
import styles from './EditTimeline.module.css';

interface ContextMenuState {
  camera_name: string;
  segment_name: string;
  x: number;
  y: number;
}

/** 标签列宽度（box-sizing:border-box）：眼睛(20) + 相机名(110) + 加段按钮(20+4) + 删相机按钮(20+4)。 */
const LABEL_WIDTH = 178;

/** 编辑态底部时间轴：左侧播放控制 + 时间刻度 + 段轨道 + 播放头（竖线 + 三角形）。 */
export function EditTimeline() {
  const shot = useStore((state) => state.shot);
  const currentTime = useStore((state) => state.currentTime);
  const setCurrentTime = useStore((state) => state.setCurrentTime);
  const selectedSegment = useStore((state) => state.selectedSegment);
  const setSelectedSegment = useStore((state) => state.setSelectedSegment);
  const addSegment = useStore((state) => state.addSegment);
  const deleteSegment = useStore((state) => state.deleteSegment);
  const shiftSegment = useStore((state) => state.shiftSegment);
  const retimeSegment = useStore((state) => state.retimeSegment);
  const trimSegment = useStore((state) => state.trimSegment);
  const addCamera = useStore((state) => state.addCamera);
  const deleteCamera = useStore((state) => state.deleteCamera);
  const isPlaying = useStore((state) => state.isPlaying);
  const setPlaying = useStore((state) => state.setPlaying);
  const activeCameraName = useStore((state) => state.activeCameraName);
  const setActiveCamera = useStore((state) => state.setActiveCamera);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const rulerReference = useRef<HTMLDivElement | null>(null);
  const editingSegments = useStore((state) => state.editingSegments);
  const editingCameras = useStore((state) => state.editingCameras);
  const segments = editingSegments ?? shot?.segments ?? [];
  // 时间轴固定 10 分钟总长度，段按比例排布
  const duration = TIMELINE_TOTAL;
  // 有效总时长 = 所有段的最大 end_time
  const effective = effectiveEnd(segments);
  const cameras = editingCameras ?? shot?.cameras ?? [];

  // 无段相机不补虚拟整段：删除完所有段后时间轴为空，用户可通过「+」按钮重新加段。
  const allSegments = segments;

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

  if (duration <= 0) return null;

  const playheadLeft = LABEL_WIDTH + currentTime * PX_PER_SECOND;

  // 播放头拖动/点击：在时间刻度轴上操作（拖动三角形 + 点击刻度轴）
  const handleTimelineMouseDown = (event: React.MouseEvent<HTMLDivElement>) => {
    const ruler = rulerReference.current;
    if (!ruler) return;
    event.preventDefault();
    setPlaying(false);
    const rect = ruler.getBoundingClientRect();
    const updateTime = (clientX: number) => {
      const target = Math.max(0, Math.min(duration, (clientX - rect.left) / PX_PER_SECOND));
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

  // 段拖动：中段整体平移（shift）、两端边缘改时长（S 段 re-time / C 段 trim）
  const handleSegmentMouseDown = (event: React.MouseEvent<HTMLDivElement>, segment: ShotSegment) => {
    event.preventDefault();
    event.stopPropagation();
    const rect = event.currentTarget.getBoundingClientRect();
    const zone = hitZone(event.clientX - rect.left, rect.width);
    let lastClientX = event.clientX;
    const cameraName = segment.camera_name;
    const segmentName = segment.segment_name;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const deltaPx = moveEvent.clientX - lastClientX;
      lastClientX = moveEvent.clientX;
      const deltaSec = deltaPx / PX_PER_SECOND;
      if (zone === 'shift') {
        shiftSegment(cameraName, segmentName, deltaSec);
        return;
      }
      const editing = useStore.getState().editingSegments;
      const current = editing?.find(
        (candidate) =>
          candidate.camera_name === cameraName && candidate.segment_name === segmentName,
      );
      if (!current) return;
      const newTime =
        zone === 'start' ? current.start_time + deltaSec : current.end_time + deltaSec;
      const action = current.segment_type === 'C' ? trimSegment : retimeSegment;
      action(cameraName, segmentName, zone, newTime);
    };
    const handleMouseUp = () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  // 时间刻度（每 1 秒一个，最多约 10 个）
  const ticks = Array.from({ length: Math.floor(duration) + 1 }, (_, index) => index);

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
        <div
          className={styles.timelineContent}
          style={{ width: `${LABEL_WIDTH + TIMELINE_TOTAL * PX_PER_SECOND}px` }}
        >
        <div
          className={styles.effectiveHighlight}
          style={{ left: `${LABEL_WIDTH}px`, width: `${effective * PX_PER_SECOND}px` }}
        />
        <div
          className={styles.effectiveMark}
          style={{ left: `${LABEL_WIDTH + effective * PX_PER_SECOND}px` }}
          title={`Effective total duration ${effective.toFixed(2)}s`}
        />
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
              <button
                className={styles.deleteCameraButton}
                onClick={() => {
                  if (window.confirm(`Delete camera "${camera.camera_name}" and all its segments?`)) {
                    deleteCamera(camera.camera_name);
                  }
                }}
                title={`Delete camera ${camera.camera_name}`}
                aria-label={`Delete camera ${camera.camera_name}`}
              >
                ✕
              </button>
              <div
                className={styles.trackLane}
                style={{ width: `${TIMELINE_TOTAL * PX_PER_SECOND}px` }}
              >
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
                          left: `${segmentPixels(segment.start_time, segment.end_time).leftPx}px`,
                          width: `${segmentPixels(segment.start_time, segment.end_time).widthPx}px`,
                        }}
                        title={`${segment.segment_name} · ${
                          segment.segment_type === 'S' ? 'Simple' : 'Complex'
                        }`}
                        onMouseDown={(event) => handleSegmentMouseDown(event, segment)}
                        onClick={() => handleSegmentClick(segment.camera_name, segment.segment_name)}
                        onContextMenu={(event) =>
                          handleSegmentContextMenu(event, segment.camera_name, segment.segment_name)
                        }
                      >
                        <div className={`${styles.segmentHandle} ${styles.segmentHandleLeft}`} />
                        <div className={`${styles.segmentHandle} ${styles.segmentHandleRight}`} />
                        {segment.segment_name}
                      </div>
                    );
                  })}
              </div>
            </div>
          ))}
          <button
            className={styles.addCameraButton}
            onClick={addCamera}
            title="Add camera"
            aria-label="Add camera"
          >
            + Camera
          </button>
        </div>
        <div className={styles.timeScale}>
          <div className={styles.timeScaleSpacer} />
          <div
            className={styles.timeScaleRuler}
            ref={rulerReference}
            onMouseDown={handleTimelineMouseDown}
            style={{ width: `${TIMELINE_TOTAL * PX_PER_SECOND}px` }}
          >
            {ticks.map((tick) => (
              <span
                key={tick}
                className={styles.tickLabel}
                style={{ left: `${tick * PX_PER_SECOND}px` }}
              >
                {tick}s
              </span>
            ))}
          </div>
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
