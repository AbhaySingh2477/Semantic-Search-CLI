/**
 * ═══════════════════════════════════════════════════════════════
 * nb-chat-panel — Main chat container
 * Manages the message list, streaming state, auto-scroll,
 * and coordinates between input, messages, and thinking indicator.
 * ═══════════════════════════════════════════════════════════════
 */

import { NbComponent, defineComponent } from '@core/component.js';
import chatService from '@services/chat-service.js';

class NbChatPanel extends NbComponent {
  /** @type {{ abort: Function } | null} */
  #activeStream = null;

  onMount() {
    this.setState({
      sessionId: '',
      notebookId: '',
      messages: [],
      isStreaming: false,
      statusMessage: '',
      retrievedSources: [],
      error: '',
      pinnedChunks: [],  // user-pinned search results
    });
  }

  onUnmount() {
    this.#activeStream?.abort();
    this.#activeStream = null;
  }

  _bindEvents() {
    const input = this.$('nb-chat-input');
    if (input) {
      this.on(input, 'send-message', (e) => {
        this._handleSend(e.detail.content);
      });
      this.on(input, 'stop-generation', () => {
        this._handleStop();
      });
    }
  }

  /**
   * Load a chat session.
   * @param {string} sessionId
   * @param {string} notebookId
   */
  async loadSession(sessionId, notebookId) {
    this.setState({
      sessionId,
      notebookId,
      messages: [],
      error: '',
      isStreaming: false,
    });

    if (!sessionId) return;

    const result = await chatService.getSession(sessionId);
    if (result.ok && result.data) {
      this.setState({ messages: result.data.messages || [] });
      requestAnimationFrame(() => {
        this._scrollToBottom();
      });
    }
  }

