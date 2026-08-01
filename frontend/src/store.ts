import { create } from 'zustand';
import type { ShotMetadata } from './types';

interface StoreState {
  shot: ShotMetadata | null;
  isLoading: boolean;
  errorMessage: string | null;
  activeCameraName: string | null;
  isPlaying: boolean;
  currentTime: number;
  durationSeconds: number;
  framesPerSecond: number;
  animationStartTime: number;

  /** Character (armature root) transforms set by the Free View gizmo.
   *  Keyed by node name; both viewports apply them every frame so the
   *  Camera View reflects character moves made in the Free View. */
  characterTransforms: Record<
    string,
    { position: [number, number, number]; quaternion: [number, number, number, number] }
  >;
  setCharacterTransform: (
    nodeName: string,
    position: [number, number, number],
    quaternion: [number, number, number, number],
  ) => void;

  uploadFile: (file: File, force: boolean = false) => Promise<void>;
  clearError: () => void;
  setActiveCamera: (cameraName: string) => void;
  setPlaying: (playing: boolean) => void;
  setCurrentTime: (time: number) => void;
  reset: () => void;
}

export const useStore = create<StoreState>((set) => ({
  shot: null,
  isLoading: false,
  errorMessage: null,
  activeCameraName: null,
  isPlaying: false,
  currentTime: 0,
  durationSeconds: 0,
  framesPerSecond: 24,
  animationStartTime: 0,
  characterTransforms: {},

  uploadFile: async (file: File, force: boolean = false) => {
    set({ isLoading: true, errorMessage: null });

    const formData = new FormData();
    formData.append('file', file);

    const queryString = force ? '?force=true' : '';

    try {
      const response = await fetch(`/api/shots${queryString}`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Upload failed (${response.status})`);
      }

      const metadata: ShotMetadata = await response.json();
      set({
        shot: metadata,
        isLoading: false,
        errorMessage: null,
        activeCameraName: metadata.cameras.length > 0 ? metadata.cameras[0].camera_name : null,
        durationSeconds: metadata.duration_seconds,
        framesPerSecond: metadata.frames_per_second,
        currentTime: 0,
        isPlaying: false,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      set({ isLoading: false, errorMessage: message });
    }
  },

  clearError: () => set({ errorMessage: null }),
  setActiveCamera: (cameraName) => set({ activeCameraName: cameraName }),
  setPlaying: (playing) =>
    set((state) => {
      // Restart from beginning if at/after the end
      if (playing && state.currentTime >= state.durationSeconds && state.durationSeconds > 0) {
        return { isPlaying: true, currentTime: state.animationStartTime };
      }
      return { isPlaying: playing };
    }),
  setCurrentTime: (time) => set({ currentTime: time }),
  setCharacterTransform: (nodeName, position, quaternion) =>
    set((state) => ({
      characterTransforms: {
        ...state.characterTransforms,
        [nodeName]: { position, quaternion },
      },
    })),
  reset: () =>
    set({
      shot: null,
      isLoading: false,
      errorMessage: null,
      activeCameraName: null,
      isPlaying: false,
      currentTime: 0,
      characterTransforms: {},
    }),
}));
