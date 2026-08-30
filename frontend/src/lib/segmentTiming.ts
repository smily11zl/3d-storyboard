import type { ShotSegment } from '../types';

/** 段拖动的模式：shift=整体平移、start=拖起点、end=拖终点。 */
export type DragMode = 'shift' | 'start' | 'end';

export interface ClampedTimes {
  start_time: number;
  end_time: number;
}

/**
 * 约束段的 [start_time, end_time]，满足：
 * 1. 起点 ≥ 0；2. 起点 ≥ 前一段终点；3. 终点 ≤ 后一段起点；
 * 4. 时长 ≤ original_duration（上限，保持拖动端、另一端回退）；
 * 5. 时长 ≥ 1/fps（下限，保持拖动端、另一端前移）。
 *
 * newTime：mode='shift' 时为平移量（秒）；mode='start'/'end' 时为新边界值（秒）。
 */
export function clampSegmentTimes(
  segment: ShotSegment,
  allSegments: ShotSegment[],
  mode: DragMode,
  newTime: number,
  fps: number,
): ClampedTimes {
  const { start_time: origStart, end_time: origEnd } = segment;
  const original = segment.original_duration ?? (origEnd - origStart);
  const minDur = 1 / fps;

  // C 段采样范围：段的区间不能超出 keyframes 的 time 范围（否则渲染/保存无帧可采）。
  const sampleTimes = segment.position_keyframes?.map((keyframe) => keyframe.time);
  const minSample = sampleTimes && sampleTimes.length > 0 ? Math.min(...sampleTimes) : -Infinity;
  const maxSample = sampleTimes && sampleTimes.length > 0 ? Math.max(...sampleTimes) : Infinity;

  const siblings = allSegments.filter(
    (s) => s.camera_name === segment.camera_name && s.segment_name !== segment.segment_name,
  );
  const prev = siblings
    .filter((s) => s.end_time <= origStart)
    .sort((a, b) => b.end_time - a.end_time)[0];
  const next = siblings
    .filter((s) => s.start_time >= origEnd)
    .sort((a, b) => a.start_time - b.start_time)[0];

  const minStart = prev ? prev.end_time : 0;
  const maxEnd = next ? next.start_time : Infinity;

  let start = origStart;
  let end = origEnd;

  if (mode === 'shift') {
    const delta = newTime;
    start = origStart + delta;
    end = origEnd + delta;
    // 平移越界则整体回拉，保持时长不变
    if (start < minStart) {
      const pull = minStart - start;
      start += pull;
      end += pull;
    }
    if (end > maxEnd) {
      const pull = end - maxEnd;
      start -= pull;
      end -= pull;
    }
  } else if (mode === 'end') {
    // 拖终点：终点是拖动端，保持终点、起点回退/前移
    end = Math.min(newTime, maxEnd, maxSample);
    start = Math.max(origStart, end - original, minSample);
    start = Math.max(start, minStart);
    end = Math.max(end, start + minDur);
    end = Math.min(end, maxEnd, maxSample);
  } else {
    // 拖起点：起点是拖动端，保持起点、终点回退/前移
    start = Math.max(newTime, minStart, minSample);
    end = Math.min(origEnd, start + original, maxSample);
    end = Math.min(end, maxEnd);
    start = Math.min(start, end - minDur);
    start = Math.max(start, minStart, minSample);
  }

  return { start_time: start, end_time: end };
}
