(function () {
  'use strict';

  const urlInput = document.getElementById('url-input');
  if (!urlInput) return;  // Not on main page

  const urlWrap      = document.getElementById('url-wrap');
  const urlFeedback  = document.getElementById('url-feedback');
  const formatPanel  = document.getElementById('format-panel');
  const formatList   = document.getElementById('format-list');
  const videoMeta    = document.getElementById('video-meta');
  const downloadBtn  = document.getElementById('download-btn');
  const downloadText = document.getElementById('download-btn-text');
  const hiddenFormat = document.getElementById('selected-format-id');

  let debounceTimer = null;
  let selectedFormatId = '';

  // ── URL input handler ────────────────────────────────────────────────────
  urlInput.addEventListener('input', function () {
    clearTimeout(debounceTimer);
    const url = urlInput.value.trim();

    if (!url) {
      reset();
      return;
    }

    debounceTimer = setTimeout(() => fetchVideoInfo(url), 600);
  });

  // ── Fetch video info ─────────────────────────────────────────────────────
  async function fetchVideoInfo(url) {
    setLoading(true);

    try {
      const resp = await fetch('/ajax/video-info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await resp.json();

      if (!data.success) {
        setError(data.error || 'Could not load video info');
        return;
      }

      renderVideoInfo(data);
    } catch {
      setError('Network error — please check your connection');
    } finally {
      setLoading(false);
    }
  }

  // ── Render video info + format list ─────────────────────────────────────
  function renderVideoInfo(data) {
    // Reset selection state from any previous URL
    selectedFormatId = '';
    hiddenFormat.value = '';

    urlWrap.classList.remove('invalid');
    urlWrap.classList.add('valid');
    urlFeedback.textContent = '✓ ' + data.extractor;
    urlFeedback.className = 'url-feedback ok';

    // Thumbnail / meta
    const thumbHtml = data.thumbnail
      ? '<img class="video-thumb" src="' + esc(data.thumbnail) + '" alt="" loading="lazy">'
      : '<div class="video-thumb-placeholder">🎬</div>';

    const dur = data.duration ? formatDuration(data.duration) : '';
    videoMeta.innerHTML =
      thumbHtml +
      '<div class="video-meta-info">' +
        '<div class="video-title">' + esc(data.title) + '</div>' +
        '<div class="video-sub">' + (dur ? dur + ' \xB7 ' : '') + esc(data.extractor) + '</div>' +
        '<span class="platform-badge">' + esc(data.extractor) + '</span>' +
      '</div>';

    // Format list
    formatList.innerHTML = '';

    data.formats.forEach(function (fmt, i) {
      const sizeText = fmt.filesize_approx ? '~' + humanSize(fmt.filesize_approx) : '';
      const bestBadge = fmt.is_best ? '<span class="best-badge">BEST</span>' : '';
      const codecText = fmt.label === 'Audio only'
        ? 'MP3 \xB7 audio extracted'
        : 'MP4 \xB7 ' + (fmt.vcodec ? fmt.vcodec.split('.')[0] : '');

      const item = document.createElement('div');
      item.className = 'format-item' + (fmt.is_best ? ' selected' : '');
      item.dataset.formatId = fmt.format_id;
      item.innerHTML =
        '<div class="format-radio"></div>' +
        '<div class="format-info">' +
          '<div class="format-label">' + esc(fmt.label) + bestBadge + '</div>' +
          '<div class="format-codec">' + codecText + '</div>' +
        '</div>' +
        '<div class="format-size">' + sizeText + '</div>';

      item.addEventListener('click', function () { selectFormat(item, fmt); });
      formatList.appendChild(item);

      if (fmt.is_best) {
        selectFormat(item, fmt);
      }
    });

    // Fallback: select first format if nothing marked best
    if (!selectedFormatId && data.formats.length > 0) {
      var firstItem = formatList.querySelector('.format-item');
      selectFormat(firstItem, data.formats[0]);
    }

    formatPanel.classList.add('visible');
    enableDownload();
  }

  function selectFormat(item, fmt) {
    formatList.querySelectorAll('.format-item').forEach(function (el) {
      el.classList.remove('selected');
    });
    item.classList.add('selected');
    selectedFormatId = fmt.format_id;
    hiddenFormat.value = fmt.format_id;

    const sizeText = fmt.filesize_approx ? ' \xB7 ~' + humanSize(fmt.filesize_approx) : '';
    downloadText.textContent = 'Download ' + fmt.label + sizeText;
  }

  // ── States ───────────────────────────────────────────────────────────────
  function reset() {
    urlWrap.classList.remove('valid', 'invalid');
    urlFeedback.textContent = '';
    urlFeedback.className = 'url-feedback';
    formatPanel.classList.remove('visible');
    formatList.innerHTML = '';
    videoMeta.innerHTML = '';
    selectedFormatId = '';
    hiddenFormat.value = '';
    downloadBtn.disabled = true;
    downloadText.textContent = 'Download';
  }

  function setLoading(on) {
    if (on) {
      urlWrap.classList.remove('valid', 'invalid');
      urlFeedback.className = 'url-feedback';
      urlFeedback.innerHTML = '<div class="spinner" style="width:14px;height:14px;display:inline-block;vertical-align:middle;margin-right:6px;"></div> Fetching video info…';
      downloadBtn.disabled = true;
      formatPanel.classList.remove('visible');
    }
  }

  function setError(msg) {
    urlWrap.classList.remove('valid');
    urlWrap.classList.add('invalid');
    urlFeedback.textContent = '✗ ' + msg;
    urlFeedback.className = 'url-feedback err';
    formatPanel.classList.remove('visible');
    downloadBtn.disabled = true;
    downloadText.textContent = 'Download';
  }

  function enableDownload() {
    downloadBtn.disabled = false;
  }

  // ── Download form submit ─────────────────────────────────────────────────
  document.getElementById('download-form').addEventListener('submit', function () {
    downloadBtn.disabled = true;
    downloadBtn.innerHTML = '<div class="spinner"></div><span>Downloading…</span>';
    setTimeout(function () {
      downloadBtn.disabled = false;
      downloadBtn.innerHTML = '<span>⬇</span><span id="download-btn-text">Download again</span>';
    }, 15000);
  });

  // ── Helpers ──────────────────────────────────────────────────────────────
  function esc(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function humanSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + ' MB';
    return (bytes / 1024 / 1024 / 1024).toFixed(1) + ' GB';
  }

  function formatDuration(secs) {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    if (h > 0) return h + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
    return m + ':' + String(s).padStart(2, '0');
  }

})();
