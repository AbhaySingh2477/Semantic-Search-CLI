import { NbComponent, defineComponent } from '@core/component.js';
import { appStore } from '@core/store.js';
import { onDocumentProgress, listDocuments } from '@services/document-service.js';
import { createSession, listSessions } from '@services/chat-service.js';
import { api } from '@core/api.js';

class NotebookPage extends NbComponent {
  
  onMount() {
    appStore.state.sidebarCollapsed = true;

    this._notebookId = this.routeParams?.id || 'default-notebook';
    this._documents = [];
    this._processingDocs = new Map();
    this._sessionId = null;
    // Search State
    this._searchQuery = '';
    this._searchMode = 'hybrid';
    this._isSearching = false;
    this._searchResults = [];
    this._pinnedChunks = [];

    this._loadDocuments();
    this._initChatSession();
    const uploadZone = this.$('nb-upload-zone');
    if (uploadZone) {
      uploadZone.setAttribute('notebook-id', this._notebookId);
      this.on(uploadZone, 'documents-uploaded', (e) => this._onDocumentsUploaded(e.detail));
    }

    this._unsubProgress = onDocumentProgress((data) => this._onProgress(data));
    
    requestAnimationFrame(() => this._bindSearchEvents());
  }

  onUnmount() {
    this._unsubProgress?.();
  }

  _bindSearchEvents() {
    const searchForm = this.$('.search-form');
    if (searchForm) {
      this.on(searchForm, 'submit', (e) => {
        e.preventDefault();
        const input = this.$('.search-input');
        if (input && input.value.trim()) {
          this._performSearch(input.value.trim());
        }
      });
    }

    const modeSelect = this.$('.search-mode-select');
    if (modeSelect) {
      this.on(modeSelect, 'change', (e) => {
        this._searchMode = e.target.value;
      });
    }

    // Pinning results
    this.$$('.pin-btn').forEach(btn => {
      this.on(btn, 'click', (e) => {
        const id = e.currentTarget.dataset.id;
        this._togglePin(id);
      });
    });
  }

  async _performSearch(query) {
    this._searchQuery = query;
    this._isSearching = true;
    this._searchResults = [];
    this._renderSearchPanel();

    try {
      const res = await api.post('/search', { 
        query: query, 
        notebook_id: this._notebookId,
        mode: this._searchMode,
        limit: 15,
      });
      if (res.ok && res.data) {
        this._searchResults = res.data.results || [];
      } else {
        this._searchResults = [];
      }
    } catch (err) {
      console.error('Search failed', err);
      this._searchResults = [];
    }
    
    this._isSearching = false;
    this._renderSearchPanel();
  }

  _togglePin(chunkId) {
    const chunk = this._searchResults.find(c => c.id === chunkId || c.chunk_id === chunkId);
    if (!chunk) return;
    
    // We normalize id vs chunk_id depending on API return
    const id = chunk.id || chunk.chunk_id;

    if (this._pinnedChunks.find(c => (c.id || c.chunk_id) === id)) {
      // Unpin
      this._pinnedChunks = this._pinnedChunks.filter(c => (c.id || c.chunk_id) !== id);
    } else {
      // Pin
      this._pinnedChunks = [...this._pinnedChunks, chunk];
    }
    
    // Sync with chat panel
    const panel = this.$('nb-chat-panel');
    if (panel && panel.setPinnedChunks) {
      panel.setPinnedChunks(this._pinnedChunks);
    }

    this._renderSearchPanel();
  }


  // ── Chat session ─────────────────────────────────────────────

  async _initChatSession() {
    // Reuse existing session or create new one
    const listResult = await listSessions(this._notebookId);
    let session = null;
    const sessions = listResult.data?.sessions || listResult.data || [];
    if (listResult.ok && sessions.length > 0) {
      session = sessions[0];
    } else {
      const createResult = await createSession(this._notebookId, '', 'Notebook Chat');
      if (createResult.ok && createResult.data) {
        session = createResult.data;
      }
    }

    if (session?.id) {
      this._sessionId = session.id;
      const chatPanel = this.$('nb-chat-panel');
      if (chatPanel?.loadSession) {
        chatPanel.loadSession(session.id, this._notebookId);
      }
    }
  }

  // ── Documents ────────────────────────────────────────────────

  async _loadDocuments() {
    const result = await listDocuments(this._notebookId);
    if (result.ok && result.data) {
      this._documents = result.data;
      this._renderDocumentList();
    }
  }

  _onDocumentsUploaded(data) {
    if (!data?.documents) return;
    for (const doc of data.documents) {
      if (!this._documents.find(d => d.id === doc.id)) this._documents.unshift(doc);
      this._processingDocs.set(doc.id, { stage: 'pending', progress: 0 });
    }
    this._renderDocumentList();
    this._updateSourceCount();
  }

