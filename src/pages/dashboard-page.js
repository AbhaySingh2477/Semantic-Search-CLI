/**
 * ═══════════════════════════════════════════════════════════════
 * <dashboard-page> — Notebook Manager
 * ═══════════════════════════════════════════════════════════════
 */
import { NbComponent, defineComponent } from '@core/component.js';
import { listNotebooks, createNotebook, deleteNotebook } from '@services/notebook-service.js';
import { useRouter } from '@core/router.js';

class DashboardPage extends NbComponent {
  constructor() {
    super();
    this.setState({
      notebooks: [],
      loading: true,
      error: null,
      showCreateDialog: false,
      newNotebookName: ''
    });
  }

  styles() {
    return `
      ${NbComponent.sharedStyles()}
      :host {
        display: block;
        height: 100%;
        width: 100%;
        overflow-y: auto;
        background: var(--color-bg-primary);
        color: var(--color-text-primary);
      }

      .dashboard-container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 40px 24px;
      }

      .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 32px;
      }

      .header h1 {
        font-size: 2rem;
        font-weight: 600;
        margin: 0;
        letter-spacing: -0.02em;
      }

      .btn-primary {
        background: var(--color-accent);
        color: #fff;
        border: none;
        padding: 10px 20px;
        border-radius: var(--radius-md);
        font-weight: 500;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 8px;
        transition: all var(--duration-fast) ease;
      }

      .btn-primary:hover {
        opacity: 0.9;
        transform: translateY(-1px);
      }

      .notebooks-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 24px;
      }

      .notebook-card {
        background: var(--color-bg-secondary);
        border: 1px solid var(--color-border);
        border-radius: var(--radius-lg);
        padding: 24px;
        cursor: pointer;
        transition: all var(--duration-base) ease;
        position: relative;
        overflow: hidden;
      }

      .notebook-card:hover {
        border-color: var(--color-accent);
        transform: translateY(-4px);
        box-shadow: 0 12px 24px rgba(0,0,0,0.2);
      }



      .notebook-icon {
        width: 48px;
        height: 48px;
        border-radius: var(--radius-md);
        color: var(--color-text-primary);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 16px;
      }

      .notebook-title {
        font-size: 1.25rem;
        font-weight: 600;
        margin: 0 0 8px 0;
      }

      .notebook-desc {
        color: var(--color-text-secondary);
        font-size: 0.875rem;
        margin: 0 0 16px 0;
        line-height: 1.5;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }

      .notebook-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.75rem;
        color: var(--color-text-tertiary);
        border-top: 1px solid var(--color-border);
        padding-top: 16px;
      }

      .delete-btn {
        position: absolute;
        top: 16px;
        right: 16px;
        background: transparent;
        border: none;
        color: var(--color-text-tertiary);
        cursor: pointer;
        padding: 4px;
        border-radius: var(--radius-sm);
        opacity: 0;
        transition: all var(--duration-fast) ease;
      }

      .delete-btn:hover {
        color: var(--color-danger);
        background: hsla(0, 84%, 60%, 0.1);
      }

      .notebook-card:hover .delete-btn {
        opacity: 1;
      }

      /* Dialog */
      .dialog-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.5);
        backdrop-filter: blur(4px);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
      }

      .dialog {
        background: var(--color-bg-secondary);
        border: 1px solid var(--color-border);
        border-radius: var(--radius-lg);
        width: 100%;
        max-width: 400px;
        padding: 24px;
        box-shadow: 0 24px 48px rgba(0,0,0,0.3);
      }

      .dialog h2 {
        margin: 0 0 16px 0;
        font-size: 1.25rem;
      }

      .dialog input {
        width: 100%;
        background: var(--color-bg-primary);
        border: 1px solid var(--color-border);
        color: var(--color-text-primary);
        padding: 10px 12px;
        border-radius: var(--radius-md);
        margin-bottom: 24px;
        font-size: 1rem;
        box-sizing: border-box;
      }

      .dialog input:focus {
        outline: none;
        border-color: var(--color-accent);
      }

      .dialog-actions {
        display: flex;
        justify-content: flex-end;
        gap: 12px;
      }

      .btn-secondary {
        background: transparent;
        color: var(--color-text-secondary);
        border: 1px solid var(--color-border);
        padding: 8px 16px;
        border-radius: var(--radius-md);
        cursor: pointer;
      }

      .btn-secondary:hover {
        background: var(--color-bg-primary);
        color: var(--color-text-primary);
      }

      .empty-state {
        text-align: center;
        padding: 80px 0;
        color: var(--color-text-secondary);
      }

      .empty-state nb-icon {
        color: var(--color-text-tertiary);
        margin-bottom: 16px;
      }
    `;
  }

