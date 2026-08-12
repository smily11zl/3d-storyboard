import { useStore } from '../store';
import styles from './TopBar.module.css';

interface TopBarProperties {
  onOpenSettings: () => void;
}

/** V2 top bar: product name, sidebar toggle, settings entry. */
export function TopBar({ onOpenSettings }: TopBarProperties) {
  const sidebarCollapsed = useStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useStore((state) => state.toggleSidebar);

  return (
    <header className={styles.topBar}>
      <div className={styles.leftGroup}>
        <button
          className={styles.iconButton}
          onClick={toggleSidebar}
          title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
          aria-label="切换侧边栏"
        >
          <span className={styles.hamburger}>☰</span>
        </button>
        <span className={styles.productName}>Storyboard 3D</span>
      </div>
      <div className={styles.rightGroup}>
        <button
          className={styles.iconButton}
          onClick={onOpenSettings}
          title="API 设置"
          aria-label="打开设置"
        >
          <span className={styles.gearIcon}>⚙</span>
        </button>
      </div>
    </header>
  );
}