  _onProgress(data) {
    const { document_id, stage, progress, error } = data;
    if (stage === 'indexed' || stage === 'complete') {
      this._processingDocs.delete(document_id);
      const doc = this._documents.find(d => d.id === document_id);
      if (doc) { doc.status = 'indexed'; doc.processing_progress = 1.0; }
    } else if (stage === 'failed') {
      this._processingDocs.delete(document_id);
      const doc = this._documents.find(d => d.id === document_id);
      if (doc) { doc.status = 'failed'; doc.error_message = error; }
    } else {
      this._processingDocs.set(document_id, { stage, progress });
    }
    const card = this.$(`nb-document-card[doc-id="${document_id}"]`);
    if (card) card.setProgress(stage, progress);
    this._renderProcessingStatus();
    this._updateSourceCount();
  }

  _renderDocumentList() {
    const container = this.$('.sources-list');
    const emptyState = this.$('.sources-empty');
    if (!container) return;
    if (this._documents.length === 0) {
      container.innerHTML = '';
      if (emptyState) emptyState.style.display = 'flex';
      return;
    }
    if (emptyState) emptyState.style.display = 'none';
    container.innerHTML = this._documents.map(doc => `
      <nb-document-card
        doc-id="${doc.id}" filename="${doc.filename}"
        file-type="${doc.file_type}" file-size="${doc.file_size}"
        status="${doc.status}" progress="${doc.processing_progress}"
        error="${doc.error_message || ''}"
      ></nb-document-card>
    `).join('');
    container.querySelectorAll('nb-document-card').forEach(card => {
      card.addEventListener('document-deleted', (e) => {
        this._documents = this._documents.filter(d => d.id !== e.detail.id);
        this._updateSourceCount();
      });
    });
  }

  _renderProcessingStatus() {
    const container = this.$('.processing-container');
    if (!container) return;
    if (this._processingDocs.size === 0) { container.innerHTML = ''; return; }
    const [docId, info] = [...this._processingDocs.entries()][0];
    const doc = this._documents.find(d => d.id === docId);
    container.innerHTML = `
      <nb-processing-status stage="${info.stage}" progress="${info.progress}"
        doc-name="${doc?.filename || 'Document'}"></nb-processing-status>
    `;
  }

  _updateSourceCount() {
    const indexed = this._documents.filter(d => d.status === 'indexed').length;
    const total = this._documents.length;
    const countEl = this.$('.source-count');
    if (countEl) countEl.textContent = `${indexed} / ${total} source${total !== 1 ? 's' : ''}`;
  }

  _escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  _renderSearchPanel() {
    const container = this.$('.search-results-container');
    if (!container) return;

    if (this._isSearching) {
      container.innerHTML = `<div class="loading-container">Searching documents...</div>`;
      return;
    }

    if (!this._searchResults || this._searchResults.length === 0) {
      if (this._searchQuery) {
        container.innerHTML = `<div class="empty-state">No results found for "${this._escapeHtml(this._searchQuery)}".</div>`;
      } else {
        container.innerHTML = `
          <div class="empty-state">
            <nb-icon name="search" size="24"></nb-icon>
            <div style="margin-top:10px">Search your notebook</div>
            <div style="font-size:0.8rem;opacity:0.7;margin-top:5px;max-width:200px">Find specific concepts and pin them to feed into the AI chat prompt.</div>
          </div>
        `;
      }
      return;
    }

    const pinIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>`;
    const checkIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="20 6 9 17 4 12"/></svg>`;

    const cards = this._searchResults.map(r => {
      const rId = r.id || r.chunk_id;
      const isPinned = this._pinnedChunks.some(c => (c.id || c.chunk_id) === rId);
      const levelLabel = r.level ? r.level.charAt(0).toUpperCase() + r.level.slice(1) : 'Chunk';
      return `
        <div class="result-card ${isPinned ? 'is-pinned' : ''}">
          <div class="result-meta">
            <span class="level-badge">${levelLabel}</span>
            <span>${r.page_number ? `p. ${r.page_number}` : ''}</span>
          </div>
          <div class="doc-name">${this._escapeHtml(r.section_title || r.document_name)}</div>
          <div class="result-content">${this._escapeHtml(r.content)}</div>
          <div class="result-actions">
            <span class="relevance-score">Match: ${Math.round((r.score || 0)*100)}%</span>
            <button class="pin-btn" data-id="${rId}">
              ${isPinned ? `${checkIcon} Pinned` : `${pinIcon} Pin to Chat`}
            </button>
          </div>
        </div>
      `;
    }).join('');

    container.innerHTML = cards;
    
    // Rebind pin buttons inside results
    requestAnimationFrame(() => this._bindSearchEvents());
  }

