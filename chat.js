/**
 * DevMind Studio — Chat Module
 * Manages the chat panel: messages, input, markdown rendering.
 */

const Chat = (() => {
  let messagesEl     = null;
  let inputEl        = null;
  let sendBtn        = null;
  let typingEl       = null;
  let typingLabel    = null;
  let welcomeCard    = null;
  let onSendCallback = null;

  // ── Init ──────────────────────────────────────────────
  function init(onSend) {
    onSendCallback = onSend;

    messagesEl  = document.getElementById('chat-messages');
    inputEl     = document.getElementById('chat-input');
    sendBtn     = document.getElementById('send-btn');
    typingEl    = document.getElementById('typing-indicator');
    typingLabel = document.getElementById('typing-label');
    welcomeCard = document.getElementById('welcome-card');

    // Send on button click
    sendBtn.addEventListener('click', handleSend);

    // Send on Enter (Shift+Enter = newline)
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });

    // Auto-resize textarea
    inputEl.addEventListener('input', () => {
      inputEl.style.height = 'auto';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
    });

    // Quick prompt buttons
    messagesEl.addEventListener('click', (e) => {
      const btn = e.target.closest('.qp-btn');
      if (btn && btn.dataset.prompt) {
        sendMessage(btn.dataset.prompt);
      }
    });

    // Clear button
    const clearBtn = document.getElementById('clear-chat-btn');
    if (clearBtn) clearBtn.addEventListener('click', clearChat);
  }

  // ── Send ──────────────────────────────────────────────
  function handleSend() {
    const text = inputEl.value.trim();
    if (!text) return;
    sendMessage(text);
  }

  function sendMessage(text) {
    hideWelcome();
    addMessage('user', text);

    inputEl.value = '';
    inputEl.style.height = 'auto';
    setTyping(true, 'DevMind is thinking…');

    if (onSendCallback) onSendCallback(text);
  }

  // ── Messages ──────────────────────────────────────────
  function addMessage(role, content, meta = {}) {
    if (!messagesEl) return;

    const isUser = role === 'user';
    const now    = new Date().toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' });

    const el = document.createElement('div');
    el.className = `chat-msg ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'chat-msg-bubble';

    if (isUser) {
      bubble.textContent = content;
    } else {
      // Render markdown for AI messages
      bubble.innerHTML = renderMarkdown(content);
    }

    el.appendChild(bubble);

    // Timestamp
    const timeEl = document.createElement('div');
    timeEl.className = 'msg-time';
    timeEl.textContent = now;
    el.appendChild(timeEl);

    // Files updated badge
    if (!isUser && meta.files_updated && meta.files_updated > 0) {
      const badge = document.createElement('div');
      badge.className = 'files-badge';
      badge.innerHTML = `
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" style="width:12px;height:12px">
          <path d="M13 2H3a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V3a1 1 0 0 0-1-1z"/>
          <path d="M5 8l2 2 4-4"/>
        </svg>
        ${meta.files_updated} file${meta.files_updated !== 1 ? 's' : ''} updated
      `;
      el.appendChild(badge);
    }

    messagesEl.appendChild(el);
    scrollToBottom();
  }

  function addSystemMessage(text, type = 'info') {
    if (!messagesEl) return;
    const el = document.createElement('div');
    el.className = 'chat-msg assistant';
    el.innerHTML = `
      <div class="chat-msg-bubble" style="background:var(--surface-3);border-color:var(--border-2);font-size:12px;color:var(--text-muted)">
        <em>${escHtml(text)}</em>
      </div>
    `;
    messagesEl.appendChild(el);
    scrollToBottom();
  }

  function clearChat() {
    if (!messagesEl) return;
    // Remove all messages but keep the welcome card
    const msgs = messagesEl.querySelectorAll('.chat-msg');
    msgs.forEach(m => m.remove());
    showWelcome();
  }

  // ── Typing indicator ──────────────────────────────────
  function setTyping(visible, label = 'Thinking…') {
    if (!typingEl) return;
    typingEl.style.display = visible ? 'flex' : 'none';
    if (typingLabel) typingLabel.textContent = label;
    if (!visible) setInputEnabled(true);
    if (visible)  setInputEnabled(false);
  }

  function setTypingLabel(label) {
    if (typingLabel) typingLabel.textContent = label;
  }

  // ── Input state ───────────────────────────────────────
  function setInputEnabled(enabled) {
    if (inputEl)  inputEl.disabled  = !enabled;
    if (sendBtn)  sendBtn.disabled  = !enabled;
  }

  // ── Welcome card ──────────────────────────────────────
  function hideWelcome() {
    if (welcomeCard) welcomeCard.style.display = 'none';
  }

  function showWelcome() {
    if (welcomeCard) welcomeCard.style.display = 'block';
  }

  // ── Scroll ────────────────────────────────────────────
  function scrollToBottom() {
    if (messagesEl) {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  // ── Markdown rendering ────────────────────────────────
  function renderMarkdown(text) {
    if (window.marked) {
      try {
        return marked.parse(text, {
          breaks: true,
          gfm: true,
        });
      } catch (e) {
        return escHtml(text).replace(/\n/g, '<br>');
      }
    }
    // Fallback: basic rendering
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  return {
    init,
    addMessage,
    addSystemMessage,
    setTyping,
    setTypingLabel,
    setInputEnabled,
    clearChat,
  };
})();