  /**
   * Handle sending a message.
   * @param {string} content
   */
  async _handleSend(content) {
    if (!content?.trim() || this.state.isStreaming) return;

    const { sessionId, messages, pinnedChunks = [] } = this.state;
    if (!sessionId) {
      this.setState({ error: 'No active chat session. Please wait or refresh.' });
      return;
    }

    const pinnedIds = pinnedChunks.map(c => c.id).filter(Boolean);

    // Add user message to UI immediately
    const userMsg = {
      role: 'user',
      content: content.trim(),
      created_at: new Date().toISOString(),
      citations: [],
      pinnedCount: pinnedIds.length,
    };
    const newMessages = [...messages, userMsg];
    this.setState({
      messages: newMessages,
      isStreaming: true,
      error: '',
      statusMessage: 'Connecting...',
      retrievedSources: [],
      pinnedChunks: [],  // clear pins after send
    });

    // Notify parent to collapse search panel
    this.emit('message-sent', {});

    requestAnimationFrame(() => {
      this._scrollToBottom();
      this._updateInputState();
      this._renderPinnedPills();
    });

    // Start SSE stream
    let assistantContent = '';
    let citations = [];

    this.#activeStream = chatService.sendMessage(sessionId, content.trim(), {
      onStatus: (message) => {
        this.setState({ statusMessage: message });
        this._updateThinking(message);
      },

      onRetrieval: (data) => {
        this.setState({
          retrievedSources: data.chunks || [],
          statusMessage: `Found ${data.count} relevant sources`,
        });
        this._updateThinking(`Found ${data.count} sources — generating response…`);
      },

      onToken: (token) => {
        assistantContent += token;
        // Update the streaming message
        this._updateStreamingMessage(assistantContent);
      },

      onCitations: (citationData) => {
        citations = citationData || [];
      },

      onDone: (data) => {
        // Finalize the assistant message
        const finalMessages = [...this.state.messages];

        // Remove the streaming placeholder if present
        const lastMsg = finalMessages[finalMessages.length - 1];
        if (lastMsg && lastMsg._streaming) {
          finalMessages.pop();
        }

        finalMessages.push({
          role: 'assistant',
          content: assistantContent,
          citations: citations,
          created_at: new Date().toISOString(),
          latency_ms: data.latency_ms || 0,
        });

        this.setState({
          messages: finalMessages,
          isStreaming: false,
          statusMessage: '',
        });

        this.#activeStream = null;

        requestAnimationFrame(() => {
          this._scrollToBottom();
          this._updateInputState();
          this._hideThinking();
          this.$('nb-chat-input')?.focusInput();
        });

        // Emit session title update
        if (data.session_title) {
          this.emit('session-title-updated', {
            sessionId,
            title: data.session_title,
          });
        }
      },

      onError: (message) => {
        this.setState({
          isStreaming: false,
          statusMessage: '',
          error: message,
        });
        this.#activeStream = null;

        requestAnimationFrame(() => {
          this._updateInputState();
          this._hideThinking();
        });
      },
    }, null, pinnedIds);
  }

  _handleStop() {
    this.#activeStream?.abort();
    this.#activeStream = null;

    this.setState({
      isStreaming: false,
      statusMessage: '',
    });

    requestAnimationFrame(() => {
      this._updateInputState();
      this._hideThinking();
    });
  }

  _updateStreamingMessage(content) {
    const messages = [...this.state.messages];

    // Check if last message is the streaming placeholder
    const lastMsg = messages[messages.length - 1];
    if (lastMsg && lastMsg._streaming) {
      lastMsg.content = content;
    } else {
      messages.push({
        role: 'assistant',
        content: content,
        citations: [],
        created_at: new Date().toISOString(),
        _streaming: true,
      });
    }

    // Direct DOM update for performance (avoid full re-render)
    const msgList = this.$('.message-list');
    if (msgList) {
      const lastMsgEl = msgList.querySelector('nb-message:last-child');
      if (lastMsgEl && lastMsgEl.state?.role === 'assistant') {
        lastMsgEl.appendToken('');
        // Update the content directly
        lastMsgEl.setState({ content, isStreaming: true });
        // Need to add a new message element
        this.state.messages = messages;
        this.update();
        requestAnimationFrame(() => {
          this._hideThinking();
        });
      }
    }

    this.state.messages = messages;
    this._scrollToBottom();
  }

  _updateInputState() {
    const input = this.$('nb-chat-input');
    if (input) {
      input.setStreaming(this.state.isStreaming);
    }
  }

  _updateThinking(message) {
    const thinking = this.$('nb-thinking');
    if (thinking) {
      thinking.setMessage(message);
      thinking.show();
    }
  }

  _hideThinking() {
    const thinking = this.$('nb-thinking');
    if (thinking) {
      thinking.hide();
    }
  }

  _scrollToBottom() {
    requestAnimationFrame(() => {
      const container = this.$('.message-list');
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    });
  }

  setPinnedChunks(chunks) {
    this.setState({ pinnedChunks: chunks || [] });
    this._renderPinnedPills();
  }

  _renderPinnedPills() {
    const container = this.$('.pinned-pills-container');
    if (!container) return;

    const { pinnedChunks = [] } = this.state;
    if (pinnedChunks.length === 0) {
      container.style.display = 'none';
      container.innerHTML = '';
      return;
    }

    container.style.display = 'flex';
    container.innerHTML = pinnedChunks.map(chunk => `
      <div class="pinned-pill">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
        </svg>
        <span>${this._escapeHtml(chunk.section_title || chunk.document_name)}</span>
        <button class="remove-pin" data-id="${chunk.id}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
    `).join('');

    container.querySelectorAll('.remove-pin').forEach(btn => {
      this.on(btn, 'click', (e) => {
        const id = e.currentTarget.dataset.id;
        const remaining = this.state.pinnedChunks.filter(c => c.id !== id);
        this.setPinnedChunks(remaining);
      });
    });
  }

  _escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  styles() {
    return `
      ${NbComponent.sharedStyles()}

      :host {
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: hidden;
      }

      .chat-container {
        display: flex;
        flex-direction: column;
        height: 100%;
        position: relative;
      }

      .message-list {
        flex: 1;
        overflow-y: auto;
        padding: 24px 20px;
        scroll-behavior: smooth;
      }

      .message-list::-webkit-scrollbar {
        width: 6px;
      }
      .message-list::-webkit-scrollbar-track {
        background: transparent;
      }
      .message-list::-webkit-scrollbar-thumb {
        background: hsla(0, 0%, 100%, 0.1);
        border-radius: 3px;
      }

      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100%;
        text-align: center;
        padding: 40px;
      }

      .empty-icon {
        width: 72px;
        height: 72px;
        margin-bottom: 20px;
        opacity: 0.15;
      }

      .empty-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: var(--color-text-primary, hsl(0, 0%, 95%));
        margin-bottom: 8px;
      }

      .empty-desc {
        font-size: 0.9rem;
        color: var(--color-text-secondary, hsl(0, 0%, 68%));
        max-width: 400px;
        line-height: 1.6;
      }

      .thinking-container {
        padding: 0 20px 10px 20px;
        flex-shrink: 0;
      }

      /* ── Pinned Context Pills ── */
      .pinned-pills-container {
        display: none;
        flex-wrap: wrap;
        gap: 8px;
        padding: 8px 20px 12px;
        border-top: 1px solid var(--color-border);
        background: hsla(230, 15%, 18%, 0.4);
      }
      .pinned-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        background: hsla(250, 85%, 65%, 0.15);
        border: 1px solid hsla(250, 85%, 65%, 0.25);
        border-radius: var(--radius-full);
        font-size: 0.75rem;
        color: hsl(250, 85%, 75%);
        max-width: 250px;
      }
      .pinned-pill svg {
        width: 12px;
        height: 12px;
        flex-shrink: 0;
      }
      .pinned-pill span {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .pinned-pill .remove-pin {
        background: transparent;
        border: none;
        padding: 2px;
        color: inherit;
        opacity: 0.6;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
      }
      .pinned-pill .remove-pin:hover {
        opacity: 1;
        background: hsla(250, 85%, 65%, 0.2);
      }

      .error-banner {
        margin: 8px 20px;
        padding: 12px 16px;
        background: hsla(0, 84%, 55%, 0.1);
        border: 1px solid hsla(0, 84%, 55%, 0.3);
        border-radius: var(--radius-md, 10px);
        color: hsl(0, 84%, 70%);
        font-size: 0.85rem;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .error-banner svg {
        width: 16px;
        height: 16px;
        flex-shrink: 0;
      }

      .sources-preview {
        padding: 8px 20px;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }

      .source-tag {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 10px;
        font-size: 0.72rem;
        background: hsla(250, 85%, 65%, 0.08);
        border: 1px solid hsla(250, 85%, 65%, 0.15);
        border-radius: var(--radius-full, 9999px);
        color: var(--color-text-secondary, hsl(0, 0%, 68%));
      }

      .source-tag svg {
        width: 12px;
        height: 12px;
        opacity: 0.5;
      }
    `;
  }

  render() {
    const { messages = [], isStreaming = false, statusMessage = '', retrievedSources = [], error = '' } = this.state;

    const errorHtml = error ? `
      <div class="error-banner">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        ${error}
      </div>
    ` : '';

    // Sources preview (during retrieval)
    let sourcesHtml = '';
    if (isStreaming && retrievedSources.length > 0) {
      const docIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
      sourcesHtml = `
        <div class="sources-preview">
          ${retrievedSources.map(s => `
            <span class="source-tag">${docIcon} ${s.document_name || 'Document'}${s.page_number ? ` p.${s.page_number}` : ''}</span>
          `).join('')}
        </div>
      `;
    }

    if (messages.length === 0 && !isStreaming) {
      return `
        <div class="chat-container">
          <div class="message-list">
            <div class="empty-state">
              <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
              <div class="empty-title">Chat with your documents</div>
              <div class="empty-desc">
                Ask questions about your uploaded documents. The AI will search through them and provide answers with citations.
              </div>
            </div>
          </div>
          ${errorHtml}
          <nb-chat-input></nb-chat-input>
        </div>
      `;
    }

    const messagesHtml = messages.map((msg, i) => {
      const isStreamingMsg = msg._streaming;
      return `<nb-message
        data-index="${i}"
        data-role="${msg.role}"
        data-streaming="${isStreamingMsg || false}"
      ></nb-message>`;
    }).join('');

    return `
      <div class="chat-container">
        <div class="message-list">
          ${messagesHtml}
        </div>
        ${sourcesHtml}
        <div class="thinking-container">
          <nb-thinking message="${statusMessage || 'Thinking'}"></nb-thinking>
        </div>
        ${errorHtml}
        <div class="pinned-pills-container"></div>
        <nb-chat-input></nb-chat-input>
      </div>
    `;
  }

  onUpdate() {
    // After rendering, set data on message components
    const { messages, isStreaming } = this.state;
    const msgEls = this.$$('nb-message');

    msgEls.forEach((el, i) => {
      if (i < messages.length) {
        el.setData({
          ...messages[i],
          isStreaming: messages[i]._streaming || false,
        });
      }
    });

    // Update thinking visibility
    const thinking = this.$('nb-thinking');
    if (thinking) {
      if (isStreaming && this.state.statusMessage) {
        thinking.show();
      } else {
        thinking.hide();
      }
    }

    // Update input state
    this._bindEvents();
    this._updateInputState();
    this._renderPinnedPills();
  }
}

defineComponent('nb-chat-panel', NbChatPanel);
export default NbChatPanel;
