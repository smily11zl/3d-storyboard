import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  exportBlendToDirectory,
  exportMp4ToDirectory,
  startExportMp4,
  fetchExportStatus,
} from './exportApi';

function makeDirectoryHandle(): { handle: FileSystemDirectoryHandle; written: Record<string, ArrayBuffer> } {
  const written: Record<string, ArrayBuffer> = {};
  const fileHandleFactory = {
    getFileHandle: async (name: string) => ({
      createWritable: async () => ({
        write: async (data: ArrayBuffer) => {
          written[name] = data;
        },
        close: async () => {},
      }),
    }),
  };
  const handle = {
    getFileHandle: fileHandleFactory.getFileHandle,
    getDirectoryHandle: async () => fileHandleFactory,
  } as unknown as FileSystemDirectoryHandle;
  return { handle, written };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('exportBlendToDirectory', () => {
  it('POST /export-blend 并把返回的 blend 写入目录句柄', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ filename: '聊天_scene.blend', content_base64: btoa('blend bytes') }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const { handle, written } = makeDirectoryHandle();

    const result = await exportBlendToDirectory('abc123', '聊天', handle);

    expect(result).toEqual(['聊天_scene.blend']);
    expect(new TextDecoder().decode(written['聊天_scene.blend'])).toBe('blend bytes');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/shots/abc123/export-blend',
      expect.objectContaining({ method: 'POST' }),
    );
  });
});

describe('exportMp4ToDirectory', () => {
  it('POST /export-mp4 并把返回的文件列表写入目录句柄', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        files: [
          { filename: 'cam_01_full.mp4', content_base64: btoa('full') },
          { filename: 'cam_01_seg_01.mp4', content_base64: btoa('seg') },
        ],
      }),
    });
    vi.stubGlobal('fetch', fetchMock);
    const { handle, written } = makeDirectoryHandle();

    const result = await exportMp4ToDirectory('abc123', '聊天', 'scene', '1080p', handle);

    expect(result).toEqual(['cam_01_full.mp4', 'cam_01_seg_01.mp4']);
    expect(new TextDecoder().decode(written['cam_01_full.mp4'])).toBe('full');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/shots/abc123/export-mp4',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('startExportMp4 POST 后返回 task_id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ task_id: 'task123' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const taskId = await startExportMp4('abc123', '聊天', 'scene', '1080p');

    expect(taskId).toBe('task123');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/shots/abc123/export-mp4',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('fetchExportStatus GET 返回进度', async () => {
    const status = {
      status: 'rendering',
      progress: {
        completed_files: 1,
        total_files: 2,
        current_file: 'a.mp4',
        current_frame: 5,
        current_total_frames: 10,
      },
      files: [],
      error: null,
    };
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => status });
    vi.stubGlobal('fetch', fetchMock);

    const result = await fetchExportStatus('task123');

    expect(result.status).toBe('rendering');
    expect(result.progress.completed_files).toBe(1);
    expect(result.progress.current_file).toBe('a.mp4');
  });
});
