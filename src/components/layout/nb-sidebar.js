/**
 * ═══════════════════════════════════════════════════════════════
 * <nb-sidebar> — Application Sidebar Navigation
 * Features: collapsible, nav items, active state, glassmorphism,
 *           backend status indicator, theme toggle.
 * ═══════════════════════════════════════════════════════════════
 */
import { NbComponent, defineComponent } from '@core/component.js';
import { appStore } from '@core/store.js';
import { useRouter } from '@core/router.js';
import { eventBus, Events } from '@core/events.js';

const NAV_ITEMS = [
  { id: 'dashboard',  icon: 'layout',      label: 'Dashboard',  path: '/' },
];

class NbSidebar extends NbComponent {
  styles() {
    return `
      ${NbComponent.sharedStyles()}
      :host {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: var(--color-sidebar-bg, hsl(230, 21%, 9%));
        border-right: 1px solid var(--color-sidebar-border, hsla(0,0%,100%,0.06));
        overflow: hidden;
        transition: width var(--duration-base, 250ms) var(--ease-default, ease);
        position: relative;
      }

      /* ── Logo / Brand ─────── */
      .sidebar__brand {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px 20px;
        height: var(--header-height, 56px);
        border-bottom: 1px solid var(--color-sidebar-border, hsla(0,0%,100%,0.06));
        flex-shrink: 0;
      }

      .sidebar__logo {
        width: 28px;
        height: 28px;
        border-radius: var(--radius-sm, 6px);
        background: linear-gradient(135deg, hsl(0, 0%, 40%), hsl(0, 0%, 20%));
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .sidebar__logo nb-icon {
        color: #fff;
      }

      .sidebar__title {
        font-size: 1rem;
        font-weight: 600;
        color: var(--color-text-primary, #f2f2f2);
        letter-spacing: -0.02em;
        white-space: nowrap;
        overflow: hidden;
      }

      /* ── Navigation ─────── */
      .sidebar__nav {
        flex: 1;
        padding: 8px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 2px;
      }

      .nav-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 12px;
        border-radius: var(--radius-md, 10px);
        color: var(--color-text-secondary, #adadad);
        cursor: pointer;
        transition: all var(--duration-fast, 150ms) var(--ease-default, ease);
        white-space: nowrap;
        user-select: none;
        border: 1px solid transparent;
        font-size: 0.875rem;
        font-weight: 450;
      }

      .nav-item:hover {
        background: var(--color-sidebar-item-hover, hsla(0,0%,100%,0.05));
        color: var(--color-text-primary, #f2f2f2);
      }

      .nav-item--active {
        background: var(--color-sidebar-item-active, hsla(250, 85%, 65%, 0.12));
        color: var(--color-accent, hsl(0, 0%, 75%));
        border-color: hsla(250, 85%, 65%, 0.1);
        font-weight: 500;
      }

      .nav-item--active nb-icon {
        color: var(--color-accent, hsl(0, 0%, 75%));
      }

      .nav-item:active {
        transform: scale(0.98);
      }

      .nav-item__label {
        overflow: hidden;
        text-overflow: ellipsis;
      }

      /* ── Footer ──────────── */
      .sidebar__footer {
        padding: 12px;
        border-top: 1px solid var(--color-sidebar-border, hsla(0,0%,100%,0.06));
        display: flex;
        flex-direction: column;
        gap: 8px;
        flex-shrink: 0;
      }

      .sidebar__status {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        border-radius: var(--radius-sm, 6px);
        background: var(--color-bg-secondary, hsl(230, 18%, 14%));
        font-size: 0.75rem;
        color: var(--color-text-tertiary, #7a7a7a);
      }

      .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
      }

      .status-dot--connected {
        background: var(--color-success, hsl(142, 71%, 45%));
        box-shadow: 0 0 6px hsla(142, 71%, 45%, 0.5);
      }

      .status-dot--disconnected {
        background: var(--color-danger, hsl(0, 84%, 60%));
        box-shadow: 0 0 6px hsla(0, 84%, 60%, 0.5);
      }

      .status-dot--connecting {
        background: var(--color-warning, hsl(38, 92%, 50%));
        animation: pulse 1.5s ease-in-out infinite;
      }

      @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
      }

      .sidebar__actions {
        display: flex;
        gap: 4px;
      }

      .sidebar__action-btn {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        padding: 8px;
        border-radius: var(--radius-sm, 6px);
        color: var(--color-text-tertiary, #7a7a7a);
        cursor: pointer;
        transition: all var(--duration-fast, 150ms) var(--ease-default, ease);
        font-size: 0.75rem;
      }

      .sidebar__action-btn:hover {
        background: var(--color-sidebar-item-hover, hsla(0,0%,100%,0.05));
        color: var(--color-text-primary, #f2f2f2);
      }

      /* Separator */
      .sidebar__separator {
        flex: 1;
      }
    `;
  }

