export function base64ToBytes(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes.buffer;
}

export interface ExportFile {
  filename: string;
  contentBase64: string;
}

export async function writeFilesToDirectory(
  directoryHandle: FileSystemDirectoryHandle,
  files: ExportFile[],
  subfolderName?: string,
): Promise<string[]> {
  let target = directoryHandle;
  if (subfolderName) {
    target = await directoryHandle.getDirectoryHandle(subfolderName, { create: true });
  }
  const written: string[] = [];
  for (const file of files) {
    const fileHandle = await target.getFileHandle(file.filename, { create: true });
    const writable = await fileHandle.createWritable();
    await writable.write(base64ToBytes(file.contentBase64));
    await writable.close();
    written.push(file.filename);
  }
  return written;
}
