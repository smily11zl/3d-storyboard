import { describe, expect, it } from 'vitest';
import type { ShotSegment } from '../types';
import { clampSegmentTimes } from './segmentTiming';

const FPS = 24;
const FRAME = 1 / FPS; // ≈ 0.041667

function makeSegment(
  camera: string,
  name: string,
  start: number,
  end: number,
  overrides: Partial<ShotSegment> = {},
): ShotSegment {
  return {
    camera_name: camera,
    segment_name: name,
    start_time: start,
    end_time: end,
    start_pose: { position: [0, 0, 0], rotation: [0, 0, 0] },
    end_pose: { position: [0, 0, 0], rotation: [0, 0, 0] },
    segment_type: 'S',
    original_duration: end - start,
    ...overrides,
  };
}

describe('clampSegmentTimes', () => {
  it('shift 平移：整体 +delta，时长不变', () => {
    const seg = makeSegment('cam_01', 'seg_02', 5, 8);
    const all = [
      makeSegment('cam_01', 'seg_01', 0, 5),
      seg,
    ];
    const result = clampSegmentTimes(seg, all, 'shift', 1, FPS);
    expect(result).toEqual({ start_time: 6, end_time: 9 });
  });

  it('shift 平移：起点不越过前一段终点', () => {
    const seg = makeSegment('cam_01', 'seg_02', 5, 8);
    const all = [
      makeSegment('cam_01', 'seg_01', 0, 5),
      seg,
    ];
    const result = clampSegmentTimes(seg, all, 'shift', -1, FPS);
    expect(result).toEqual({ start_time: 5, end_time: 8 });
  });

  it('retime 拖起点：缩短且不越过前一段', () => {
    const seg = makeSegment('cam_01', 'seg_02', 5, 8);
    const all = [
      makeSegment('cam_01', 'seg_01', 0, 5),
      seg,
    ];
    const result = clampSegmentTimes(seg, all, 'start', 6, FPS);
    expect(result).toEqual({ start_time: 6, end_time: 8 });
  });

  it('retime 拖终点：加长超过原始时长时保持终点、起点回退', () => {
    const seg = makeSegment('cam_01', 'seg_01', 0, 6);
    const all = [seg];
    const result = clampSegmentTimes(seg, all, 'end', 10, FPS);
    expect(result).toEqual({ start_time: 4, end_time: 10 });
  });

  it('retime 拖终点：缩短到 1 帧下限', () => {
    const seg = makeSegment('cam_01', 'seg_01', 0, 6);
    const all = [seg];
    const result = clampSegmentTimes(seg, all, 'end', 0.01, FPS);
    expect(result).toEqual({ start_time: 0, end_time: 0 + FRAME });
  });

  it('retime 拖终点：不越过下一段起点', () => {
    const seg = makeSegment('cam_01', 'seg_01', 0, 6);
    const all = [
      seg,
      makeSegment('cam_01', 'seg_02', 6, 9),
    ];
    const result = clampSegmentTimes(seg, all, 'end', 8, FPS);
    expect(result).toEqual({ start_time: 0, end_time: 6 });
  });

  it('C 段 trim 拖终点：不超出采样范围（拖长被 clamp 到 maxSample）', () => {
    const keyframes = [0, 1, 2, 3, 4, 5].map((t) => ({ time: t, position: [t, 0, 0] as [number, number, number] }));
    const seg = makeSegment('cam_01', 'seg_01', 0, 5, {
      segment_type: 'C',
      position_keyframes: keyframes,
    });
    const result = clampSegmentTimes(seg, [seg], 'end', 10, FPS);
    expect(result).toEqual({ start_time: 0, end_time: 5 });
  });

  it('C 段 trim 拖起点：不超出采样范围（拖过末尾被 clamp 到 maxSample，受 1 帧下限）', () => {
    const keyframes = [0, 1, 2, 3, 4, 5].map((t) => ({ time: t, position: [t, 0, 0] as [number, number, number] }));
    const seg = makeSegment('cam_01', 'seg_01', 0, 5, {
      segment_type: 'C',
      position_keyframes: keyframes,
    });
    const result = clampSegmentTimes(seg, [seg], 'start', 6, FPS);
    expect(result.end_time).toBe(5);
    expect(result.start_time).toBeCloseTo(5 - FRAME, 5);
  });
});
