import { useStore } from '../store';
import styles from './Sidebar.module.css';

/** V2 left sidebar: 直接上传 / AI 生成 mode switch.
 *  AI 生成模式下侧边栏会被 ChatPanel 替换（切片 05）。 */
export function Sidebar() {
  const sidebarMode = useStore((state) => state.sidebarMode);
  const setSidebarMode = useStore((state) => state.setSidebarMode);

  return (
    <aside className={styles.sidebar}>
      <nav className={styles.nav}>
        <button
          className={sidebarMode === 'upload' ? `${styles.navItem} ${styles.active}` : styles.navItem}
          onClick={() => setSidebarMode('upload')}
        >
          直接上传
        </button>
        <button
          className={
            sidebarMode === 'generate' ? `${styles.navItem} ${styles.active}` : styles.navItem
          }
          onClick={() => setSidebarMode('generate')}
        >
          AI 生成
        </button>
      </nav>
    </aside>
  );
}