  render() {
    if (this.state.loading) {
      return `<div class="dashboard-container">Loading notebooks...</div>`;
    }

    if (this.state.error) {
      return `<div class="dashboard-container"><div style="color:var(--color-danger)">${this.state.error}</div></div>`;
    }

    return `
      <div class="dashboard-container">
        <div class="header">
          <h1>My Notebooks</h1>
          <button class="btn-primary" id="btn-create">
            <nb-icon name="plus" size="16"></nb-icon>
            New Notebook
          </button>
        </div>

        ${this.state.notebooks.length === 0 ? `
          <div class="empty-state">
            <nb-icon name="book-open" size="48"></nb-icon>
            <h2>No notebooks yet</h2>
            <p>Create your first notebook to get started.</p>
          </div>
        ` : `
          <div class="notebooks-grid">
            ${this.state.notebooks.map(nb => `
              <div class="notebook-card" data-id="${nb.id}" style="--notebook-color: ${nb.color}">
                <button class="delete-btn" data-id="${nb.id}" title="Delete Notebook">
                  <nb-icon name="trash-2" size="16"></nb-icon>
                </button>
                <div class="notebook-icon">
                  <nb-icon name="${nb.icon}" size="24"></nb-icon>
                </div>
                <h3 class="notebook-title">${nb.name}</h3>
                <p class="notebook-desc">${nb.description || 'No description provided.'}</p>
                <div class="notebook-meta">
                  <span>${nb.document_count} Documents</span>
                  <span>Updated ${new Date(nb.updated_at).toLocaleDateString()}</span>
                </div>
              </div>
            `).join('')}
          </div>
        `}

        ${this.state.showCreateDialog ? `
          <div class="dialog-overlay" id="dialog-overlay">
            <div class="dialog" id="dialog-content">
              <h2>Create Notebook</h2>
              <input type="text" id="input-nb-name" placeholder="Notebook Name" autofocus value="${this.state.newNotebookName}">
              <div class="dialog-actions">
                <button class="btn-secondary" id="btn-cancel">Cancel</button>
                <button class="btn-primary" id="btn-save">Create</button>
              </div>
            </div>
          </div>
        ` : ''}
      </div>
    `;
  }

  async onMount() {
    await this.fetchNotebooks();
    this.setupListeners();
  }

  onUpdate() {
    this.setupListeners();
  }

  setupListeners() {
    const btnCreate = this.shadowRoot.getElementById('btn-create');
    if (btnCreate) {
      btnCreate.addEventListener('click', () => {
        this.setState({ showCreateDialog: true, newNotebookName: '' });
        setTimeout(() => {
          this.shadowRoot.getElementById('input-nb-name')?.focus();
        }, 50);
      });
    }

    if (this.state.showCreateDialog) {
      const btnCancel = this.shadowRoot.getElementById('btn-cancel');
      const btnSave = this.shadowRoot.getElementById('btn-save');
      const inputName = this.shadowRoot.getElementById('input-nb-name');
      const overlay = this.shadowRoot.getElementById('dialog-overlay');

      const closeDialog = () => this.setState({ showCreateDialog: false });

      btnCancel?.addEventListener('click', closeDialog);
      overlay?.addEventListener('click', (e) => {
        if (e.target === overlay) closeDialog();
      });

      inputName?.addEventListener('input', (e) => {
        this.state.newNotebookName = e.target.value;
      });

      inputName?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') btnSave?.click();
        if (e.key === 'Escape') closeDialog();
      });

      btnSave?.addEventListener('click', async () => {
        const name = this.state.newNotebookName.trim();
        if (!name) return;
        
        closeDialog();
        await this.createNewNotebook(name);
      });
    }

    // Grid clicks
    const grid = this.shadowRoot.querySelector('.notebooks-grid');
    if (grid) {
      grid.addEventListener('click', async (e) => {
        const deleteBtn = e.target.closest('.delete-btn');
        if (deleteBtn) {
          e.stopPropagation();
          const id = deleteBtn.dataset.id;
          await this.deleteNb(id);
          return;
        }

        const card = e.target.closest('.notebook-card');
        if (card) {
          const id = card.dataset.id;
          const router = useRouter();
          router.navigate(`/notebooks/${id}`);
        }
      });
    }
  }

  async fetchNotebooks() {
    try {
      const res = await listNotebooks();
      if (res.ok) {
        this.setState({ notebooks: res.data, loading: false });
      } else {
        this.setState({ error: res.error, loading: false });
      }
    } catch (err) {
      this.setState({ error: err.message, loading: false });
    }
  }

  async createNewNotebook(name) {
    try {
      const res = await createNotebook(name);
      if (res.ok) {
        await this.fetchNotebooks();
      } else {
        alert(res.error);
      }
    } catch (err) {
      alert(err.message);
    }
  }

  async deleteNb(id) {
    try {
      const res = await deleteNotebook(id);
      if (res.ok) {
        await this.fetchNotebooks();
      } else {
        alert(res.error);
      }
    } catch (err) {
      alert(err.message);
    }
  }
}

defineComponent('dashboard-page', DashboardPage);
export default DashboardPage;
