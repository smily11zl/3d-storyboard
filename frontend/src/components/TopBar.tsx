import { useRef } from 'react';
import { useStore } from '../store';
import styles from './TopBar.module.css';

interface TopBarProperties {
  onOpenSettings: () => void;
}

/** Top bar: logo + upload button, sidebar toggle, settings entry. */
export function TopBar({ onOpenSettings }: TopBarProperties) {
  const sidebarCollapsed = useStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useStore((state) => state.toggleSidebar);
  const uploadFile = useStore((state) => state.uploadFile);
  const requestNewChat = useStore((state) => state.requestNewChat);
  const fileInputReference = useRef<HTMLInputElement | null>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (!file.name.endsWith('.blend')) {
        useStore.setState({ errorMessage: 'Only .blend files are supported' });
        return;
      }
      uploadFile(file, false);
    }
    if (fileInputReference.current) {
      fileInputReference.current.value = '';
    }
  };

  const handleUploadClick = (event: React.MouseEvent) => {
    // Hold Shift while clicking to force re-conversion (skip cache)
    if (event.shiftKey) {
      const file = fileInputReference.current?.files?.[0];
      if (file) {
        uploadFile(file, true);
        return;
      }
    }
    fileInputReference.current?.click();
  };

  return (
    <header className={styles.topBar}>
      <div className={styles.leftGroup}>
        <button
          className={styles.iconButton}
          onClick={toggleSidebar}
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label="Toggle sidebar"
        >
          ☰
        </button>
        <span className={styles.logo}>Storyboard 3D</span>
        <button
          className={styles.newChatButton}
          onClick={requestNewChat}
          title="Start a new chat"
        >
          + New chat
        </button>
        <button
          className={styles.uploadButton}
          onClick={handleUploadClick}
          title="Upload a .blend file (hold Shift to force re-conversion)"
        >
          Upload .blend
        </button>
        <input
          ref={fileInputReference}
          type="file"
          accept=".blend"
          className={styles.fileInput}
          onChange={handleFileSelect}
        />
      </div>
      <button
        className={styles.iconButton}
        onClick={onOpenSettings}
        title="API Settings"
        aria-label="Open settings"
      >
        ⚙
      </button>
    </header>
  );
}
