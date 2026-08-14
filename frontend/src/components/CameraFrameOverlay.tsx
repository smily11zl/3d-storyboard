import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store';
import styles from './CameraView.module.css';

/** Default camera frame aspect when the scene doesn't specify one (Blender's
 *  default render ratio is 16:9). */
export const DEFAULT_FRAME_ASPECT = 16 / 9;

interface FrameRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/**
 * Blender-style "active camera" passepartout overlay: a centered window shows
 * exactly what the camera sees (letterboxed to the canvas, using the scene's
 * actual frame aspect), everything outside is dimmed by a translucent grey mask.
 */
export function CameraFrameOverlay() {
  const containerReference = useRef<HTMLDivElement | null>(null);
  const [frame, setFrame] = useState<FrameRect | null>(null);
  const frameAspect = useStore((state) => state.shot?.frame_aspect) ?? DEFAULT_FRAME_ASPECT;

  useEffect(() => {
    const container = containerReference.current;
    if (!container) return;

    const update = () => {
      const bounds = container.getBoundingClientRect();
      const width = bounds.width;
      const height = bounds.height;
      if (width === 0 || height === 0) return;

      // Contain the camera frame in the canvas:
      // - wider-than-tall camera (16:9): fill the width, grey above/below
      // - taller-than-wide camera: fill the height, grey left/right
      const canvasAspect = width / height;
      let frameWidth: number;
      let frameHeight: number;
      if (canvasAspect >= frameAspect) {
        frameHeight = height;
        frameWidth = height * frameAspect;
      } else {
        frameWidth = width;
        frameHeight = width / frameAspect;
      }

      setFrame({
        x: (width - frameWidth) / 2,
        y: (height - frameHeight) / 2,
        w: frameWidth,
        h: frameHeight,
      });
    };

    update();
    const observer = new ResizeObserver(update);
    observer.observe(container);
    return () => observer.disconnect();
  }, [frameAspect]);

  if (!frame) {
    // Always render the container so the ref attaches; masks mount once the
    // first measurement lands.
    return <div ref={containerReference} className={styles.frameOverlay} />;
  }

  return (
    <div ref={containerReference} className={styles.frameOverlay}>
      {/* Dimmed areas outside the camera frame */}
      <div className={styles.frameMask} style={{ left: 0, top: 0, width: '100%', height: frame.y }} />
      <div
        className={styles.frameMask}
        style={{ left: 0, top: frame.y + frame.h, width: '100%', height: `calc(100% - ${frame.y + frame.h}px)` }}
      />
      <div className={styles.frameMask} style={{ left: 0, top: frame.y, width: frame.x, height: frame.h }} />
      <div
        className={styles.frameMask}
        style={{ left: frame.x + frame.w, top: frame.y, width: `calc(100% - ${frame.x + frame.w}px)`, height: frame.h }}
      />
      {/* Camera frame border */}
      <div className={styles.frameBorder} style={{ left: frame.x, top: frame.y, width: frame.w, height: frame.h }} />
    </div>
  );
}