  // ── Styles ───────────────────────────────────────────────────

  styles() {
    return `
      ${NbComponent.sharedStyles()}
      :host {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: var(--color-bg-primary);
        color: var(--color-text-primary);
        overflow: hidden;
      }


      /* ── Header ─────────────────────────────────────────── */
      .nb-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 20px;
        border-bottom: 1px solid var(--color-border);
        flex-shrink: 0;
      }
      .nb-header__left { display: flex; align-items: center; gap: 14px; }
      .nb-header__back {
        width: 30px; height: 30px; border-radius: 8px;
        background: var(--color-bg-secondary);
        display: flex; align-items: center; justify-content: center;
        cursor: pointer; transition: background 150ms;
      }
      .nb-header__back:hover { background: var(--color-bg-hover); }
      .nb-header__title { font-size: 1rem; font-weight: 600; }
      .nb-header__right { display: flex; align-items: center; gap: 10px; }
      .header-btn {
        display: flex; align-items: center; gap: 6px;
        padding: 7px 14px; border-radius: 20px;
        font-size: 0.8125rem; font-weight: 500; cursor: pointer;
        border: 1px solid var(--color-border); background: transparent;
        color: var(--color-text-secondary); transition: all 150ms;
      }
      .header-btn:hover { background: var(--color-bg-hover); color: var(--color-text-primary); }

      /* ── Layout ─────────────────────────────────────────── */
      .nb-content {
        display: grid;
        grid-template-columns: 300px 1fr 340px;
        gap: 12px;
        padding: 12px;
        flex: 1;
        min-height: 0;
        overflow: hidden;
      }
      
      .panel {
        background: var(--color-bg-secondary);
        border: 1px solid var(--color-border);
        border-radius: var(--radius-lg);
        display: flex; flex-direction: column; overflow: hidden;
      }
      .panel-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 12px 14px;
        border-bottom: 1px solid var(--color-border);
        flex-shrink: 0;
      }
      .panel-title { font-size: 0.9375rem; font-weight: 600; }
      .panel-body { flex: 1; overflow-y: auto; padding: 12px 14px 14px; }

      /* ── Sources ────────────────────────────────────────── */
      .sources-list { display: flex; flex-direction: column; gap: 4px; margin-top: 8px; }
      .processing-container { margin-top: 8px; }
      .sources-empty {
        display: flex; flex-direction: column; align-items: center;
        text-align: center; color: var(--color-text-secondary);
        padding: 28px 12px; gap: 8px; margin-top: 20px;
      }

      /* ── Chat panel ─────────────────────────────────────── */
      .chat-panel { background: transparent; border: none; }

      /* ── Search Panel ───────────────────────────────────── */
      .search-form-container {
        padding: 12px 14px;
        border-bottom: 1px solid var(--color-border);
        display: flex;
        flex-direction: column;
        gap: 8px;
        background: var(--color-bg-elevated);
      }
      
      .search-form {
        display: flex;
        align-items: center;
        background: var(--color-bg-primary);
        border: 1px solid var(--color-border);
        border-radius: var(--radius-sm);
        padding: 4px 10px;
        transition: border-color 150ms;
      }
      .search-form:focus-within {
        border-color: hsl(250, 85%, 65%);
        box-shadow: 0 0 0 2px hsla(250, 85%, 65%, 0.15);
      }
      .search-input {
        flex: 1;
        background: transparent;
        border: none;
        color: var(--color-text-primary);
        padding: 6px;
        font-size: 0.85rem;
        outline: none;
      }
      
      .search-controls {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      
      .search-mode-select {
        background: var(--color-bg-primary);
        border: 1px solid var(--color-border);
        color: var(--color-text-secondary);
        border-radius: var(--radius-sm);
        padding: 4px 8px;
        font-size: 0.75rem;
        outline: none;
        cursor: pointer;
      }
      .search-mode-select:focus { border-color: hsl(250, 85%, 65%); }
      
      .search-results-container {
        flex: 1;
        overflow-y: auto;
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      
      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        color: var(--color-text-secondary);
        height: 100%;
        font-size: 0.85rem;
        padding: 20px;
      }
      
      .loading-container {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: var(--color-text-secondary);
        font-size: 0.85rem;
      }
      
      .result-card {
        background: var(--color-bg-primary);
        border: 1px solid var(--color-border);
        border-radius: var(--radius-md);
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        transition: border-color 150ms;
      }
      .result-card:hover { border-color: hsl(250, 50%, 40%); }
      .result-card.is-pinned { border-color: hsl(250, 85%, 65%); background: hsla(250, 85%, 65%, 0.03); }
      
      .result-meta {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        font-size: 0.7rem;
        color: var(--color-text-secondary);
      }
      .level-badge {
        background: hsla(0,0%,100%,0.08);
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 500;
        color: var(--color-text-primary);
      }
      .doc-name { margin-top: 2px; font-weight: 500; color: var(--color-text-primary); font-size: 0.8rem;}
      
      .result-content {
        font-size: 0.75rem;
        line-height: 1.5;
        color: var(--color-text-secondary);
        display: -webkit-box;
        -webkit-line-clamp: 4;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
      
      .result-actions {
        margin-top: auto;
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-top: 8px;
        border-top: 1px solid var(--color-border);
      }
      
      .relevance-score {
        font-size: 0.65rem;
        font-weight: 500;
        color: hsl(150, 80%, 40%);
        background: hsla(150, 80%, 40%, 0.1);
        padding: 2px 6px;
        border-radius: 4px;
      }
      
      .pin-btn {
        background: transparent;
        border: 1px solid var(--color-border);
        color: var(--color-text-primary);
        padding: 4px 10px;
        border-radius: var(--radius-full);
        font-size: 0.7rem;
        font-weight: 500;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 4px;
        transition: all 150ms;
      }
      .pin-btn:hover { background: hsla(0,0%,100%,0.06); }
      .result-card.is-pinned .pin-btn {
        background: hsl(250, 85%, 65%);
        border-color: hsl(250, 85%, 65%);
        color: white;
      }
    `;
  }

