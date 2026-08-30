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

export interface PositionKeyframe {
  time: number;
  position: [number, number, number];
}

export interface RotationKeyframe {
  time: number;
  rotation: [number, number, number];
}

export interface BlendVersion {
  filename: string;
  version: number;
  mtime: number;
  blend_hash: string;
  /** 有对应 script_vN.py = AI 生成；无 = 直接改 blend。 */
  has_script: boolean;
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

export interface SegmentInterpolation {
  position: string;
  rotation: string;
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
  interpolation?: SegmentInterpolation;
  /** 编辑态的朝向模式（interpolate=角度 / follow=目标点）。 */
  orientation_mode?: "interpolate" | "follow";
  /** follow 段的 TRACK_TO 目标点位置（glTF Y-up），每段独立；interpolate 段无。 */
  target_position?: [number, number, number];
  /** 原始时长（秒）：进入编辑态那刻的 end_time - start_time，拖动时长的上限。S 段可改，C 段只读。 */
  original_duration?: number;
  /** C 段：完整采样点（保存时逐帧复刻用）。 */
  position_keyframes?: PositionKeyframe[];
  rotation_keyframes?: RotationKeyframe[];
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
