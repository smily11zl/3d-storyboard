import { describe, expect, it } from 'vitest';
import type { ShotSegment } from '../types';
import { PX_PER_SECOND, TIMELINE_TOTAL, effectiveEnd, hitZone, segmentPixels } from './timeline';

function makeSegment(name: string, start: number, end: number): ShotSegment {
  return {
    camera_name: 'cam_01',
    segment_name: name,
    start_time: start,
    end_time: end,
    start_pose: { position: [0, 0, 0], rotation: [0, 0, 0] },
    end_pose: { position: [0, 0, 0], rotation: [0, 0, 0] },
    segment_type: 'S',
  };
}

describe('timeline 纯函数', () => {
  it('TIMELINE_TOTAL 固定 600 秒（10 分钟）', () => {
    expect(TIMELINE_TOTAL).toBe(600);
  });

  it('effectiveEnd：空段返回 0', () => {
    expect(effectiveEnd([])).toBe(0);
  });

  it('effectiveEnd：取段的最大 end_time', () => {
    expect(effectiveEnd([makeSegment('a', 0, 5), makeSegment('b', 5, 8)])).toBe(8);
  });

  it('segmentPixels：按固定像素比例（1 秒 = 90px）计算 left/width', () => {
    expect(PX_PER_SECOND).toBe(90);
    expect(segmentPixels(0, 3)).toEqual({ leftPx: 0, widthPx: 270 });
    expect(segmentPixels(5, 8)).toEqual({ leftPx: 450, widthPx: 270 });
  });

  it('hitZone：左边缘命中 start、右边缘命中 end、中段命中 shift', () => {
    expect(hitZone(4, 100)).toBe('start');
    expect(hitZone(96, 100)).toBe('end');
    expect(hitZone(50, 100)).toBe('shift');
  });
});
