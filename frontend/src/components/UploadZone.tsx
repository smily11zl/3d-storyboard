import { useCallback, useRef, useState, type DragEvent } from 'react';
import { useStore } from '../store';
import styles from './UploadZone.module.css';

export function UploadZone() {
  const uploadFile = useStore((state) => state.uploadFile);
  const isLoading = useStore((state) => state.isLoading);
  const errorMessage = useStore((state) => state.errorMessage);
  const clearError = useStore((state) => state.clearError);
  const shot = useStore((state) => state.shot);
  const reset = useStore((state) => state.reset);

  const [isDragging, setIsDragging] = useState(false);
  const dragCounter = useRef(0);

  const handleFile = useCallback(
    (file: File, event?: React.MouseEvent | DragEvent) => {
      if (!file.name.endsWith('.blend')) {
        useStore.setState({
          errorMessage: 'Only .blend files are supported',
        });
        return;
      }
      const forceReload = event?.shiftKey ?? false;
      uploadFile(file, forceReload);
    },
    [uploadFile],
  );

  const onDragEnter = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    dragCounter.current += 1;
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current === 0) {
      setIsDragging(false);
    }
  }, []);

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.stopPropagation();
  }, []);

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();
      event.stopPropagation();
      setIsDragging(false);
      dragCounter.current = 0;

      const files = event.dataTransfer.files;
      if (files.length > 0) {
        handleFile(files[0], event);
      }
    },
    [handleFile],
  );

  const onFileSelect = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = event.target.files;
      if (files && files.length > 0) {
        handleFile(files[0], event);
      }
    },
    [handleFile],
  );

  // When loading or shot exists, show compact top bar
  if (isLoading || shot) {
    return (
      <div className={styles.topBar}>
        <button
          className={styles.newUploadButton}
          onClick={reset}
          title="Upload new file"
        >
          + New Upload
        </button>
        {shot && (
          <span className={styles.topBarTitle}>
            {shot.export_hash.slice(0, 12)}
          </span>
        )}
        {isLoading && <span className={styles.convertingLabel}>Converting...</span>}
        {errorMessage && (
          <span className={styles.errorLabel}>{errorMessage}</span>
        )}
      </div>
    );
  }

  return (
    <div className={styles.uploadPage}>
      <div
        className={`${styles.dropZone} ${isDragging ? styles.dropZoneActive : ''}`}
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        onDragOver={onDragOver}
        onDrop={onDrop}
        onClick={() => document.getElementById('file-input')?.click()}
      >
        <div className={styles.dropZoneIcon}>⬆</div>
        <h2 className={styles.dropZoneTitle}>Drop a .blend file here</h2>
        <p className={styles.dropZoneSubtitle}>
          or click to browse
        </p>
        <input
          id="file-input"
          type="file"
          accept=".blend"
          className={styles.fileInput}
          onChange={onFileSelect}
        />
      </div>
      {errorMessage && (
        <div className={styles.errorBanner}>
          <span>{errorMessage}</span>
          <button className={styles.dismissButton} onClick={clearError}>
            ✕
          </button>
        </div>
      )}
    </div>
  );
}
