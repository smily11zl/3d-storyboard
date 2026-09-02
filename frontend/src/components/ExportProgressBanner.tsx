import { useState } from 'react';
import { useStore } from '../store';
import { ConfirmDialog } from './ConfirmDialog';
import styles from './ExportProgressBanner.module.css';

export function ExportProgressBanner() {
  const exportProgress = useStore((state) => state.exportProgress);
  const clearExportProgress = useStore((state) => state.clearExportProgress);
  const cancelExport = useStore((state) => state.cancelExport);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  if (!exportProgress) return null;

  const {
    status,
    completedFiles,
    totalFiles,
    currentFile,
    currentFrame,
    currentTotalFrames,
    error,
  } = exportProgress;

  if (status === 'error') {
    return (
      <div className={styles.banner}>
        <span className={styles.errorText}>Export failed: {error || 'unknown error'}</span>
        <button className={styles.dismiss} onClick={clearExportProgress} aria-label="Dismiss">
          ✕
        </button>
      </div>
    );
  }

  if (status === 'cancelled') {
    return (
      <div className={styles.banner}>
        <span className={styles.errorText}>Export cancelled</span>
        <button className={styles.dismiss} onClick={clearExportProgress} aria-label="Dismiss">
          ✕
        </button>
      </div>
    );
  }

  if (status === 'done') {
    return (
      <div className={styles.banner}>
        <span className={styles.doneText}>Export complete</span>
        <button className={styles.dismiss} onClick={clearExportProgress} aria-label="Dismiss">
          ✕
        </button>
      </div>
    );
  }

  const fileProgress = totalFiles > 0 ? `${completedFiles}/${totalFiles}` : '';
  const currentLabel =
    status === 'composing'
      ? currentFile
        ? `Composing ${currentFile}`
        : 'Composing…'
      : currentFile
        ? `Rendering ${currentFile}`
        : 'Preparing…';
  const frameProgress =
    status !== 'composing' && currentTotalFrames > 0
      ? `${currentFrame}/${currentTotalFrames} frames`
      : '';

  return (
    <>
      <div className={styles.banner}>
        <span className={styles.title}>Exporting {fileProgress}</span>
        <span className={styles.detail}>{currentLabel}</span>
        {frameProgress && <span className={styles.detail}>{frameProgress}</span>}
        <button
          className={styles.dismiss}
          onClick={() => setShowCancelConfirm(true)}
          aria-label="Stop export"
        >
          ✕
        </button>
      </div>
      {showCancelConfirm && (
        <ConfirmDialog
          title="Stop export?"
          message="The current export will be stopped. Already written files will be kept."
          confirmLabel="Stop"
          cancelLabel="Cancel"
          danger
          onConfirm={() => {
            setShowCancelConfirm(false);
            void cancelExport();
          }}
          onClose={() => setShowCancelConfirm(false)}
        />
      )}
    </>
  );
}
