import { writeFilesToDirectory, type ExportFile } from './exportFiles';

function toExportFiles(items: { filename: string; content_base64: string }[]): ExportFile[] {
  return items.map((item) => ({ filename: item.filename, contentBase64: item.content_base64 }));
}

export async function exportBlendToDirectory(
  exportHash: string,
  chatName: string,
  directoryHandle: FileSystemDirectoryHandle,
): Promise<string[]> {
  const response = await fetch(`/api/shots/${exportHash}/export-blend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_name: chatName }),
  });
  if (!response.ok) {
    throw new Error('Export Blend failed');
  }
  const data = await response.json();
  return writeFilesToDirectory(directoryHandle, [
    { filename: data.filename, contentBase64: data.content_base64 },
  ]);
}

export async function exportMp4ToDirectory(
  exportHash: string,
  chatName: string,
  blendPrefix: string,
  resolution: string,
  directoryHandle: FileSystemDirectoryHandle,
): Promise<string[]> {
  const response = await fetch(`/api/shots/${exportHash}/export-mp4`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_name: chatName, blend_prefix: blendPrefix, resolution }),
  });
  if (!response.ok) {
    throw new Error('Export MP4 failed');
  }
  const data = await response.json();
  return writeFilesToDirectory(
    directoryHandle,
    toExportFiles(data.files),
    `${chatName}_${blendPrefix}`,
  );
}

export interface ExportStatus {
  status: string;
  progress: {
    completed_files: number;
    total_files: number;
    current_file: string | null;
    current_frame: number;
    current_total_frames: number;
  };
  files: { filename: string; content_base64: string }[];
  error: string | null;
}

export async function startExportMp4(
  exportHash: string,
  chatName: string,
  blendPrefix: string,
  resolution: string,
): Promise<string> {
  const response = await fetch(`/api/shots/${exportHash}/export-mp4`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_name: chatName, blend_prefix: blendPrefix, resolution }),
  });
  if (!response.ok) {
    throw new Error('Export MP4 failed');
  }
  const data = await response.json();
  return data.task_id;
}

export async function fetchExportStatus(taskId: string): Promise<ExportStatus> {
  const response = await fetch(`/api/shots/export-status/${taskId}`);
  if (!response.ok) {
    throw new Error('Fetch export status failed');
  }
  return response.json();
}
