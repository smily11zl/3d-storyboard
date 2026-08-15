import { useEffect, useRef, useState } from 'react';
import { useStore } from '../store';
import type { SessionSummary } from '../types';
import styles from './HistoryDropdown.module.css';

interface HistoryDropdownProperties {
  onSelect: (session: SessionSummary) => void;
  onDelete: (session: SessionSummary) => void;
  onOpenFinder: (session: SessionSummary) => void;
  onNewChat: () => void;
}

/** History dropdown beside the chat title: switch / delete / open-in-Finder. */
export function HistoryDropdown({
  onSelect,
  onDelete,
  onOpenFinder,
  onNewChat,
}: HistoryDropdownProperties) {
  const sessionList = useStore((state) => state.sessionList);
  const currentSessionId = useStore((state) => state.currentSessionId);
  const [open, setOpen] = useState(false);
  const containerReference = useRef<HTMLDivElement | null>(null);

  const current = sessionList.find((session) => session.id === currentSessionId);

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
      <button className={styles.trigger} onClick={() => setOpen((value) => !value)}>
        <span className={styles.currentLabel}>
          {current ? current.folder_name : 'New chat'}
        </span>
        <span className={styles.caret}>▾</span>
      </button>

      {open && (
        <div className={styles.menu}>
          <div
            className={styles.newChatItem}
            onClick={() => {
              onNewChat();
              setOpen(false);
            }}
          >
            <span className={styles.newChatLabel}>＋ New chat</span>
          </div>
          {sessionList.length === 0 ? (
            <div className={styles.empty}>No history yet</div>
          ) : (
            sessionList.map((session) => (
              <div
                key={session.id}
                className={`${styles.item} ${session.id === currentSessionId ? styles.itemActive : ''}`}
                onClick={() => {
                  onSelect(session);
                  setOpen(false);
                }}
              >
                <div className={styles.itemMain}>
                  <span className={styles.folderName}>{session.folder_name}</span>
                  <span className={styles.preview}>{session.preview}</span>
                </div>
                <div className={styles.itemActions}>
                  {session.has_output && (
                    <button
                      className={styles.actionButton}
                      onClick={(event) => {
                        event.stopPropagation();
                        onOpenFinder(session);
                        setOpen(false);
                      }}
                      title="Open in Finder"
                    >
                      Finder
                    </button>
                  )}
                  <button
                    className={styles.actionButton}
                    onClick={(event) => {
                      event.stopPropagation();
                      onDelete(session);
                    }}
                    title="Delete this chat"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
