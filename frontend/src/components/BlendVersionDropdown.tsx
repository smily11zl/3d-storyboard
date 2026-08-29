import { useEffect, useRef, useState } from 'react';
import type { BlendVersion } from '../types';
import styles from './BlendVersionDropdown.module.css';

interface BlendVersionDropdownProperties {
  blendVersions: BlendVersion[];
  currentHash: string;
  onSelect: (blendHash: string) => void;
}

/** Blend version selector — same visual style as HistoryDropdown (chat switcher). */
export function BlendVersionDropdown({
  blendVersions,
  currentHash,
  onSelect,
}: BlendVersionDropdownProperties) {
  const [open, setOpen] = useState(false);
  const containerReference = useRef<HTMLDivElement | null>(null);

  const current = blendVersions.find((blend) => blend.blend_hash === currentHash);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (containerReference.current && !containerReference.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  return (
    <div ref={containerReference} className={styles.container}>
      <button
        className={styles.trigger}
        onClick={() => setOpen((value) => !value)}
        title="Switch blend version"
      >
        <span className={styles.currentLabel}>
          {current ? current.filename : 'Select version'}
        </span>
        <span className={styles.caret}>▾</span>
      </button>

      {open && (
        <div className={styles.menu}>
          {blendVersions.map((blend) => (
            <div
              key={blend.blend_hash}
              className={`${styles.item} ${blend.blend_hash === currentHash ? styles.itemActive : ''}`}
              onClick={() => {
                onSelect(blend.blend_hash);
                setOpen(false);
              }}
            >
              <span className={styles.filename}>{blend.filename}</span>
              <span className={styles.sourceTag}>
                {blend.has_script ? 'AI generated' : 'Blend modified'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
