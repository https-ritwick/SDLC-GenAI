/**
 * DevMind Studio — Editor Module
 * Manages the file explorer tree and CodeMirror code editor.
 */

const Editor = (() => {
  // ── State ─────────────────────────────────────────────
  let cmInstance  = null;
  let files       = [];
  let openTabs    = [];   // [{path, content, modified}]
  let activeTab   = null; // path
  let ws          = null; // WebSocket reference (set by app.js)

  // DOM refs
  let treeBody    = null;
  let tabBar      = null;
  let editorBody  = null;
  let emptyState  = null;
  let statusBar   = null;
  let sbLang      = null;
  let sbPath      = null;
  let sbModified  = null;
  let saveBtn     = null;

  // ── File type → language ──────────────────────────────
  const EXT_LANG = {
    html: 'htmlmixed', htm: 'htmlmixed',
    css: 'css', scss: 'css', sass: 'css', less: 'css',
    js: 'javascript', mjs: 'javascript', cjs: 'javascript',
    jsx: 'jsx',
    ts: 'javascript', tsx: 'javascript',
    json: 'javascript', jsonc: 'javascript',
    py: 'python',
    md: 'markdown', markdown: 'markdown',
    xml: 'xml', svg: 'xml',
    go: 'go',
    rs: 'rust',
    sh: 'shell', bash: 'shell', zsh: 'shell',
    yml: 'yaml', yaml: 'yaml',
    dockerfile: 'dockerfile',
    txt: 'text/plain',
    env: 'shell',
    toml: 'text/plain',
    php: 'htmlmixed',
    rb: 'text/plain',
    java: 'text/plain',
    kt: 'text/plain',
    swift: 'text/plain',
    c: 'text/plain', cpp: 'text/plain', h: 'text/plain',
    cs: 'text/plain',
    sql: 'text/plain',
    graphql: 'text/plain', gql: 'text/plain',
    vue: 'htmlmixed',
    svelte: 'htmlmixed',
  };

  const EXT_ICON = {
    html: '🌐', htm: '🌐',
    css: '🎨', scss: '🎨', sass: '🎨', less: '🎨',
    js: '⚡', mjs: '⚡', cjs: '⚡',
    jsx: '⚛️',
    ts: '🔷', tsx: '🔷',
    json: '📦', jsonc: '📦',
    md: '📝', markdown: '📝',
    py: '🐍',
    go: '🐹',
    rs: '🦀',
    sh: '🖥️', bash: '🖥️', zsh: '🖥️',
    yml: '⚙️', yaml: '⚙️',
    dockerfile: '🐳',
    env: '🔑',
    toml: '⚙️',
    php: '🐘',
    rb: '💎',
    java: '☕',
    kt: '🎯',
    swift: '🍎',
    sql: '🗄️',
    graphql: '🔮', gql: '🔮',
    vue: '💚',
    svelte: '🔥',
    png: '🖼️', jpg: '🖼️', jpeg: '🖼️', gif: '🖼️', svg: '🎭', webp: '🖼️',
    txt: '📄', xml: '📄',
    lock: '🔒',
  };

  // ── Init ───────────────────────────────────────────────
  function init(wsRef) {
    ws = wsRef;

    treeBody   = document.getElementById('file-tree-body');
    tabBar     = document.getElementById('editor-tab-bar');
    editorBody = document.getElementById('editor-body');
    emptyState = document.getElementById('editor-empty-state');
    statusBar  = document.getElementById('editor-statusbar');
    sbLang     = document.getElementById('sb-lang');
    sbPath     = document.getElementById('sb-path');
    sbModified = document.getElementById('sb-modified');
    saveBtn    = document.getElementById('sb-save-btn');

    // Init CodeMirror on the textarea
    const textarea = document.getElementById('cm-textarea');
    if (textarea && window.CodeMirror) {
      cmInstance = CodeMirror.fromTextArea(textarea, {
        theme:           'dracula',
        lineNumbers:     true,
        matchBrackets:   true,
        autoCloseBrackets: true,
        indentUnit:      2,
        tabSize:         2,
        indentWithTabs:  false,
        lineWrapping:    false,
        extraKeys: {
          'Ctrl-S':    () => saveActiveFile(),
          'Cmd-S':     () => saveActiveFile(),
          'Tab':       (cm) => {
            if (cm.somethingSelected()) cm.indentSelection('add');
            else cm.replaceSelection('  ', 'end');
          },
        },
      });

      // Mark as modified on change
      cmInstance.on('change', () => {
        if (activeTab) markModified(activeTab);
      });

      // Initially hidden
      cmInstance.getWrapperElement().style.display = 'none';
    }

    // New file button
    const newFileBtn = document.getElementById('new-file-btn');
    if (newFileBtn) {
      newFileBtn.addEventListener('click', promptNewFile);
    }

    // Save button
    if (saveBtn) {
      saveBtn.addEventListener('click', saveActiveFile);
    }
  }

  // ── File list updates ─────────────────────────────────
  function setFiles(fileList) {
    files = fileList || [];
    renderTree();
  }

  function onFileUpdate(path, content) {
    // Update in-memory tab if open
    const tab = openTabs.find(t => t.path === path);
    if (tab) {
      if (tab.path === activeTab && !tab.modified) {
        // Refresh editor content only if not locally modified
        cmInstance.setValue(content);
        cmInstance.clearHistory();
        tab.content = content;
      } else if (tab.path !== activeTab) {
        tab.content = content;
      }
    }
  }

  function onFileDelete(path) {
    closeTab(path);
    files = files.filter(f => f.path !== path);
    renderTree();
  }

  // ── File tree rendering ───────────────────────────────
  function renderTree() {
    if (!treeBody) return;

    if (!files || files.length === 0) {
      treeBody.innerHTML = `
        <div class="file-tree-empty-state">
          <p>No files yet</p>
          <p class="hint">Chat with DevMind to start building</p>
        </div>`;
      return;
    }

    const tree = buildTree(files.map(f => f.path));
    treeBody.innerHTML = '';
    renderNode(tree, treeBody, '');
  }

  function buildTree(paths) {
    const root = {};
    paths.forEach(p => {
      const parts = p.split('/');
      let node = root;
      parts.forEach((part, i) => {
        if (i === parts.length - 1) {
          node[part] = null; // file
        } else {
          node[part] = node[part] || {};
        }
        node = node[part] || {};
      });
    });
    return root;
  }

  function renderNode(node, parent, prefix) {
    // Sort: folders first, then files alphabetically
    const entries = Object.entries(node).sort((a, b) => {
      const aIsDir = a[1] !== null;
      const bIsDir = b[1] !== null;
      if (aIsDir !== bIsDir) return aIsDir ? -1 : 1;
      return a[0].localeCompare(b[0]);
    });

    entries.forEach(([name, children]) => {
      const fullPath = prefix ? `${prefix}/${name}` : name;
      const isDir    = children !== null && typeof children === 'object';

      if (isDir) {
        // Folder
        const folderEl = document.createElement('div');
        folderEl.className = 'ft-folder open';
        folderEl.innerHTML = `
          <div class="ft-folder-header no-select">
            <svg class="ft-folder-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M1 4a1 1 0 0 1 1-1h4l1.5 2H14a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H2a1 1 0 0 1-1-1V4z"/>
            </svg>
            <span>${escHtml(name)}</span>
            <svg class="ft-chevron" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M6 4l4 4-4 4"/>
            </svg>
          </div>
          <div class="ft-folder-children"></div>
        `;

        folderEl.querySelector('.ft-folder-header').addEventListener('click', () => {
          folderEl.classList.toggle('open');
        });

        renderNode(children, folderEl.querySelector('.ft-folder-children'), fullPath);
        parent.appendChild(folderEl);

      } else {
        // File
        const ext  = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
        const icon = EXT_ICON[ext] || '📄';

        const fileEl = document.createElement('div');
        fileEl.className = 'ft-file';
        if (activeTab === fullPath) fileEl.classList.add('active');
        fileEl.dataset.path = fullPath;
        fileEl.innerHTML = `
          <span class="ft-file-icon">${icon}</span>
          <span class="ft-file-name">${escHtml(name)}</span>
        `;
        fileEl.addEventListener('click', () => openFile(fullPath));
        parent.appendChild(fileEl);
      }
    });
  }

  // ── Open / close files ────────────────────────────────
  function openFile(path) {
    // Check if already open
    if (openTabs.find(t => t.path === path)) {
      switchTab(path);
      return;
    }

    // Request content via WebSocket
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'get_file', path }));
    }

    // Optimistic: open empty tab while loading
    openTabs.push({ path, content: '', modified: false });
    switchTab(path);
    Logs.add('info', `📂 Opened ${path}`);
  }

  function loadFileContent(path, content) {
    const tab = openTabs.find(t => t.path === path);
    if (tab) {
      tab.content = content;
      if (activeTab === path) {
        const ext  = path.split('.').pop().toLowerCase();
        const mode = EXT_LANG[ext] || 'text/plain';
        if (cmInstance) {
          cmInstance.setOption('mode', mode);
          cmInstance.setValue(content);
          cmInstance.clearHistory();
        }
      }
    }
  }

  function switchTab(path) {
    activeTab = path;
    const tab = openTabs.find(t => t.path === path);

    // Update file tree selection
    document.querySelectorAll('.ft-file').forEach(el => {
      el.classList.toggle('active', el.dataset.path === path);
    });

    // Show editor, hide empty state
    if (emptyState) emptyState.style.display = 'none';
    if (cmInstance) {
      const wrapEl = cmInstance.getWrapperElement();
      wrapEl.style.display = 'block';
      wrapEl.style.height  = '100%';

      const ext  = path.split('.').pop().toLowerCase();
      const mode = EXT_LANG[ext] || 'text/plain';
      cmInstance.setOption('mode', mode);
      cmInstance.setValue(tab ? tab.content : '');
      cmInstance.clearHistory();
      setTimeout(() => cmInstance.refresh(), 50);
    }

    // Status bar
    if (statusBar)  statusBar.style.display = 'flex';
    if (sbPath)     sbPath.textContent = path;
    if (sbLang) {
      const ext = path.split('.').pop().toLowerCase();
      const LANG_LABELS = {
        htmlmixed: 'HTML', javascript: 'JS', jsx: 'JSX',
        css: 'CSS', python: 'Python', go: 'Go',
        rust: 'Rust', shell: 'Shell', yaml: 'YAML',
        dockerfile: 'Dockerfile', markdown: 'Markdown',
        xml: 'XML', 'text/plain': ext.toUpperCase() || '—',
      };
      const mode = EXT_LANG[ext] || 'text/plain';
      sbLang.textContent = LANG_LABELS[mode] || ext.toUpperCase() || '—';
    }
    if (sbModified) sbModified.style.display = (tab && tab.modified) ? 'inline' : 'none';

    renderTabs();
  }

  function closeTab(path) {
    openTabs = openTabs.filter(t => t.path !== path);
    if (activeTab === path) {
      activeTab = openTabs.length > 0 ? openTabs[openTabs.length - 1].path : null;
      if (activeTab) switchTab(activeTab);
      else showEmptyState();
    }
    renderTabs();
  }

  function markModified(path) {
    const tab = openTabs.find(t => t.path === path);
    if (tab && !tab.modified) {
      tab.modified = true;
      renderTabs();
      if (sbModified) sbModified.style.display = 'inline';
    }
  }

  function showEmptyState() {
    if (emptyState) emptyState.style.display = 'flex';
    if (cmInstance)  cmInstance.getWrapperElement().style.display = 'none';
    if (statusBar)   statusBar.style.display = 'none';
  }

  // ── Tab bar rendering ─────────────────────────────────
  function renderTabs() {
    if (!tabBar) return;
    tabBar.innerHTML = '';
    openTabs.forEach(tab => {
      const name = tab.path.split('/').pop();
      const ext  = name.includes('.') ? name.split('.').pop().toLowerCase() : '';
      const icon = EXT_ICON[ext] || '📄';

      const el = document.createElement('div');
      el.className = 'editor-tab' + (tab.path === activeTab ? ' active' : '');
      el.innerHTML = `
        <span>${icon}</span>
        <span>${escHtml(name)}</span>
        ${tab.modified ? '<span style="color:var(--warning);font-size:9px;margin-left:-4px">●</span>' : ''}
        <button class="tab-close" title="Close">✕</button>
      `;
      el.addEventListener('click', (e) => {
        if (!e.target.classList.contains('tab-close')) switchTab(tab.path);
      });
      el.querySelector('.tab-close').addEventListener('click', (e) => {
        e.stopPropagation();
        closeTab(tab.path);
      });
      tabBar.appendChild(el);
    });
  }

  // ── Save ──────────────────────────────────────────────
  function saveActiveFile() {
    if (!activeTab || !cmInstance) return;
    const content = cmInstance.getValue();
    const tab = openTabs.find(t => t.path === activeTab);
    if (tab) {
      tab.content  = content;
      tab.modified = false;
    }
    renderTabs();
    if (sbModified) sbModified.style.display = 'none';

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'save_file', path: activeTab, content }));
    }
  }

  // ── New file ──────────────────────────────────────────
  function promptNewFile() {
    const name = prompt('New file name (e.g. app.js, css/theme.css):');
    if (!name || !name.trim()) return;
    const path = name.trim().replace(/^\/+/, '');
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'save_file', path, content: '' }));
    }
    // Optimistic
    openTabs.push({ path, content: '', modified: false });
    switchTab(path);
    files.push({ path, size: 0, extension: path.split('.').pop() });
    renderTree();
  }

  // ── Helpers ───────────────────────────────────────────
  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function setWs(wsRef) { ws = wsRef; }

  return {
    init,
    setFiles,
    setWs,
    openFile,
    loadFileContent,
    onFileUpdate,
    onFileDelete,
    renderTree,
    saveActiveFile,
  };
})();