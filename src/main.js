/**
 * ═══════════════════════════════════════════════════════════════
 * Application Entry Point
 * Bootstraps the entire frontend: imports components, initializes
 * router and stores, starts WebSocket connection, checks backend.
 * ═══════════════════════════════════════════════════════════════
 */

/* ── Import Core ─────────────────────────────────────────── */
import { createRouter } from '@core/router.js';
import { appStore } from '@core/store.js';
import { api, ws } from '@core/api.js';
import { eventBus, Events } from '@core/events.js';

/* ── Import Components (registers custom elements) ────── */
import '@components/ui/nb-icon.js';
import '@components/ui/nb-button.js';
import '@components/ui/nb-toast.js';
import '@components/layout/nb-sidebar.js';
import '@components/layout/nb-header.js';
import '@components/layout/nb-shell.js';

/* ── Import Document Components (Phase 2) ────────────── */
import '@components/documents/nb-upload-zone.js';
import '@components/documents/nb-document-card.js';
import '@components/documents/nb-processing-status.js';

/* ── Import Search Components (Phase 3) ──────────────── */
import '@components/search/nb-search-bar.js';
import '@components/search/nb-search-results.js';
import '@components/search/nb-search-filters.js';

/* ── Import Chat Components (Phase 4) ────────────────── */
import '@components/chat/nb-thinking.js';
import '@components/chat/nb-citation.js';
import '@components/chat/nb-message.js';
import '@components/chat/nb-chat-input.js';
import '@components/chat/nb-chat-panel.js';

import '@pages/dashboard-page.js';
import '@pages/notebook-page.js';

/* ── Route Definitions ───────────────────────────────────── */
const routes = [
  {
    path: '/',
    title: 'Dashboard',
    component: () => document.createElement('dashboard-page'),
  },
  {
    path: '/notebooks/:id',
    title: 'Notebook',
    component: () => document.createElement('notebook-page'),
  },
  {
    path: '*',
    title: '404',
    component: () => {
      const el = document.createElement('div');
      el.innerHTML = `<div style="padding:40px;text-align:center;color:var(--color-text-secondary)">
        <h2 style="color:var(--color-text-primary);font-size:3rem;margin-bottom:8px">404</h2>
        <p>Page not found</p>
        <a href="#/" style="color:var(--color-accent);margin-top:16px;display:inline-block">← Back to Dashboard</a>
      </div>`;
      return el;
    },
  },
];

/* ── Application Bootstrap ───────────────────────────────── */

async function initApp() {
  console.log('[App] Initializing NotebookLM Local...');

  // 1. Apply persisted theme
  const theme = appStore.state.theme || 'dark';
  document.documentElement.setAttribute('data-theme', theme);

  // 2. Mount the app shell
  const appRoot = document.getElementById('app');
  const shell = document.createElement('nb-shell');
  appRoot.appendChild(shell);

  // 3. Wait for shell to be ready, then init router
  await new Promise(resolve => {
    // Small delay to ensure shadow DOM is ready
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        resolve();
      });
    });
  });

  const outlet = shell.getOutlet();
  if (!outlet) {
    console.error('[App] Router outlet not found');
    return;
  }

  // 4. Initialize router
  const router = createRouter(outlet, routes);

  // Track page changes
  router.afterEach((to) => {
    appStore.state.currentPage = 'notebooks';
  });

  // 5. Check backend health
  await checkBackendHealth();

  // 6. Hide boot screen
  const bootScreen = document.getElementById('boot-screen');
  if (bootScreen) {
    bootScreen.classList.add('hidden');
    setTimeout(() => bootScreen.remove(), 400);
  }

  // 7. Hide shell loader
  shell.hideLoader();

  // 8. Connect WebSocket for real-time updates
  try {
    ws.connect();
    ws.onStatus((status) => {
      appStore.state.backendStatus = status;
    });
  } catch {
    // WebSocket is optional for initial load
  }

  // 9. Mark app as initialized
  appStore.state.initialized = true;
  eventBus.emit(Events.APP_READY);

  console.log('[App] NotebookLM Local ready ✓');
}

/**
 * Check if the Python backend is running.
 */
async function checkBackendHealth() {
  appStore.state.backendStatus = 'connecting';

  try {
    const result = await api.get('/health', { timeout: 5000 });
    if (result.ok) {
      appStore.state.backendStatus = 'connected';
      eventBus.emit(Events.BACKEND_CONNECTED, result.data);
      console.log('[App] Backend connected:', result.data);
    } else {
      appStore.state.backendStatus = 'disconnected';
      eventBus.emit(Events.BACKEND_DISCONNECTED);
    }
  } catch {
    appStore.state.backendStatus = 'disconnected';
    eventBus.emit(Events.BACKEND_DISCONNECTED);
    console.warn('[App] Backend not available — start it with: cd backend && python main.py');
  }
}

// Periodically check backend health
setInterval(checkBackendHealth, 30000);

// Start the app
initApp().catch(err => {
  console.error('[App] Fatal initialization error:', err);
});
