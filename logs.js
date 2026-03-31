/**
 * DevMind Studio — Logs Module
 * Manages the terminal-style logs panel.
 */

const Logs = (() => {
  let container = null;
  let badgeEl   = null;
  let allLogs   = [];
  let activeFilter = 'all';
  let unreadCount  = 0;
  let isLogsTabActive = false;

  const LEVEL_MAP = {
    info:    { label: 'INFO',    cls: 'info' },
    success: { label: 'SUCCESS', cls: 'success' },
    warning: { label: 'WARN',   cls: 'warning' },
    error:   { label: 'ERROR',  cls: 'error' },
  };

  function init() {
    container = document.getElementById('logs-terminal');
    badgeEl   = document.getElementById('log-badge');

    // Filter buttons
    document.querySelectorAll('.log-filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.log-filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeFilter = btn.dataset.filter;
        renderAll();
      });
    });

    // Clear button
    const clearBtn = document.getElementById('clear-logs-btn');
    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        allLogs = [];
        renderAll();
        setBadge(0);
      });
    }

    add('info', '🚀 DevMind Studio initialized');
  }

  /** Add a new log entry */
  function add(level, message) {
    const now  = new Date();
    const time = now.toLocaleTimeString('en-GB', { hour12: false });
    const entry = { level: level || 'info', message: String(message), time };
    allLogs.push(entry);

    // Limit to 1000 entries
    if (allLogs.length > 1000) allLogs.shift();

    if (activeFilter === 'all' || activeFilter === level) {
      appendEntry(entry);
      scrollToBottom();
    }

    // Badge
    if (!isLogsTabActive) {
      unreadCount++;
      setBadge(unreadCount);
    }
  }

  function appendEntry(entry) {
    if (!container) return;
    const meta  = LEVEL_MAP[entry.level] || LEVEL_MAP.info;
    const el    = document.createElement('div');
    el.className = `log-entry ${meta.cls}`;
    el.dataset.level = entry.level;

    el.innerHTML = `
      <span class="log-ts">${entry.time}</span>
      <span class="log-lvl">${meta.label}</span>
      <span class="log-msg">${escHtml(entry.message)}</span>
    `;
    container.appendChild(el);
  }

  function renderAll() {
    if (!container) return;
    container.innerHTML = '';
    allLogs
      .filter(e => activeFilter === 'all' || e.level === activeFilter)
      .forEach(appendEntry);
    scrollToBottom();
  }

  function scrollToBottom() {
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }

  function setBadge(count) {
    if (!badgeEl) return;
    if (count > 0) {
      badgeEl.style.display = 'flex';
      badgeEl.textContent   = count > 99 ? '99+' : String(count);
    } else {
      badgeEl.style.display = 'none';
    }
  }

  function setTabActive(active) {
    isLogsTabActive = active;
    if (active) {
      unreadCount = 0;
      setBadge(0);
      scrollToBottom();
    }
  }

  function clear() {
    allLogs = [];
    renderAll();
    setBadge(0);
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  return { init, add, clear, setTabActive };
})();