  render() {
    const currentPage = appStore.state.currentPage;
    const backendStatus = appStore.state.backendStatus;
    const theme = appStore.state.theme;

    return `
      <div class="sidebar__brand">
        <div class="sidebar__logo">
          <nb-icon name="sparkles" size="16"></nb-icon>
        </div>
        <span class="sidebar__title">NotebookLM</span>
      </div>

      <nav class="sidebar__nav">
        ${NAV_ITEMS.map(item => `
          <div
            class="nav-item ${currentPage === item.id ? 'nav-item--active' : ''}"
            data-page="${item.id}"
            data-path="${item.path}"
            role="button"
            tabindex="0"
            aria-label="${item.label}"
          >
            <nb-icon name="${item.icon}" size="18"></nb-icon>
            <span class="nav-item__label">${item.label}</span>
          </div>
        `).join('')}
      </nav>

      <div class="sidebar__footer">
        <div class="sidebar__status">
          <span class="status-dot status-dot--${backendStatus}"></span>
          <span>Backend: ${backendStatus}</span>
        </div>
        <div class="sidebar__actions">
          <button class="sidebar__action-btn" data-action="toggle-theme" title="Toggle theme">
            <nb-icon name="${theme === 'dark' ? 'sun' : 'moon'}" size="14"></nb-icon>
          </button>
          <button class="sidebar__action-btn" data-action="toggle-sidebar" title="Collapse sidebar">
            <nb-icon name="sidebar" size="14"></nb-icon>
          </button>
        </div>
      </div>
    `;
  }

  onMount() {
    // Watch for store changes
    this.bindStore(appStore, ['currentPage', 'backendStatus', 'theme']);

    // Nav item clicks
    this.shadowRoot.addEventListener('click', (e) => {
      const navItem = e.target.closest('.nav-item');
      if (navItem) {
        const path = navItem.dataset.path;
        const page = navItem.dataset.page;
        appStore.state.currentPage = page;
        try {
          const router = useRouter();
          router.navigate(path);
        } catch {
          // Router not initialized yet
          window.location.hash = path;
        }
        return;
      }

      const actionBtn = e.target.closest('[data-action]');
      if (actionBtn) {
        const action = actionBtn.dataset.action;
        if (action === 'toggle-theme') {
          const newTheme = appStore.state.theme === 'dark' ? 'light' : 'dark';
          appStore.state.theme = newTheme;
          document.documentElement.setAttribute('data-theme', newTheme);
          eventBus.emit(Events.THEME_CHANGED, newTheme);
        } else if (action === 'toggle-sidebar') {
          eventBus.emit(Events.SIDEBAR_TOGGLE);
        }
      }
    });

    // Keyboard navigation
    this.shadowRoot.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        const navItem = e.target.closest('.nav-item');
        if (navItem) {
          e.preventDefault();
          navItem.click();
        }
      }
    });
  }
}

defineComponent('nb-sidebar', NbSidebar);
export default NbSidebar;
