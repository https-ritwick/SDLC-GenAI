/**
 * DevMind Studio — Preview Module
 * Manages the live preview iframe and device modes.
 */

const Preview = (() => {
  let iframe      = null;
  let frameWrap   = null;
  let emptyState  = null;
  let urlDisplay  = null;
  let projectId   = null;
  let backendUrl  = 'http://localhost:8000';
  let currentDevice = 'desktop';

  function init(pid, bUrl) {
    projectId  = pid;
    backendUrl = bUrl || backendUrl;

    iframe     = document.getElementById('preview-iframe');
    frameWrap  = document.getElementById('preview-frame-wrap');
    emptyState = document.getElementById('preview-empty-state');
    urlDisplay = document.getElementById('preview-url-display');

    // Device buttons
    document.querySelectorAll('.dev-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.dev-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        setDevice(btn.dataset.device);
      });
    });

    // Refresh button
    const refreshBtn = document.getElementById('refresh-preview-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', reload);

    // Open in new tab
    const openBtn = document.getElementById('open-in-new-btn');
    if (openBtn) {
      openBtn.addEventListener('click', () => {
        if (projectId) window.open(previewUrl(), '_blank');
      });
    }
  }

  function previewUrl() {
    // Trailing slash is critical: without it, relative CSS/JS in index.html
    // resolves to /preview/styles.css instead of /preview/{id}/styles.css
    return `${backendUrl}/preview/${projectId}/`;
  }

  function show() {
    if (!projectId) return;
    const url = previewUrl();

    // Update URL bar
    if (urlDisplay) {
      urlDisplay.textContent = `localhost:${new URL(backendUrl).port || 80}/preview/${projectId}/`;
    }

    // Show iframe, hide empty state
    if (emptyState) emptyState.style.display = 'none';
    if (frameWrap)  frameWrap.style.display  = 'flex';

    // Load the preview
    if (iframe && iframe.src !== url) {
      iframe.src = url;
    }

    setDevice(currentDevice);
  }

  function reload() {
    if (!projectId) return;
    if (iframe) {
      const url = previewUrl();
      // Force reload by resetting src
      iframe.src = 'about:blank';
      setTimeout(() => { iframe.src = url; }, 80);
    }
    Logs.add('info', '🔄 Preview refreshed');
  }

  function setDevice(device) {
    currentDevice = device;
    if (!frameWrap) return;

    frameWrap.classList.remove('device-desktop', 'device-tablet', 'device-mobile');
    frameWrap.classList.add(`device-${device}`);

    const scaleEl = document.getElementById('preview-scale');
    const scales  = { desktop: '100%', tablet: '768px', mobile: '390px' };
    if (scaleEl) scaleEl.textContent = scales[device] || '100%';
  }

  function updateProjectId(pid) {
    projectId = pid;
  }

  function updateBackendUrl(url) {
    backendUrl = url;
  }

  return { init, show, reload, updateProjectId, updateBackendUrl };
})();