  // ── Render ───────────────────────────────────────────────────

  render() {
    return `

      <!-- Header -->
      <div class="nb-header">
        <div class="nb-header__left">
          <div class="nb-header__back" onclick="window.location.hash='/'">
            <nb-icon name="chevron-left" size="18"></nb-icon>
          </div>
          <div class="nb-header__title">Notebook</div>
        </div>
        <div class="nb-header__right">
          <button class="header-btn">
            <nb-icon name="settings" size="15"></nb-icon> Settings
          </button>
        </div>
      </div>

      <!-- Main 3-column layout -->
      <div class="nb-content">

        <!-- Sources Panel -->
        <div class="panel sources-panel">
          <div class="panel-header">
            <div class="panel-title">Sources</div>
            <span class="source-count" style="font-size:0.8rem;color:var(--color-text-secondary)">0 sources</span>
          </div>
          <div class="panel-body">
            <nb-upload-zone notebook-id="${this._notebookId || 'default-notebook'}"></nb-upload-zone>
            <div class="processing-container"></div>
            <div class="sources-list"></div>
            <div class="sources-empty">
              <nb-icon name="file" size="26"></nb-icon>
              <div style="font-weight:500">No sources yet</div>
              <div style="font-size:0.8rem;line-height:1.5">
                Drop files above to add PDFs, DOCX, text and more.
              </div>
            </div>
          </div>
        </div>

        <!-- Chat Panel — wired to nb-chat-panel with real session -->
        <div class="panel chat-panel" style="display:flex;flex-direction:column;">
          <div class="panel-header">
            <div class="panel-title">Chat</div>
          </div>
          <nb-chat-panel style="flex:1;min-height:0;"></nb-chat-panel>
        </div>

        <!-- Search Panel (Replaces Studio) -->
        <div class="panel search-panel">
          <div class="panel-header">
            <div class="panel-title">Search & Pin</div>
          </div>
          
          <div class="search-form-container">
            <form class="search-form">
              <nb-icon name="search" size="14" style="color:var(--color-text-secondary)"></nb-icon>
              <input type="text" class="search-input" placeholder="Search concept or keyword..." value="${this._escapeHtml(this._searchQuery)}">
            </form>
            <div class="search-controls">
              <span style="font-size:0.75rem;color:var(--color-text-secondary)">Mode:</span>
              <select class="search-mode-select">
                <option value="hybrid" ${this._searchMode === 'hybrid' ? 'selected' : ''}>Hybrid Search</option>
                <option value="vector" ${this._searchMode === 'vector' ? 'selected' : ''}>Semantic Search</option>
                <option value="keyword" ${this._searchMode === 'keyword' ? 'selected' : ''}>Keyword Search</option>
              </select>
            </div>
          </div>
          
          <div class="search-results-container">
            <!-- Results rendered via JS -->
            <div class="empty-state">
              <nb-icon name="search" size="24"></nb-icon>
              <div style="margin-top:10px">Search your notebook</div>
              <div style="font-size:0.8rem;opacity:0.7;margin-top:5px;max-width:200px">Find specific concepts and pin them to feed into the AI chat prompt.</div>
            </div>
          </div>
        </div>

      </div>
    `;
  }
}

defineComponent('notebook-page', NotebookPage);
export default NotebookPage;
