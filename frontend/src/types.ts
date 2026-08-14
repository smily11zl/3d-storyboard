/** Shared types for the Shot Viewer application. */

export interface CameraInfo {
  camera_name: string;
}

export interface AnimationInfo {
  animation_name: string;
  animation_length_seconds: number;
}

export interface ShotMetadata {
  export_hash: string;
  gltf_output_url: string;
  cameras: CameraInfo[];
  animations: AnimationInfo[];
  duration_seconds: number;
  frames_per_second: number;
  /** Camera frame width/height ratio from Blender's render resolution. */
  frame_aspect?: number;
}

export interface ShotState {
  shot: ShotMetadata | null;
  isLoading: boolean;
  errorMessage: string | null;
  activeCameraName: string | null;
  isPlaying: boolean;
  currentTime: number;
}
