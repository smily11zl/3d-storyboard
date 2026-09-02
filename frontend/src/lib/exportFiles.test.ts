import { describe, it, expect } from 'vitest';
import { base64ToBytes, writeFilesToDirectory } from './exportFiles';

describe('base64ToBytes', () => {
  it('decodes a base64 string to bytes', () => {
    const bytes = base64ToBytes(btoa('hello'));
    expect(new TextDecoder().decode(bytes)).toBe('hello');
  });
});

describe('writeFilesToDirectory', () => {
  it('writes each file to the directory handle and returns written names', async () => {
    const written: Record<string, Uint8Array> = {};
    const directoryHandle = {
      getFileHandle: async (name: string) => ({
        createWritable: async () => ({
          write: async (data: Uint8Array) => {
            written[name] = data;
          },
          close: async () => {},
        }),
      }),
    } as unknown as FileSystemDirectoryHandle;

    const files = [
      { filename: 'a.mp4', contentBase64: btoa('AAA') },
      { filename: 'b.mp4', contentBase64: btoa('BBB') },
    ];

    const result = await writeFilesToDirectory(directoryHandle, files);

    expect(result).toEqual(['a.mp4', 'b.mp4']);
    expect(new TextDecoder().decode(written['a.mp4'])).toBe('AAA');
    expect(new TextDecoder().decode(written['b.mp4'])).toBe('BBB');
  });

  it('传入 subfolderName 时写入子文件夹', async () => {
    const written: Record<string, ArrayBuffer> = {};
    let createdSubfolder = '';
    const directoryHandle = {
      getDirectoryHandle: async (name: string) => {
        createdSubfolder = name;
        return {
          getFileHandle: async (fileName: string) => ({
            createWritable: async () => ({
              write: async (data: ArrayBuffer) => {
                written[fileName] = data;
              },
              close: async () => {},
            }),
          }),
        };
      },
    } as unknown as FileSystemDirectoryHandle;

    const result = await writeFilesToDirectory(
      directoryHandle,
      [{ filename: 'a.mp4', contentBase64: btoa('AAA') }],
      '聊天_scene',
    );

    expect(createdSubfolder).toBe('聊天_scene');
    expect(result).toEqual(['a.mp4']);
    expect(new TextDecoder().decode(written['a.mp4'])).toBe('AAA');
  });
});
