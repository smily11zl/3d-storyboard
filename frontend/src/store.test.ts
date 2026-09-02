import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ShotSegment } from './types';
import { useStore } from './store';
import { startExportMp4, fetchExportStatus, exportBlendToDirectory } from './lib/exportApi';

vi.mock('./lib/exportApi', () => ({
  startExportMp4: vi.fn().mockResolvedValue('task123'),
  fetchExportStatus: vi.fn().mockResolvedValue({
    status: 'done',
    progress: {
      completed_files: 2,
      total_files: 2,
      current_file: null,
      current_frame: 0,
      current_total_frames: 0,
    },
    files: [],
    error: null,
  }),
  exportBlendToDirectory: vi.fn().mockResolvedValue(['b.blend']),
}));

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

function findSegment(name: string): ShotSegment {
  const seg = useStore.getState().editingSegments!.find((s) => s.segment_name === name);
  if (!seg) throw new Error(`segment ${name} not found`);
  return seg;
}

describe('段拖动 store action', () => {
  beforeEach(() => {
    useStore.setState({
      editingSegments: [
        makeSegment('cam_01', 'seg_01', 0, 5),
        makeSegment('cam_01', 'seg_02', 5, 8),
      ],
      framesPerSecond: 24,
      dirty: false,
    });
  });

  it('shiftSegment：整体平移 +delta，时长不变', () => {
    useStore.getState().shiftSegment('cam_01', 'seg_02', 1);
    const seg = findSegment('seg_02');
    expect(seg.start_time).toBe(6);
    expect(seg.end_time).toBe(9);
    expect(useStore.getState().dirty).toBe(true);
  });

  it('shiftSegment：起点不越过前一段终点', () => {
    useStore.getState().shiftSegment('cam_01', 'seg_02', -1);
    const seg = findSegment('seg_02');
    expect(seg.start_time).toBe(5);
    expect(seg.end_time).toBe(8);
  });

  it('retimeSegment：拖终点加长超过原始时长时保持终点、起点回退', () => {
    useStore.setState({
      editingSegments: [makeSegment('cam_01', 'seg_01', 0, 6)],
    });
    useStore.getState().retimeSegment('cam_01', 'seg_01', 'end', 10);
    const seg = findSegment('seg_01');
    expect(seg.start_time).toBe(4);
    expect(seg.end_time).toBe(10);
  });

  it('trimSegment：C 段拖终点只改时间段，keyframes 完整保留（非破坏性）', () => {
    const keyframes = [0, 1, 2, 3, 4, 5, 6].map((t) => ({ time: t, position: [t, 0, 0] as [number, number, number] }));
    useStore.setState({
      editingSegments: [
        makeSegment('cam_01', 'seg_01', 0, 6, {
          segment_type: 'C',
          position_keyframes: keyframes,
          rotation_keyframes: [],
        }),
      ],
    });
    useStore.getState().trimSegment('cam_01', 'seg_01', 'end', 4);
    const seg = findSegment('seg_01');
    expect(seg.end_time).toBe(4);
    // 关键帧完整保留（拖回来能恢复），裁剪发生在渲染/保存时按段范围过滤
    expect(seg.position_keyframes!.map((k) => k.time)).toEqual([0, 1, 2, 3, 4, 5, 6]);
  });

  it('setSegmentOriginalDuration：改原始时长上限', () => {
    useStore.getState().setSegmentOriginalDuration('cam_01', 'seg_02', 5);
    const seg = findSegment('seg_02');
    expect(seg.original_duration).toBe(5);
  });
});

describe('相机轴增删 store action', () => {
  beforeEach(() => {
    useStore.setState({
      shot: { cameras: [{ camera_name: 'cam_01' }] } as never,
      editingSegments: [makeSegment('cam_01', 'seg_01', 0, 5)],
      editingCameras: [{ camera_name: 'cam_01' }],
      activeCameraName: 'cam_01',
      selectedSegment: null,
      framesPerSecond: 24,
      dirty: false,
    });
  });

  it('addCamera：新建 cam_0N + 初始 3s 段 + 自动选中', () => {
    useStore.getState().addCamera();
    const segments = useStore.getState().editingSegments!;
    const newSeg = segments.find((s) => s.camera_name === 'cam_02');
    expect(newSeg).toBeDefined();
    expect(newSeg!.segment_name).toBe('cam_02_seg_01');
    expect(newSeg!.start_time).toBe(0);
    expect(newSeg!.end_time).toBe(3);
    expect(newSeg!.original_duration).toBe(3);
    expect(newSeg!.orientation_mode).toBe('interpolate');
    expect(useStore.getState().activeCameraName).toBe('cam_02');
    expect(useStore.getState().selectedSegment).toEqual({
      camera_name: 'cam_02',
      segment_name: 'cam_02_seg_01',
    });
  });

  it('deleteCamera：删除该相机的所有段', () => {
    useStore.setState({
      editingSegments: [
        makeSegment('cam_01', 'seg_01', 0, 5),
        makeSegment('cam_02', 'seg_02', 0, 5),
      ],
    });
    useStore.getState().deleteCamera('cam_02');
    const segments = useStore.getState().editingSegments!;
    expect(segments.length).toBe(1);
    expect(segments[0].camera_name).toBe('cam_01');
  });

  it('deleteCamera：删除活跃相机后切到剩余第一个', () => {
    useStore.setState({
      editingSegments: [
        makeSegment('cam_01', 'seg_01', 0, 5),
        makeSegment('cam_02', 'seg_02', 0, 5),
      ],
      activeCameraName: 'cam_02',
      selectedSegment: { camera_name: 'cam_02', segment_name: 'seg_02' },
    });
    useStore.getState().deleteCamera('cam_02');
    expect(useStore.getState().activeCameraName).toBe('cam_01');
    expect(useStore.getState().selectedSegment).toBeNull();
  });
});

describe('V7 导出 store action', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('exportMp4 选目录后调 startExportMp4 并设置进度', async () => {
    const picker = vi.fn().mockResolvedValue({});
    vi.stubGlobal('window', { showDirectoryPicker: picker });
    vi.stubGlobal('localStorage', { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn() });
    useStore.setState({
      shot: { export_hash: 'abc' } as never,
      sessionList: [
        {
          id: 's1',
          folder_name: 'folder1',
          preview: 'my chat',
          input_tokens: 0,
          output_tokens: 0,
          estimated_cost_usd: null,
          message_count: 1,
          has_output: true,
          started_at: 0,
        },
      ],
      currentSessionId: 's1',
      blendVersions: [
        { filename: 'scene_v3.blend', version: 3, mtime: 100, blend_hash: 'h', has_script: true },
      ],
    });
    await useStore.getState().exportMp4('1080p');
    expect(picker).toHaveBeenCalled();
    expect(startExportMp4).toHaveBeenCalledWith('abc', 'folder1', 'scene_v3', '1080p');
    expect(useStore.getState().exportProgress?.taskId).toBe('task123');
  });

  it('exportBlend 选目录后调 exportBlendToDirectory（无 session 时 chatName=chat）', async () => {
    const picker = vi.fn().mockResolvedValue({});
    vi.stubGlobal('window', { showDirectoryPicker: picker });
    useStore.setState({
      shot: { export_hash: 'abc' } as never,
      sessionList: [],
      currentSessionId: null,
      blendVersions: [],
    });
    await useStore.getState().exportBlend();
    expect(exportBlendToDirectory).toHaveBeenCalledWith('abc', '', expect.anything());
  });
});
