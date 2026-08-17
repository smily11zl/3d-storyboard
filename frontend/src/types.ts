/** Shared types for the Shot Viewer application. */

export interface CameraInfo {
  camera_name: string;
}

export interface AnimationInfo {
  animation_name: string;
  animation_length_seconds: number;
}

export interface Pose {
  position: [number, number, number];
  rotation: [number, number, number];
}

export interface ConstraintEntry {
  type: string;
  target: string | null;
  track_axis?: string;
  up_axis?: string;
}

export interface SegmentConstraint {
  position?: ConstraintEntry[];
  rotation?: ConstraintEntry[];
}

export interface ShotSegment {
  camera_name: string;
  segment_name: string;
  start_time: number;
  end_time: number;
  start_pose: Pose;
  end_pose: Pose;
  segment_type: "S" | "C";
  constraint?: SegmentConstraint;
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
  /** V4: identified shot segments (from segments.json sidecar). */
  segments?: ShotSegment[];
}

export interface ShotState {
  shot: ShotMetadata | null;
  isLoading: boolean;
  errorMessage: string | null;
  activeCameraName: string | null;
  isPlaying: boolean;
  currentTime: number;
}

export interface SessionSummary {
  id: string;
  folder_name: string;
  preview: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number | null;
  message_count: number;
  has_output: boolean;
  started_at: number;
}
