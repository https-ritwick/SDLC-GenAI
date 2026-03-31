/**
 * DevMind Studio — App Controller
 * Central coordinator: WebSocket, state management, tab switching,
 * panel resizing, settings, and module wiring.
 */

const App = (() => {
  // ── Config ────────────────────────────────────────────
  // Auto-detect backend URL: on Render/production the frontend IS the backend
  // (FastAPI serves static files). Use window.location.origin so it works
  // on localhost:8000, Render, and any other deployment automatically.
  const DEFAULT_BACKEND = window.location.origin;
  let backendUrl = localStorage.getItem('devmind_backend') || DEFAULT_BACKEND;
  let projectId  = localStorage.getItem('devmind_project') || generateId();

  // ── State ─────────────────────────────────────────────
  let ws          = null;
  let wsConnected = false;
  let reconnectTimer = null;
  let reconnectAttempts = 0;

  // DOM refs
  // ws:// for http://, wss:// for https:// (required on Render HTTPS)
  const wsUrl = () => backendUrl.replace(/^https/, 'wss').replace(/^http(?!s)/, 'ws') + `/ws/${projectId}`;

  // ── Bootstrap ─────────────────────────────────────────
  function init() {
    // On cloud/Render deployment: if stored backendUrl is localhost but current
    // origin is different, clear the stale URL so we use window.location.origin
    const storedBackend = localStorage.getItem('devmind_backend');
    if (storedBackend && storedBackend.includes('localhost') && !window.location.hostname.includes('localhost')) {
      localStorage.removeItem('devmind_backend');
      backendUrl = DEFAULT_BACKEND;
    }

    // Save project id
    localStorage.setItem('devmind_project', projectId);

    // Update header
    updateProjectHeader();

    // Init modules
    Logs.init();
    Preview.init(projectId, backendUrl);
    Editor.init(null); // ws set after connect

    Chat.init((userMessage) => {
      sendChat(userMessage);
    });

    // Tab switching
    initTabs();

    // Panel resize
    initResize();

    // Modals
    initSettings();
    initNewProject();

    // Project name click → rename
    document.getElementById('project-name-display')?.addEventListener('dblclick', promptRename);

    // Connect WebSocket
    connectWS();
  }

  // ══════════════════════════════════════════════════════
  //  WEBSOCKET
  // ══════════════════════════════════════════════════════
  function connectWS() {
    if (ws) {
      try { ws.close(); } catch (_) {}
    }

    setAiStatus('connecting', 'Connecting…');
    Logs.add('info', `🔌 Connecting to ${backendUrl}…`);

    ws = new WebSocket(wsUrl());
    Editor.setWs(ws);

    ws.onopen = () => {
      wsConnected = true;
      reconnectAttempts = 0;
      setAiStatus('ready', 'AI Ready');
      setWsDot('connected');
      Logs.add('success', '✅ Connected to DevMind backend');
    };

    ws.onmessage = (event) => {
      let data;
      try { data = JSON.parse(event.data); } catch { return; }
      handleServerMessage(data);
    };

    ws.onerror = () => {
      Logs.add('error', '❌ WebSocket error — check if the backend is running');
    };

    ws.onclose = () => {
      wsConnected = false;
      setAiStatus('error', 'Disconnected');
      setWsDot('error');
      Logs.add('warning', '⚠️ Connection lost. Reconnecting…');
      scheduleReconnect();
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    const delay = Math.min(2000 * Math.pow(1.5, reconnectAttempts), 20000);
    reconnectAttempts++;
    reconnectTimer = setTimeout(connectWS, delay);
  }

  function sendChat(message) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      Chat.setTyping(false);
      Chat.addSystemMessage('⚠️ Not connected to backend. Please check your settings.', 'error');
      Logs.add('error', 'Cannot send — WebSocket not connected');
      return;
    }
    ws.send(JSON.stringify({ type: 'chat', message }));
    Logs.add('info', `📤 User: ${message.substring(0, 80)}${message.length > 80 ? '…' : ''}`);
  }

  // ══════════════════════════════════════════════════════
  //  SERVER MESSAGE HANDLER
  // ══════════════════════════════════════════════════════
  function handleServerMessage(data) {
    const { type } = data;

    switch (type) {
      case 'init':
        _files = data.files || [];
        Logs.add('success', `Project "${data.project_name}" loaded (${_files.length} files)`);
        Editor.setFiles(_files);
        Preview.updateProjectId(data.project_id || projectId);
        if (data.project_name) updateProjectName(data.project_name);
          if (data.project_id) updateProjectId(data.project_id);

          if (!data.gemini_configured) {
            Chat.addSystemMessage(
              '⚠️ Gemini API key not configured. Click the gear icon (⚙️) to add your key.',
              'warning'
            );
            Logs.add('warning', 'Gemini API key not set — open Settings to configure');
          }

          if (_files.some(f => f.path === 'index.html')) {
            switchTab('preview');
            Preview.show();
          }
          break;

      case 'message':
        Chat.setTyping(false);
        Chat.addMessage('assistant', data.content, {
          files_updated: data.files_updated || 0,
        });

        if (data.files_updated > 0) {
          // Auto-switch to preview after code generation
          setTimeout(() => {
            switchTab('preview');
            Preview.show();
            Preview.reload();
          }, 600);
        }
        break;

      case 'status':
        if (data.status === 'thinking') {
          setAiStatus('thinking', data.label || 'Thinking…');
          setWsDot('thinking');
          Chat.setTypingLabel(data.label || 'Thinking…');
        } else {
          setAiStatus('ready', 'AI Ready');
          setWsDot('connected');
        }
        break;

      case 'file_update':
        Editor.setFiles(updateFileInList(data.path));
        Editor.onFileUpdate(data.path, data.content || '');
        break;

      case 'file_delete':
        Editor.onFileDelete(data.path);
        break;

      case 'files_list':
          _files = data.files || [];
          Editor.setFiles(_files);
        break;

      case 'file_content':
        Editor.loadFileContent(data.path, data.content || '');
        break;

      case 'log':
        Logs.add(data.level || 'info', data.message);
        break;

      case 'project_renamed':
        updateProjectName(data.name);
        break;

      case 'error':
        Logs.add('error', data.message);
        Chat.setTyping(false);
        break;

      default:
        break;
    }
  }

  // ── File list helpers ─────────────────────────────────
  let _files = [];

  function updateFileInList(path) {
    if (!_files.find(f => f.path === path)) {
      _files.push({ path, size: 0, extension: path.split('.').pop() });
    }
    return _files;
  }

  // ══════════════════════════════════════════════════════
  //  TAB SWITCHING
  // ══════════════════════════════════════════════════════
  function initTabs() {
    document.querySelectorAll('.ws-tab').forEach(tab => {
      tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });
  }

  function switchTab(tabId) {
    document.querySelectorAll('.ws-tab').forEach(t => {
      t.classList.toggle('active', t.dataset.tab === tabId);
    });
    document.querySelectorAll('.ws-content').forEach(c => {
      c.classList.toggle('active', c.id === `tab-${tabId}`);
    });

    if (tabId === 'logs') Logs.setTabActive(true);
    else                  Logs.setTabActive(false);
  }

  // ══════════════════════════════════════════════════════
  //  PANEL RESIZE
  // ══════════════════════════════════════════════════════
  function initResize() {
    const handle    = document.getElementById('resize-handle');
    const chatPanel = document.getElementById('chat-panel');
    if (!handle || !chatPanel) return;

    let dragging = false;
    let startX   = 0;
    let startW   = 0;

    handle.addEventListener('mousedown', (e) => {
      dragging = true;
      startX   = e.clientX;
      startW   = chatPanel.offsetWidth;
      handle.classList.add('dragging');
      document.body.style.userSelect = 'none';
      document.body.style.cursor     = 'col-resize';
    });

    document.addEventListener('mousemove', (e) => {
      if (!dragging) return;
      const dx  = e.clientX - startX;
      const newW = Math.min(Math.max(startW + dx, 260), window.innerWidth * 0.55);
      chatPanel.style.width = newW + 'px';
    });

    document.addEventListener('mouseup', () => {
      if (dragging) {
        dragging = false;
        handle.classList.remove('dragging');
        document.body.style.userSelect = '';
        document.body.style.cursor     = '';
        // Save width preference
        localStorage.setItem('devmind_chat_w', chatPanel.offsetWidth);
      }
    });

    // Restore saved width
    const savedW = localStorage.getItem('devmind_chat_w');
    if (savedW) chatPanel.style.width = savedW + 'px';
  }

  // ══════════════════════════════════════════════════════
  //  SETTINGS MODAL
  // ══════════════════════════════════════════════════════
  function initSettings() {
    const modal      = document.getElementById('settings-modal');
    const settingsBtn = document.getElementById('settings-btn');
    const closeBtn   = document.getElementById('close-settings-btn');
    const apiInput   = document.getElementById('api-key-input');
    const apiSaveBtn = document.getElementById('save-api-key-btn');
    const urlInput   = document.getElementById('backend-url-input');
    const urlSaveBtn = document.getElementById('save-backend-url-btn');
    const statusEl   = document.getElementById('api-key-status');

    settingsBtn?.addEventListener('click', () => {
      modal.style.display = 'flex';
      if (urlInput) urlInput.value = backendUrl;
    });

    closeBtn?.addEventListener('click', () => modal.style.display = 'none');
    modal?.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });

    apiSaveBtn?.addEventListener('click', async () => {
      const key = apiInput?.value.trim();
      if (!key) return;

      try {
        const res = await fetch(`${backendUrl}/api/settings/api-key`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key }),
        });
        const json = await res.json();

        if (json.configured) {
          showSettingsStatus(statusEl, 'ok', '✅ API key saved and verified!');
          Logs.add('success', '🔑 Gemini API key configured');
          setAiStatus('ready', 'AI Ready');
        } else {
          showSettingsStatus(statusEl, 'error', '❌ Key saved but Gemini config failed');
        }
      } catch (e) {
        showSettingsStatus(statusEl, 'error', `❌ Could not reach backend: ${e.message}`);
      }
    });

    urlSaveBtn?.addEventListener('click', () => {
      const url = urlInput?.value.trim();
      if (!url) return;
      backendUrl = url;
      localStorage.setItem('devmind_backend', url);
      Preview.updateBackendUrl(url);
      Logs.add('info', `Backend URL updated → ${url}`);
      connectWS();
      modal.style.display = 'none';
    });
  }

  function showSettingsStatus(el, type, msg) {
    if (!el) return;
    el.className = `settings-status ${type}`;
    el.textContent = msg;
    setTimeout(() => { el.className = 'settings-status'; }, 4000);
  }

  // ══════════════════════════════════════════════════════
  //  NEW PROJECT MODAL
  // ══════════════════════════════════════════════════════
  function initNewProject() {
    const modal      = document.getElementById('new-project-modal');
    const newProjBtn = document.getElementById('new-project-btn');
    const closeBtn   = document.getElementById('close-new-project-btn');
    const nameInput  = document.getElementById('new-project-name');
    const createBtn  = document.getElementById('create-project-btn');

    newProjBtn?.addEventListener('click', () => {
      if (nameInput) nameInput.value = '';
      modal.style.display = 'flex';
      setTimeout(() => nameInput?.focus(), 100);
    });

    closeBtn?.addEventListener('click', () => modal.style.display = 'none');
    modal?.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });

    nameInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') createProject();
    });

    createBtn?.addEventListener('click', createProject);

    async function createProject() {
      const name = nameInput?.value.trim() || `Project ${generateId()}`;
      try {
        const res = await fetch(`${backendUrl}/api/projects`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name }),
        });
        const json = await res.json();
        modal.style.display = 'none';

        // Switch to new project
        projectId = json.id;
        localStorage.setItem('devmind_project', projectId);
        updateProjectHeader(name);
        Editor.setFiles([]);
        Chat.clearChat();
        Logs.clear();
        Preview.updateProjectId(projectId);
        connectWS();

        Logs.add('success', `🆕 Created project "${name}" (${json.id})`);
      } catch (e) {
        Logs.add('error', `Failed to create project: ${e.message}`);
      }
    }
  }

  // ══════════════════════════════════════════════════════
  //  HEADER HELPERS
  // ══════════════════════════════════════════════════════
  function updateProjectHeader(name = null) {
    const nameEl = document.getElementById('project-name-display');
    const idEl   = document.getElementById('project-id-display');
    if (nameEl && name) nameEl.textContent = name;
    if (idEl)           idEl.textContent   = `#${projectId}`;
  }

  function updateProjectName(name) {
    const nameEl = document.getElementById('project-name-display');
    if (nameEl) nameEl.textContent = name;
  }

  function updateProjectId(id) {
    projectId = id;
    localStorage.setItem('devmind_project', id);
    const idEl = document.getElementById('project-id-display');
    if (idEl) idEl.textContent = `#${id}`;
    Preview.updateProjectId(id);
  }

  function promptRename() {
    const nameEl = document.getElementById('project-name-display');
    const current = nameEl?.textContent || 'My Project';
    const newName = prompt('Rename project:', current);
    if (!newName || !newName.trim()) return;
    ws?.send(JSON.stringify({ type: 'rename_project', name: newName.trim() }));
    updateProjectName(newName.trim());
  }

  function setAiStatus(type, label) {
    const pill = document.getElementById('ai-status-pill');
    const text = document.getElementById('ai-status-text');
    if (!pill) return;
    pill.className = `ai-status-pill ${type}`;
    if (text) text.textContent = label;
  }

  function setWsDot(state) {
    const dot = document.getElementById('ws-dot');
    if (!dot) return;
    dot.className = `project-status-dot ${state}`;
  }

  // ── Utils ─────────────────────────────────────────────
  function generateId() {
    return Math.random().toString(36).substring(2, 10);
  }

  return { init };
})();

// ── Bootstrap on DOM ready ────────────────────────────
document.addEventListener('DOMContentLoaded', () => App.init());
