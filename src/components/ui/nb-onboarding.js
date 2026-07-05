import { NbComponent, defineComponent } from '@core/component.js';
import { api } from '@core/api.js';

class NbOnboarding extends NbComponent {
  constructor() {
    super();
    this.setState({
      apiKey: '',
      loading: false,
      error: null
    });
  }

  styles() {
    return `
      ${NbComponent.sharedStyles()}
      .overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: var(--color-bg-primary);
        z-index: 9999;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 24px;
        color: var(--color-text-primary);
      }

      .container {
        max-width: 500px;
        width: 100%;
        background: var(--color-bg-secondary);
        border: 1px solid var(--color-border);
        border-radius: var(--radius-lg);
        padding: 40px;
        box-shadow: 0 24px 48px rgba(0,0,0,0.1);
        text-align: center;
      }

      .logo-container {
        width: 64px;
        height: 64px;
        background: var(--color-accent);
        color: white;
        border-radius: var(--radius-md);
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 24px auto;
      }

      h1 {
        font-size: 1.75rem;
        margin: 0 0 16px 0;
      }

      p {
        color: var(--color-text-secondary);
        line-height: 1.6;
        margin: 0 0 24px 0;
      }

      .step {
        background: var(--color-bg-primary);
        border: 1px solid var(--color-border);
        padding: 16px;
        border-radius: var(--radius-md);
        margin-bottom: 24px;
        text-align: left;
      }

      .step strong {
        color: var(--color-text-primary);
        display: block;
        margin-bottom: 8px;
      }

      .step a {
        color: var(--color-accent);
        text-decoration: none;
        font-weight: 500;
      }

      .step a:hover {
        text-decoration: underline;
      }

      input {
        width: 100%;
        padding: 12px 16px;
        background: var(--color-bg-primary);
        border: 1px solid var(--color-border);
        color: var(--color-text-primary);
        border-radius: var(--radius-md);
        font-size: 1rem;
        margin-bottom: 16px;
        box-sizing: border-box;
      }

      input:focus {
        outline: none;
        border-color: var(--color-accent);
      }

      button {
        width: 100%;
        background: var(--color-accent);
        color: white;
        border: none;
        padding: 12px;
        border-radius: var(--radius-md);
        font-size: 1rem;
        font-weight: 600;
        cursor: pointer;
        transition: opacity var(--duration-fast);
      }

      button:hover:not(:disabled) {
        opacity: 0.9;
      }

      button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .error {
        color: var(--color-danger);
        font-size: 0.875rem;
        margin-top: -8px;
        margin-bottom: 16px;
        text-align: left;
      }
    `;
  }

  render() {
    return `
      <div class="overlay">
        <div class="container">
          <div class="logo-container">
            <nb-icon name="cpu" size="32"></nb-icon>
          </div>
          <h1>Welcome to NotebookLM Local</h1>
          <p>Before you can start analyzing documents and chatting, you need to configure your Groq API key. Groq provides ultra-fast, free cloud inference for LLMs.</p>
          
          <div class="step">
            <strong>Step 1: Get your free API Key</strong>
            <p style="margin-bottom:0">Visit <a href="https://console.groq.com/keys" target="_blank" rel="noopener">console.groq.com/keys</a>, create an account, and generate a new API key.</p>
          </div>

          <div class="step">
            <strong>Step 2: Enter your API Key</strong>
            <input type="password" id="api-key-input" placeholder="gsk_..." value="${this.state.apiKey}">
            ${this.state.error ? `<div class="error">${this.state.error}</div>` : ''}
            <button id="save-btn" ${this.state.loading || !this.state.apiKey ? 'disabled' : ''}>
              ${this.state.loading ? 'Saving...' : 'Save & Continue'}
            </button>
          </div>
        </div>
      </div>
    `;
  }

  setupListeners() {
    const input = this.shadowRoot.getElementById('api-key-input');
    const saveBtn = this.shadowRoot.getElementById('save-btn');

    if (input) {
      input.addEventListener('input', (e) => {
        this.setState({ apiKey: e.target.value, error: null });
      });

      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && this.state.apiKey) {
          saveBtn?.click();
        }
      });
    }

    if (saveBtn) {
      saveBtn.addEventListener('click', async () => {
        if (!this.state.apiKey) return;
        
        this.setState({ loading: true });
        try {
          const res = await api.post('/settings/groq-key', { api_key: this.state.apiKey });
          if (res.ok) {
            // Success! Remove the component and emit an event so app can continue
            this.remove();
            window.location.reload(); // Reload to re-initialize everything with the key
          } else {
            this.setState({ error: res.error, loading: false });
          }
        } catch (err) {
          this.setState({ error: err.message, loading: false });
        }
      });
    }
  }

  onUpdate() {
    this.setupListeners();
  }

  onMount() {
    this.setupListeners();
    setTimeout(() => {
      this.shadowRoot.getElementById('api-key-input')?.focus();
    }, 100);
  }
}

defineComponent('nb-onboarding', NbOnboarding);
export default NbOnboarding;
