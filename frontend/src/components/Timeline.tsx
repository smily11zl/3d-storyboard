import { useEffect } from 'react';
import { useStore } from '../store';
import styles from './Timeline.module.css';

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${String(minutes).padStart(2, '0')}:${remainingSeconds.toFixed(1).padStart(4, '0')}`;
}

export function Timeline() {
  const isPlaying = useStore((state) => state.isPlaying);
  const currentTime = useStore((state) => state.currentTime);
  const durationSeconds = useStore((state) => state.durationSeconds);
  const animationStartTime = useStore((state) => state.animationStartTime);
  const setPlaying = useStore((state) => state.setPlaying);
  const setCurrentTime = useStore((state) => state.setCurrentTime);
  const shot = useStore((state) => state.shot);

  const hasAnimations = (shot?.animations.length ?? 0) > 0 && durationSeconds > 0;

  // Keyboard shortcut: Space to toggle play/pause
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.code === 'Space' && event.target === document.body) {
        event.preventDefault();
        if (hasAnimations) {
          setPlaying(!isPlaying);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isPlaying, hasAnimations, setPlaying]);

  if (!shot) return null;

  const handleScrub = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newTime = parseFloat(event.target.value);
    setCurrentTime(newTime);
  };

  return (
    <div className={styles.timelineBar}>
      <button
        className={`${styles.playButton} ${isPlaying ? styles.playButtonActive : ''}`}
        onClick={() => setPlaying(!isPlaying)}
        disabled={!hasAnimations}
        title={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? '⏸' : '▶'}
      </button>

      <span className={styles.timeLabel}>
        {formatTime(currentTime)}
      </span>

      <input
        type="range"
        className={styles.scrubBar}
        min={animationStartTime}
        max={durationSeconds || 1}
        step={0.01}
        value={currentTime}
        onChange={handleScrub}
        disabled={!hasAnimations}
      />

      <span className={styles.timeLabel}>
        {formatTime(durationSeconds)}
      </span>
    </div>
  );
}
