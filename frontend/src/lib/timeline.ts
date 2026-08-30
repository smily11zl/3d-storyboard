import type { ShotSegment } from '../types';

/** 时间轴固定总长度（秒）：10 分钟。 */
export const TIMELINE_TOTAL = 600;

/** 时间轴像素比例：1 秒 = 90px。段保持可操作宽度，总宽 600×90=54000px 超出屏幕，横向滚动。 */
export const PX_PER_SECOND = 90;

/** 有效总时长：所有段的最大 end_time（秒）。 */
export function effectiveEnd(segments: ShotSegment[]): number {
  return segments.reduce((max, s) => Math.max(max, s.end_time), 0);
}

/** 段在时间轴上的 left / width 像素（按固定像素比例，非百分比）。 */
export function segmentPixels(start: number, end: number): { leftPx: number; widthPx: number } {
  return {
    leftPx: start * PX_PER_SECOND,
    widthPx: (end - start) * PX_PER_SECOND,
  };
}

/** 段 block 内命中区：start=左边缘、end=右边缘、shift=中段。 */
export type HitZone = 'start' | 'end' | 'shift';

const EDGE_PX = 8;

export function hitZone(offsetX: number, width: number): HitZone {
  if (offsetX < EDGE_PX) return 'start';
  if (offsetX > width - EDGE_PX) return 'end';
  return 'shift';
}
