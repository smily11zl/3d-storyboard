import { useStore } from '../store';
import styles from './EditToolbar.module.css';

/** 编辑态顶栏：放弃 + "Edit Mode" 标题 + Save（脏标记亮/灰）。 */
export function EditToolbar() {
  const dirty = useStore((state) => state.dirty);
  const setEditMode = useStore((state) => state.setEditMode);
  const saveEdit = useStore((state) => state.saveEdit);

  return (
    <header className={styles.editToolbar}>
      <div className={styles.leftGroup}>
        <button
          className={styles.discardButton}
          onClick={() => setEditMode(false)}
          title="Discard edits and exit edit mode"
        >
          Discard
        </button>
        <span className={styles.title}>Edit Mode</span>
      </div>
      <button
        className={`${styles.saveButton} ${dirty ? styles.saveEnabled : ''}`}
        disabled={!dirty}
        onClick={saveEdit}
        title={dirty ? 'Save edits as a new blend version' : 'No unsaved changes'}
      >
        Save
      </button>
    </header>
  );
}
