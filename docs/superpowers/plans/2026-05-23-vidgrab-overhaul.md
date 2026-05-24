# VidGrab Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the existing Flask video downloader into a polished, Docker-ready app with Gradient Hero UI, format/resolution picker, universal yt-dlp downloads, auto-starting Telegram bot, and a password-protected admin panel with 7-day auto-deletion.

**Architecture:** Incremental refactor — keep Flask, replace platform-specific downloaders with a single yt-dlp-backed `download_video()`, add background threads for bot + cleanup at module load, add admin routes with session auth, and ship a Dockerfile + docker-compose.yml for Linux deployment.

**Tech Stack:** Python 3.11, Flask 3.x, yt-dlp (subprocess), python-telegram-bot, gunicorn, pytest, Docker + Docker Compose

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `utils/downloader.py` | Rewrite | Universal download_video(), get_video_info(), remove all platform funcs |
| `utils/cleanup.py` | Create | Background thread that deletes files older than 7 days |
| `app.py` | Rewrite | All routes, background service startup, context processor |
| `telegram_bot.py` | Rewrite | Thread-safe runner, any-URL support |
| `templates/layout.html` | Rewrite | Gradient Hero base, nav, footer |
| `templates/index.html` | Rewrite | Hero, format picker panel, Telegram card |
| `templates/admin_login.html` | Create | Login form |
| `templates/admin.html` | Create | File table, stats, delete actions |
| `static/css/custom.css` | Rewrite | Gradient Hero design system |
| `static/js/script.js` | Rewrite | Format picker AJAX flow, download form |
| `tests/conftest.py` | Create | pytest fixtures, Flask test client |
| `tests/test_downloader.py` | Create | Tests for get_video_info, download_video |
| `tests/test_cleanup.py` | Create | Tests for cleanup thread logic |
| `tests/test_app.py` | Create | Tests for all Flask routes |
| `Dockerfile` | Create | Python 3.11-slim + ffmpeg + yt-dlp |
| `docker-compose.yml` | Create | Single service, .env, volume mount |
| `.env.example` | Create | Token, secret key, admin password |
| `.gitignore` | Update | Add .env, downloads/, cert.pem, key.pem |

---

## Task 1: Project Setup

**Files:**
- Update: `.gitignore`
- Create: `.env.example`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `pyproject.toml` (add pytest config)

- [ ] **Step 1.1: Update .gitignore**

Edit `.gitignore` to add:
```
.env
downloads/
cert.pem
key.pem
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 1.2: Create .env.example**

Create `.env.example`:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_BOT_USERNAME=YourBotName
SECRET_KEY=change_me_to_a_long_random_string
ADMIN_PASSWORD=change_me_to_a_strong_password
```

- [ ] **Step 1.3: Create tests/__init__.py**

Create `tests/__init__.py` as an empty file.

- [ ] **Step 1.4: Create tests/conftest.py**

```python
import os
import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('ADMIN_PASSWORD', 'testpass123')
os.environ['TESTING'] = '1'


@pytest.fixture
def app(tmp_path):
    from app import app as flask_app
    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'DOWNLOAD_FOLDER': str(tmp_path),
    })
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as sess:
        sess['admin'] = True
    return client
```

- [ ] **Step 1.5: Add pytest config to pyproject.toml**

Open `pyproject.toml` and add at the end:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
```

- [ ] **Step 1.6: Install pytest**

```bash
pip install pytest
```

- [ ] **Step 1.7: Verify pytest runs (no tests yet)**

```bash
pytest --collect-only
```
Expected output: `no tests ran` or empty collection — no errors.

- [ ] **Step 1.8: Commit**

```bash
git add .gitignore .env.example tests/ pyproject.toml
git commit -m "chore: add test infrastructure and project setup"
```

---

## Task 2: Rewrite utils/downloader.py (TDD)

**Files:**
- Rewrite: `utils/downloader.py`
- Create: `tests/test_downloader.py`

- [ ] **Step 2.1: Write failing tests**

Create `tests/test_downloader.py`:
```python
import json
import os
import pytest
from unittest.mock import patch, MagicMock


# ── get_video_info ──────────────────────────────────────────────────────────

MOCK_YTDLP_JSON = {
    'title': 'Test Video',
    'thumbnail': 'https://example.com/thumb.jpg',
    'duration': 213,
    'extractor_key': 'Youtube',
    'formats': [
        {
            'format_id': '137',
            'vcodec': 'avc1.640028',
            'acodec': 'none',
            'height': 1080,
            'width': 1920,
            'ext': 'mp4',
            'filesize': 120_000_000,
            'tbr': None,
        },
        {
            'format_id': '136',
            'vcodec': 'avc1.4d401f',
            'acodec': 'none',
            'height': 720,
            'width': 1280,
            'ext': 'mp4',
            'filesize': 55_000_000,
            'tbr': None,
        },
        {
            'format_id': '140',
            'vcodec': 'none',
            'acodec': 'mp4a.40.2',
            'height': None,
            'width': None,
            'ext': 'webm',
            'filesize': 3_500_000,
            'tbr': None,
        },
    ],
}


def _mock_run(returncode=0, stdout='', stderr=''):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


def test_get_video_info_returns_title_and_formats():
    mock_result = _mock_run(stdout=json.dumps(MOCK_YTDLP_JSON))
    with patch('subprocess.run', return_value=mock_result):
        from utils.downloader import get_video_info
        info = get_video_info('https://youtube.com/watch?v=test')

    assert info['title'] == 'Test Video'
    assert info['thumbnail'] == 'https://example.com/thumb.jpg'
    assert info['duration'] == 213
    assert info['extractor'] == 'Youtube'


def test_get_video_info_formats_sorted_best_first():
    mock_result = _mock_run(stdout=json.dumps(MOCK_YTDLP_JSON))
    with patch('subprocess.run', return_value=mock_result):
        from utils.downloader import get_video_info
        info = get_video_info('https://youtube.com/watch?v=test')

    video_formats = [f for f in info['formats'] if f['label'] != 'Audio only']
    assert video_formats[0]['label'] == '1080p'
    assert video_formats[1]['label'] == '720p'


def test_get_video_info_includes_audio_only():
    mock_result = _mock_run(stdout=json.dumps(MOCK_YTDLP_JSON))
    with patch('subprocess.run', return_value=mock_result):
        from utils.downloader import get_video_info
        info = get_video_info('https://youtube.com/watch?v=test')

    audio = next((f for f in info['formats'] if f['label'] == 'Audio only'), None)
    assert audio is not None
    assert audio['ext'] == 'mp3'
    assert audio['format_id'].endswith('+audio_only')


def test_get_video_info_marks_best_format():
    mock_result = _mock_run(stdout=json.dumps(MOCK_YTDLP_JSON))
    with patch('subprocess.run', return_value=mock_result):
        from utils.downloader import get_video_info
        info = get_video_info('https://youtube.com/watch?v=test')

    best = [f for f in info['formats'] if f.get('is_best')]
    assert len(best) == 1
    # Best should be ≤1080p (highest quality at or below 1080)
    assert best[0]['label'] == '1080p'


def test_get_video_info_raises_on_yt_dlp_failure():
    mock_result = _mock_run(returncode=1, stderr='Unsupported URL: example.com')
    with patch('subprocess.run', return_value=mock_result):
        from utils.downloader import get_video_info
        with pytest.raises(RuntimeError, match='Unsupported URL'):
            get_video_info('https://invalid.example.com/video')


def test_get_video_info_raises_on_timeout():
    import subprocess
    with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('yt-dlp', 30)):
        from utils.downloader import get_video_info
        with pytest.raises(RuntimeError, match='Timed out'):
            get_video_info('https://youtube.com/watch?v=test')


def test_get_video_info_estimates_size_from_bitrate():
    data = dict(MOCK_YTDLP_JSON)
    data['formats'] = [
        {
            'format_id': '22',
            'vcodec': 'avc1',
            'acodec': 'mp4a',
            'height': 720,
            'width': 1280,
            'ext': 'mp4',
            'filesize': None,
            'filesize_approx': None,
            'tbr': 2500,  # kbps
        },
    ]
    mock_result = _mock_run(stdout=json.dumps(data))
    with patch('subprocess.run', return_value=mock_result):
        from utils.downloader import get_video_info
        info = get_video_info('https://youtube.com/watch?v=test')

    fmt = next(f for f in info['formats'] if f['label'] == '720p')
    # size = 2500 * 1000 / 8 * 213 ≈ 66 562 500 bytes
    assert fmt['filesize_approx'] is not None
    assert fmt['filesize_approx'] > 0


# ── download_video ───────────────────────────────────────────────────────────

def test_download_video_success(tmp_path):
    timestamp = '2026-01-01_00-00-00'
    fake_file = tmp_path / f'Test_Video_{timestamp}.mp4'
    fake_file.write_bytes(b'fake content')

    mock_result = _mock_run()
    with patch('subprocess.run', return_value=mock_result), \
         patch('utils.downloader.datetime') as mock_dt:
        mock_dt.now.return_value.strftime.return_value = timestamp
        from utils.downloader import download_video
        result = download_video('https://youtube.com/watch?v=test', str(tmp_path))

    assert result['success'] is True
    assert timestamp in result['filename']


def test_download_video_failure(tmp_path):
    mock_result = _mock_run(returncode=1, stderr='ERROR: Unsupported URL')
    with patch('subprocess.run', return_value=mock_result):
        from utils.downloader import download_video
        result = download_video('https://invalid.example.com', str(tmp_path))

    assert result['success'] is False
    assert 'Unsupported URL' in result['error']


def test_download_video_audio_only_uses_x_flag(tmp_path):
    timestamp = '2026-01-01_00-00-00'
    fake_file = tmp_path / f'song_{timestamp}.mp3'
    fake_file.write_bytes(b'fake audio')

    captured = {}

    def capture_run(cmd, **kwargs):
        captured['cmd'] = cmd
        return _mock_run()

    with patch('subprocess.run', side_effect=capture_run), \
         patch('utils.downloader.datetime') as mock_dt:
        mock_dt.now.return_value.strftime.return_value = timestamp
        from utils.downloader import download_video
        download_video('https://youtube.com/watch?v=test', str(tmp_path),
                       format_id='140+audio_only')

    assert '-x' in captured['cmd']
    assert '--audio-format' in captured['cmd']
    assert 'mp3' in captured['cmd']


def test_download_video_with_format_id(tmp_path):
    timestamp = '2026-01-01_00-00-00'
    fake_file = tmp_path / f'vid_{timestamp}.mp4'
    fake_file.write_bytes(b'fake video')

    captured = {}

    def capture_run(cmd, **kwargs):
        captured['cmd'] = cmd
        return _mock_run()

    with patch('subprocess.run', side_effect=capture_run), \
         patch('utils.downloader.datetime') as mock_dt:
        mock_dt.now.return_value.strftime.return_value = timestamp
        from utils.downloader import download_video
        download_video('https://youtube.com/watch?v=test', str(tmp_path),
                       format_id='137')

    assert '-f' in captured['cmd']
    idx = captured['cmd'].index('-f')
    assert captured['cmd'][idx + 1] == '137'


# ── is_valid_url ─────────────────────────────────────────────────────────────

def test_is_valid_url_accepts_http():
    from utils.downloader import is_valid_url
    assert is_valid_url('https://youtube.com/watch?v=abc') is True


def test_is_valid_url_rejects_bare_string():
    from utils.downloader import is_valid_url
    assert is_valid_url('not a url') is False
```

- [ ] **Step 2.2: Run tests — verify all fail**

```bash
pytest tests/test_downloader.py -v 2>&1 | head -40
```
Expected: multiple FAILED or ImportError (functions don't exist yet).

- [ ] **Step 2.3: Rewrite utils/downloader.py**

Replace the entire file:
```python
import json
import logging
import os
import re
import subprocess
import urllib.parse
from datetime import datetime

logger = logging.getLogger(__name__)


def is_valid_url(url):
    try:
        r = urllib.parse.urlparse(url)
        return bool(r.scheme and r.netloc)
    except ValueError:
        return False


def get_platform(url):
    """Return a display-friendly platform name, or 'Unknown' for unrecognised URLs."""
    u = url.lower()
    if any(d in u for d in ('youtube.com', 'youtu.be')):
        return 'YouTube'
    if 'instagram.com' in u:
        return 'Instagram'
    if any(d in u for d in ('twitter.com', 'x.com')):
        return 'Twitter / X'
    if 'tiktok.com' in u:
        return 'TikTok'
    if any(d in u for d in ('facebook.com', 'fb.com', 'fb.watch')):
        return 'Facebook'
    if 'reddit.com' in u:
        return 'Reddit'
    if 'vimeo.com' in u:
        return 'Vimeo'
    return 'Unknown'


def get_video_info(url):
    """Fetch video metadata via yt-dlp --dump-json.

    Returns a dict with title, thumbnail, duration, extractor, formats.
    Raises RuntimeError if yt-dlp fails or times out.
    """
    try:
        result = subprocess.run(
            ['yt-dlp', '--dump-json', '--no-playlist', url],
            capture_output=True,
            text=True,
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError('Timed out fetching video info — the URL may be slow or unsupported')

    if result.returncode != 0:
        msg = result.stderr.strip() or 'yt-dlp returned an error'
        raise RuntimeError(msg)

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError('Could not parse video info from yt-dlp')

    return _parse_info(data)


def _parse_info(data):
    duration = data.get('duration', 0) or 0
    formats = []
    seen_heights = set()

    # Collect distinct video formats, best height first
    for f in sorted(data.get('formats', []), key=lambda x: x.get('height') or 0, reverse=True):
        height = f.get('height')
        vcodec = f.get('vcodec', 'none')
        if not height or vcodec == 'none':
            continue
        label = f'{height}p'
        if label in seen_heights:
            continue
        seen_heights.add(label)

        size = f.get('filesize') or f.get('filesize_approx')
        if not size:
            tbr = f.get('tbr') or 0
            size = int(tbr * 1000 / 8 * duration) if tbr and duration else None

        formats.append({
            'format_id': f['format_id'],
            'label': label,
            'resolution': f'{f.get("width", "?")}×{height}',
            'ext': 'mp4',
            'vcodec': vcodec,
            'acodec': f.get('acodec', ''),
            'filesize_approx': size,
            'is_best': False,
        })

    # Pick best audio-only stream
    best_audio = max(
        (f for f in data.get('formats', [])
         if f.get('vcodec') == 'none' and f.get('acodec', 'none') != 'none'),
        key=lambda f: f.get('filesize') or f.get('filesize_approx') or 0,
        default=None,
    )
    if best_audio:
        a_size = best_audio.get('filesize') or best_audio.get('filesize_approx')
        formats.append({
            'format_id': f'{best_audio["format_id"]}+audio_only',
            'label': 'Audio only',
            'resolution': 'MP3',
            'ext': 'mp3',
            'vcodec': 'none',
            'acodec': best_audio.get('acodec', ''),
            'filesize_approx': a_size,
            'is_best': False,
        })

    # Mark best video format (highest quality ≤ 1080p; fall back to highest available)
    video_fmts = [f for f in formats if f['label'] != 'Audio only']
    if video_fmts:
        preferred = next((f for f in video_fmts
                          if int(f['label'].replace('p', '')) <= 1080), video_fmts[0])
        preferred['is_best'] = True

    return {
        'title': data.get('title', 'Unknown'),
        'thumbnail': data.get('thumbnail', ''),
        'duration': duration,
        'extractor': data.get('extractor_key') or data.get('extractor', 'Unknown'),
        'formats': formats,
    }


def download_video(url, folder, format_id=None):
    """Download any yt-dlp-supported URL.

    Returns {'success': True, 'filename': str, 'path': str}
         or {'success': False, 'error': str}.
    """
    os.makedirs(folder, exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    output_template = os.path.join(folder, f'%(title)s_{timestamp}.%(ext)s')

    is_audio_only = isinstance(format_id, str) and format_id.endswith('+audio_only')
    raw_format_id = format_id.replace('+audio_only', '') if is_audio_only else format_id

    if is_audio_only:
        cmd = [
            'yt-dlp',
            '-f', raw_format_id,
            '-x', '--audio-format', 'mp3',
            '--no-playlist',
            '-o', output_template,
            url,
        ]
    elif format_id:
        cmd = [
            'yt-dlp',
            '-f', format_id,
            '--merge-output-format', 'mp4',
            '--no-playlist',
            '-o', output_template,
            url,
        ]
    else:
        cmd = [
            'yt-dlp',
            '-f', 'bestvideo+bestaudio/best',
            '--merge-output-format', 'mp4',
            '--no-playlist',
            '-o', output_template,
            url,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        error = result.stderr.strip() or 'Download failed'
        logger.error('yt-dlp error: %s', error)
        return {'success': False, 'error': error}

    # Find the file written in this download (contains the timestamp)
    try:
        files = sorted(
            [f for f in os.listdir(folder) if timestamp in f],
            key=lambda f: os.path.getmtime(os.path.join(folder, f)),
            reverse=True,
        )
    except OSError:
        files = []

    if not files:
        return {'success': False, 'error': 'File not found after download'}

    filename = files[0]
    return {
        'success': True,
        'filename': filename,
        'path': os.path.join(folder, filename),
    }
```

- [ ] **Step 2.4: Run tests — verify they pass**

```bash
pytest tests/test_downloader.py -v
```
Expected: all tests PASS.

- [ ] **Step 2.5: Commit**

```bash
git add utils/downloader.py tests/test_downloader.py
git commit -m "feat: universal yt-dlp downloader with format picker support"
```

---

## Task 3: Create utils/cleanup.py (TDD)

**Files:**
- Create: `utils/cleanup.py`
- Create: `tests/test_cleanup.py`

- [ ] **Step 3.1: Write failing tests**

Create `tests/test_cleanup.py`:
```python
import os
import time
import pytest
from unittest.mock import patch


def _make_file(path, age_days):
    path.write_bytes(b'x')
    mtime = time.time() - age_days * 86400
    os.utime(str(path), (mtime, mtime))


def test_delete_files_older_than_7_days(tmp_path):
    old_file = tmp_path / 'old.mp4'
    new_file = tmp_path / 'new.mp4'
    _make_file(old_file, 8)   # 8 days old — should be deleted
    _make_file(new_file, 3)   # 3 days old — should survive

    from utils.cleanup import delete_expired_files
    deleted = delete_expired_files(str(tmp_path))

    assert not old_file.exists()
    assert new_file.exists()
    assert 'old.mp4' in deleted


def test_exactly_7_days_survives(tmp_path):
    border_file = tmp_path / 'border.mp4'
    _make_file(border_file, 7)  # exactly 7 days — boundary is > 7 days, so survives

    from utils.cleanup import delete_expired_files
    deleted = delete_expired_files(str(tmp_path))

    assert border_file.exists()
    assert 'border.mp4' not in deleted


def test_empty_folder_no_error(tmp_path):
    from utils.cleanup import delete_expired_files
    deleted = delete_expired_files(str(tmp_path))
    assert deleted == []


def test_missing_folder_no_error():
    from utils.cleanup import delete_expired_files
    deleted = delete_expired_files('/nonexistent/path/xyz')
    assert deleted == []


def test_start_cleanup_thread_returns_thread(tmp_path):
    import threading
    from utils.cleanup import start_cleanup_thread
    t = start_cleanup_thread(str(tmp_path), interval_seconds=9999)
    assert isinstance(t, threading.Thread)
    assert t.daemon is True
```

- [ ] **Step 3.2: Run tests — verify they fail**

```bash
pytest tests/test_cleanup.py -v 2>&1 | head -20
```
Expected: ImportError or FAILED.

- [ ] **Step 3.3: Create utils/cleanup.py**

```python
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

EXPIRY_DAYS = 7


def delete_expired_files(folder, expiry_days=EXPIRY_DAYS):
    """Delete files in folder older than expiry_days. Returns list of deleted filenames."""
    if not os.path.isdir(folder):
        return []

    deleted = []
    cutoff = time.time() - expiry_days * 86400

    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if not os.path.isfile(filepath):
            continue
        try:
            if os.path.getmtime(filepath) < cutoff:
                os.remove(filepath)
                deleted.append(filename)
                logger.info('Auto-deleted expired file: %s', filename)
        except OSError as e:
            logger.warning('Could not delete %s: %s', filepath, e)

    return deleted


def start_cleanup_thread(folder, interval_seconds=3600):
    """Start a daemon thread that runs delete_expired_files every interval_seconds."""

    def _loop():
        while True:
            delete_expired_files(folder)
            time.sleep(interval_seconds)

    t = threading.Thread(target=_loop, daemon=True, name='cleanup-thread')
    t.start()
    return t
```

- [ ] **Step 3.4: Run tests — verify they pass**

```bash
pytest tests/test_cleanup.py -v
```
Expected: all PASS.

- [ ] **Step 3.5: Commit**

```bash
git add utils/cleanup.py tests/test_cleanup.py
git commit -m "feat: auto-cleanup thread deletes downloads older than 7 days"
```

---

## Task 4: Rewrite app.py — All Routes (TDD)

**Files:**
- Rewrite: `app.py`
- Create: `tests/test_app.py`

- [ ] **Step 4.1: Write failing tests**

Create `tests/test_app.py`:
```python
import json
import os
import pytest
from unittest.mock import patch, MagicMock


# ── helpers ──────────────────────────────────────────────────────────────────

def _mock_info():
    return {
        'title': 'Test Video',
        'thumbnail': 'https://example.com/thumb.jpg',
        'duration': 120,
        'extractor': 'Youtube',
        'formats': [
            {'format_id': '137', 'label': '1080p', 'resolution': '1920×1080',
             'ext': 'mp4', 'vcodec': 'avc1', 'acodec': 'none',
             'filesize_approx': 100_000_000, 'is_best': True},
            {'format_id': '140+audio_only', 'label': 'Audio only', 'resolution': 'MP3',
             'ext': 'mp3', 'vcodec': 'none', 'acodec': 'mp4a',
             'filesize_approx': 3_500_000, 'is_best': False},
        ],
    }


# ── index ─────────────────────────────────────────────────────────────────────

def test_index_returns_200(client):
    resp = client.get('/')
    assert resp.status_code == 200


# ── /ajax/video-info ─────────────────────────────────────────────────────────

def test_video_info_success(client):
    with patch('utils.downloader.get_video_info', return_value=_mock_info()):
        resp = client.post('/ajax/video-info',
                           json={'url': 'https://youtube.com/watch?v=test'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['title'] == 'Test Video'
    assert len(data['formats']) == 2


def test_video_info_missing_url(client):
    resp = client.post('/ajax/video-info', json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['success'] is False


def test_video_info_invalid_url(client):
    resp = client.post('/ajax/video-info', json={'url': 'not a url'})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data['success'] is False


def test_video_info_yt_dlp_error(client):
    with patch('utils.downloader.get_video_info', side_effect=RuntimeError('Unsupported URL')):
        resp = client.post('/ajax/video-info',
                           json={'url': 'https://unsupported.example.com/video'})
    assert resp.status_code == 422
    data = resp.get_json()
    assert data['success'] is False
    assert 'Unsupported URL' in data['error']


# ── /download ─────────────────────────────────────────────────────────────────

def test_download_success(client, tmp_path):
    fake_file = tmp_path / 'video_2026-01-01_00-00-00.mp4'
    fake_file.write_bytes(b'fake video content')

    with patch('utils.downloader.download_video', return_value={
        'success': True,
        'filename': fake_file.name,
        'path': str(fake_file),
    }), patch('app.DOWNLOAD_FOLDER', str(tmp_path)):
        resp = client.post('/download', data={
            'url': 'https://youtube.com/watch?v=test',
            'format_id': '137',
        })

    assert resp.status_code == 200
    assert resp.headers['Content-Disposition']


def test_download_missing_url(client):
    resp = client.post('/download', data={'url': ''})
    assert resp.status_code == 302  # redirect back to index


def test_download_invalid_url(client):
    resp = client.post('/download', data={'url': 'not a url'})
    assert resp.status_code == 302


def test_download_failure_redirects(client):
    with patch('utils.downloader.download_video', return_value={
        'success': False, 'error': 'Network error',
    }):
        resp = client.post('/download', data={
            'url': 'https://youtube.com/watch?v=test',
        })
    assert resp.status_code == 302


# ── /admin/login ─────────────────────────────────────────────────────────────

def test_admin_login_page_returns_200(client):
    resp = client.get('/admin/login')
    assert resp.status_code == 200


def test_admin_redirects_to_login_when_not_authenticated(client):
    resp = client.get('/admin')
    assert resp.status_code == 302
    assert '/admin/login' in resp.headers['Location']


def test_admin_login_correct_password(client):
    resp = client.post('/admin/login', data={'password': 'testpass123'},
                       follow_redirects=False)
    assert resp.status_code == 302
    assert '/admin' in resp.headers['Location']


def test_admin_login_wrong_password(client):
    resp = client.post('/admin/login', data={'password': 'wrongpass'})
    assert resp.status_code == 200
    assert b'Invalid' in resp.data


# ── /admin ────────────────────────────────────────────────────────────────────

def test_admin_page_authenticated(admin_client, tmp_path):
    with patch('app.DOWNLOAD_FOLDER', str(tmp_path)):
        resp = admin_client.get('/admin')
    assert resp.status_code == 200


def test_admin_delete_file(admin_client, tmp_path):
    target = tmp_path / 'to_delete.mp4'
    target.write_bytes(b'x')
    with patch('app.DOWNLOAD_FOLDER', str(tmp_path)):
        resp = admin_client.post('/admin/delete',
                                  json={'filename': 'to_delete.mp4'})
    assert resp.status_code == 200
    assert not target.exists()


def test_admin_delete_rejects_path_traversal(admin_client, tmp_path):
    with patch('app.DOWNLOAD_FOLDER', str(tmp_path)):
        resp = admin_client.post('/admin/delete',
                                  json={'filename': '../secret.txt'})
    assert resp.status_code == 400


def test_admin_delete_all(admin_client, tmp_path):
    (tmp_path / 'a.mp4').write_bytes(b'x')
    (tmp_path / 'b.mp4').write_bytes(b'x')
    with patch('app.DOWNLOAD_FOLDER', str(tmp_path)):
        resp = admin_client.post('/admin/delete-all')
    assert resp.status_code == 200
    assert list(tmp_path.iterdir()) == []


def test_admin_logout_clears_session(admin_client):
    resp = admin_client.get('/admin/logout', follow_redirects=False)
    assert resp.status_code == 302
    # After logout, /admin should redirect to login
    resp2 = admin_client.get('/admin', follow_redirects=False)
    assert resp2.status_code == 302
```

- [ ] **Step 4.2: Run tests — verify they fail**

```bash
pytest tests/test_app.py -v 2>&1 | head -30
```
Expected: mostly FAILED (routes don't exist yet).

- [ ] **Step 4.3: Rewrite app.py**

Replace entire file:
```python
import logging
import os
import threading
import time
from datetime import datetime, timezone

from flask import (Flask, flash, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)

from utils.downloader import download_video, get_video_info, is_valid_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-me')

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


# ── context processor ────────────────────────────────────────────────────────

@app.context_processor
def inject_globals():
    bot_username = os.environ.get('TELEGRAM_BOT_USERNAME', 'YourBot')
    bot_active = bool(os.environ.get('TELEGRAM_BOT_TOKEN'))
    return {'bot_active': bot_active, 'bot_username': bot_username}


# ── main page ────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ── video info (AJAX) ────────────────────────────────────────────────────────

@app.route('/ajax/video-info', methods=['POST'])
def video_info():
    url = (request.json or {}).get('url', '').strip()
    if not url:
        return jsonify({'success': False, 'error': 'URL is required'}), 400
    if not is_valid_url(url):
        return jsonify({'success': False, 'error': 'Invalid URL'}), 400
    try:
        info = get_video_info(url)
        return jsonify({'success': True, **info})
    except RuntimeError as e:
        return jsonify({'success': False, 'error': str(e)}), 422


# ── download ─────────────────────────────────────────────────────────────────

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url', '').strip()
    format_id = request.form.get('format_id', '').strip() or None

    if not url:
        flash('Please enter a video URL', 'danger')
        return redirect(url_for('index'))

    if not is_valid_url(url):
        flash('Invalid URL format', 'danger')
        return redirect(url_for('index'))

    try:
        result = download_video(url, DOWNLOAD_FOLDER, format_id=format_id)
        if result['success']:
            return send_from_directory(
                DOWNLOAD_FOLDER,
                result['filename'],
                as_attachment=True,
                download_name=result['filename'],
            )
        flash(f'Download failed: {result["error"]}', 'danger')
    except Exception:
        logger.exception('Unexpected error during download')
        flash('An unexpected error occurred. Please try again.', 'danger')

    return redirect(url_for('index'))


# ── admin — login / logout ───────────────────────────────────────────────────

def _require_admin():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    return None


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        expected = os.environ.get('ADMIN_PASSWORD', '')
        if expected and password == expected:
            session['admin'] = True
            return redirect(url_for('admin_panel'))
        return render_template('admin_login.html', error='Invalid password')
    return render_template('admin_login.html', error=None)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))


# ── admin — panel ─────────────────────────────────────────────────────────────

def _file_list():
    """Return list of dicts describing files in DOWNLOAD_FOLDER."""
    files = []
    now = time.time()
    for name in os.listdir(DOWNLOAD_FOLDER):
        path = os.path.join(DOWNLOAD_FOLDER, name)
        if not os.path.isfile(path):
            continue
        mtime = os.path.getmtime(path)
        size = os.path.getsize(path)
        expiry_ts = mtime + 7 * 86400
        remaining_secs = expiry_ts - now
        files.append({
            'filename': name,
            'size': size,
            'size_human': _human_size(size),
            'mtime': mtime,
            'age_human': _human_age(now - mtime),
            'expiry_secs': remaining_secs,
            'expiry_human': _human_age(remaining_secs) if remaining_secs > 0 else 'Expired',
            'expiring_soon': remaining_secs < 86400,
        })
    files.sort(key=lambda f: f['mtime'], reverse=True)
    return files


def _human_size(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f'{n:.1f} {unit}'
        n /= 1024
    return f'{n:.1f} TB'


def _human_age(secs):
    secs = abs(int(secs))
    if secs < 60:
        return f'{secs}s'
    if secs < 3600:
        return f'{secs // 60}m'
    if secs < 86400:
        h, m = divmod(secs, 3600)
        return f'{h}h {m // 60}m'
    d, rem = divmod(secs, 86400)
    return f'{d}d {rem // 3600}h'


@app.route('/admin')
def admin_panel():
    redir = _require_admin()
    if redir:
        return redir
    files = _file_list()
    total_size = sum(f['size'] for f in files)
    expiring_count = sum(1 for f in files if f['expiring_soon'])
    return render_template(
        'admin.html',
        files=files,
        total_size=_human_size(total_size),
        expiring_count=expiring_count,
    )


@app.route('/admin/delete', methods=['POST'])
def admin_delete():
    redir = _require_admin()
    if redir:
        return redir, 401

    filename = (request.json or {}).get('filename', '')
    # Prevent path traversal
    if not filename or os.sep in filename or filename.startswith('.'):
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400

    path = os.path.join(DOWNLOAD_FOLDER, filename)
    if not os.path.isfile(path):
        return jsonify({'success': False, 'error': 'File not found'}), 404

    os.remove(path)
    return jsonify({'success': True})


@app.route('/admin/delete-all', methods=['POST'])
def admin_delete_all():
    redir = _require_admin()
    if redir:
        return redir, 401

    for name in os.listdir(DOWNLOAD_FOLDER):
        path = os.path.join(DOWNLOAD_FOLDER, name)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass

    return jsonify({'success': True})


# ── background services ───────────────────────────────────────────────────────

_services_started = False
_services_lock = threading.Lock()


def _start_background_services():
    global _services_started
    with _services_lock:
        if _services_started:
            return
        _services_started = True

    from utils.cleanup import start_cleanup_thread
    start_cleanup_thread(DOWNLOAD_FOLDER)
    logger.info('Cleanup thread started')

    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if token:
        try:
            from telegram_bot import run_bot_thread
            run_bot_thread()
            logger.info('Telegram bot thread started')
        except Exception:
            logger.exception('Failed to start Telegram bot thread')


# Start background services unless in test mode or Flask reloader parent process
if os.environ.get('TESTING') != '1':
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        _start_background_services()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

- [ ] **Step 4.4: Run tests — verify they pass**

```bash
pytest tests/test_app.py -v
```
Expected: all PASS.

- [ ] **Step 4.5: Run full test suite**

```bash
pytest -v
```
Expected: all tests PASS.

- [ ] **Step 4.6: Commit**

```bash
git add app.py tests/test_app.py
git commit -m "feat: new routes — format picker, admin panel, universal download"
```

---

## Task 5: Rewrite telegram_bot.py

**Files:**
- Rewrite: `telegram_bot.py`

- [ ] **Step 5.1: Rewrite telegram_bot.py**

Replace entire file:
```python
import logging
import os
import threading
import time

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from utils.downloader import download_video, get_platform, is_valid_url

logger = logging.getLogger(__name__)

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
TELEGRAM_MAX_BYTES = 50 * 1024 * 1024  # 50 MB


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '👋 Hi! I\'m VidGrab Bot.\n\n'
        'Send me any video link and I\'ll download it for you.\n\n'
        '⚠️ *Telegram limit: 50 MB per file.* For larger videos, use the web app.',
        parse_mode='Markdown',
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '*How to use:*\n'
        '1. Paste any video URL\n'
        '2. I\'ll download it and send you the file\n\n'
        'Supports YouTube, Instagram, TikTok, Twitter, Reddit, Vimeo, and 1000+ more sites.\n\n'
        '⚠️ *50 MB limit* — larger files must be downloaded via the web app.',
        parse_mode='Markdown',
    )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not is_valid_url(url):
        await update.message.reply_text('❌ That doesn\'t look like a valid URL. Please send a video link.')
        return

    platform = get_platform(url)
    status_msg = await update.message.reply_text(f'⬇️ Downloading from {platform}…')

    start = time.time()
    result = download_video(url, DOWNLOAD_FOLDER)

    if not result['success']:
        await status_msg.edit_text(f'❌ Download failed: {result["error"]}')
        return

    filepath = result['path']
    filesize = os.path.getsize(filepath)

    if filesize > TELEGRAM_MAX_BYTES:
        size_mb = filesize / 1024 / 1024
        await status_msg.edit_text(
            f'⚠️ File is {size_mb:.1f} MB — too large for Telegram (50 MB limit).\n'
            'Please download it from the web app instead.'
        )
        return

    elapsed = time.time() - start
    await status_msg.edit_text('📤 Uploading…')

    try:
        with open(filepath, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=result['filename'],
                caption=f'✅ Done in {elapsed:.1f}s · {filesize / 1024 / 1024:.1f} MB',
            )
        await status_msg.delete()
    except Exception as e:
        logger.exception('Failed to send file via Telegram')
        await status_msg.edit_text(f'❌ Failed to send file: {e}')


def run_bot_thread():
    """Start the Telegram bot in a daemon thread. Safe to call from gunicorn."""
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.warning('TELEGRAM_BOT_TOKEN not set — bot will not start')
        return

    def _run():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_start_bot(token))
        except Exception:
            logger.exception('Telegram bot thread crashed')
        finally:
            loop.close()

    t = threading.Thread(target=_run, daemon=True, name='telegram-bot')
    t.start()
    return t


async def _start_bot(token):
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler('start', cmd_start))
    app.add_handler(CommandHandler('help', cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    logger.info('Telegram bot starting polling')
    await app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    import asyncio
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        print('Set TELEGRAM_BOT_TOKEN environment variable')
    else:
        asyncio.run(_start_bot(token))
```

- [ ] **Step 5.2: Commit**

```bash
git add telegram_bot.py
git commit -m "feat: telegram bot auto-starts as daemon thread, supports any URL"
```

---

## Task 6: Gradient Hero CSS

**Files:**
- Rewrite: `static/css/custom.css`

- [ ] **Step 6.1: Rewrite custom.css**

Replace entire file:
```css
/* ── Reset & base ────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg-1: #1e3a5f;
  --bg-2: #0d1b2a;
  --bg-3: #1a0a2e;
  --accent-1: #ff6b6b;
  --accent-2: #ff8c42;
  --glass-bg: rgba(255,255,255,0.06);
  --glass-border: rgba(255,255,255,0.12);
  --text: #ffffff;
  --text-muted: rgba(255,255,255,0.45);
  --text-dim: rgba(255,255,255,0.25);
  --success: #4ade80;
  --warning: #ffaa00;
  --danger: #ff6b6b;
  --blue: #0088ff;
  --radius: 16px;
  --radius-sm: 10px;
  --shadow: 0 8px 32px rgba(0,0,0,0.4);
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: linear-gradient(160deg, var(--bg-1) 0%, var(--bg-2) 50%, var(--bg-3) 100%);
  min-height: 100vh;
  color: var(--text);
  display: flex;
  flex-direction: column;
}

/* ── Navbar ──────────────────────────────────────────────────────────────── */
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 32px;
  border-bottom: 1px solid var(--glass-border);
  background: rgba(13,27,42,0.6);
  backdrop-filter: blur(12px);
  position: sticky;
  top: 0;
  z-index: 100;
}

.navbar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
}

.brand-icon {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, var(--accent-1), var(--accent-2));
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  box-shadow: 0 4px 12px rgba(255,107,107,0.35);
}

.brand-name {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.5px;
  color: var(--text);
}

.navbar-links {
  display: flex;
  align-items: center;
  gap: 20px;
}

.bot-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.bot-status .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.bot-status.active { color: var(--success); }
.bot-status.active .dot { background: var(--success); box-shadow: 0 0 6px var(--success); }
.bot-status.inactive { color: var(--text-muted); }
.bot-status.inactive .dot { background: var(--text-muted); }

.admin-link {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  padding: 7px 16px;
  color: var(--text-muted);
  font-size: 13px;
  text-decoration: none;
  transition: color 0.2s, border-color 0.2s;
}
.admin-link:hover { color: var(--text); border-color: rgba(255,255,255,0.25); }

/* ── Flash messages ──────────────────────────────────────────────────────── */
.flash-message {
  max-width: 640px;
  margin: 16px auto 0;
  padding: 12px 18px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  border-left: 4px solid;
}
.flash-success { background: rgba(74,222,128,0.1); border-color: var(--success); color: var(--success); }
.flash-danger  { background: rgba(255,107,107,0.1); border-color: var(--danger); color: #ff9f9f; }
.flash-warning { background: rgba(255,170,0,0.1); border-color: var(--warning); color: var(--warning); }

/* ── Main / Hero ─────────────────────────────────────────────────────────── */
main { flex: 1; }

.hero {
  text-align: center;
  padding: 52px 24px 32px;
  max-width: 700px;
  margin: 0 auto;
}

.hero-badge {
  display: inline-block;
  background: rgba(255,107,107,0.15);
  border: 1px solid rgba(255,107,107,0.3);
  border-radius: 20px;
  padding: 5px 16px;
  font-size: 12px;
  color: #ff9f9f;
  letter-spacing: 0.5px;
  margin-bottom: 18px;
}

.hero-title {
  font-size: clamp(28px, 5vw, 42px);
  font-weight: 900;
  line-height: 1.15;
  margin-bottom: 12px;
  letter-spacing: -1px;
}

.hero-title .gradient-text {
  background: linear-gradient(90deg, var(--accent-1), var(--accent-2));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-subtitle {
  color: var(--text-muted);
  font-size: 14px;
  margin-bottom: 36px;
}

/* ── Glass card ──────────────────────────────────────────────────────────── */
.glass-card {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: 20px;
  padding: 24px;
  backdrop-filter: blur(12px);
}

/* ── URL input ───────────────────────────────────────────────────────────── */
.url-input-wrap {
  display: flex;
  align-items: center;
  background: rgba(0,0,0,0.3);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: var(--radius);
  padding: 0 16px;
  height: 52px;
  gap: 10px;
  margin-bottom: 14px;
  transition: border-color 0.2s;
}
.url-input-wrap:focus-within { border-color: rgba(255,107,107,0.5); }
.url-input-wrap.valid   { border-color: rgba(74,222,128,0.4); }
.url-input-wrap.invalid { border-color: rgba(255,107,107,0.4); }

.url-icon { font-size: 18px; opacity: 0.5; flex-shrink: 0; }

#url-input {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  color: var(--text);
  font-size: 14px;
}
#url-input::placeholder { color: var(--text-dim); }

.url-feedback {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 14px;
  min-height: 16px;
  text-align: left;
}
.url-feedback.ok  { color: var(--success); }
.url-feedback.err { color: #ff9f9f; }

/* ── Download button ─────────────────────────────────────────────────────── */
.btn-download {
  width: 100%;
  height: 50px;
  background: linear-gradient(90deg, var(--accent-1), var(--accent-2));
  border: none;
  border-radius: var(--radius);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 6px 24px rgba(255,107,107,0.35);
  transition: transform 0.15s, box-shadow 0.15s;
}
.btn-download:hover { transform: translateY(-1px); box-shadow: 0 10px 32px rgba(255,107,107,0.45); }
.btn-download:active { transform: translateY(0); }
.btn-download:disabled {
  background: rgba(255,255,255,0.08);
  box-shadow: none;
  cursor: not-allowed;
  color: var(--text-dim);
}

/* ── Spinner ─────────────────────────────────────────────────────────────── */
.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255,255,255,0.2);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Format picker ───────────────────────────────────────────────────────── */
#format-panel {
  margin-top: 16px;
  display: none;
}
#format-panel.visible { display: block; }

.video-meta {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.video-thumb {
  width: 96px;
  height: 64px;
  object-fit: cover;
  border-radius: 8px;
  flex-shrink: 0;
  background: rgba(0,0,0,0.3);
}
.video-thumb-placeholder {
  width: 96px;
  height: 64px;
  border-radius: 8px;
  background: rgba(0,0,0,0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  flex-shrink: 0;
}

.video-meta-info { flex: 1; min-width: 0; }
.video-title {
  font-weight: 700;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}
.video-sub { color: var(--text-muted); font-size: 12px; margin-bottom: 6px; }
.platform-badge {
  display: inline-block;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 11px;
  color: var(--text-muted);
}

.formats-label {
  color: var(--text-muted);
  font-size: 10px;
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 10px;
}

.format-list { display: flex; flex-direction: column; gap: 8px; }

.format-item {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.format-item:hover { border-color: rgba(255,107,107,0.3); }
.format-item.selected {
  background: rgba(255,107,107,0.08);
  border-color: rgba(255,107,107,0.4);
}

.format-radio {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(255,255,255,0.2);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.15s;
}
.format-item.selected .format-radio {
  border-color: var(--accent-1);
  background: var(--accent-1);
}
.format-radio::after {
  content: '';
  display: none;
  width: 6px;
  height: 6px;
  background: #fff;
  border-radius: 50%;
}
.format-item.selected .format-radio::after { display: block; }

.format-info { flex: 1; }
.format-label { font-size: 13px; font-weight: 600; }
.format-item.selected .format-label { color: var(--text); }
.format-codec { font-size: 11px; color: var(--text-muted); margin-top: 2px; }

.format-size { font-size: 13px; font-weight: 600; color: var(--text-muted); text-align: right; }
.format-item.selected .format-size { color: #ff9f9f; }

.best-badge {
  background: linear-gradient(90deg, var(--accent-1), var(--accent-2));
  color: #fff;
  font-size: 9px;
  font-weight: 700;
  border-radius: 4px;
  padding: 2px 6px;
  margin-left: 6px;
  vertical-align: middle;
}

/* ── Platform icons row ──────────────────────────────────────────────────── */
.platform-icons {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  margin-top: 24px;
  flex-wrap: wrap;
}

.platform-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  font-size: 13px;
}

/* ── Telegram card ───────────────────────────────────────────────────────── */
.telegram-card {
  max-width: 640px;
  margin: 24px auto 0;
  background: rgba(0,136,255,0.08);
  border: 1px solid rgba(0,136,255,0.2);
  border-radius: 18px;
  padding: 18px 20px;
}

.telegram-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.telegram-icon {
  width: 40px;
  height: 40px;
  background: var(--blue);
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.telegram-title { font-weight: 700; font-size: 15px; }
.telegram-sub { color: var(--text-muted); font-size: 12px; margin-top: 2px; }

.telegram-status {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
}
.telegram-status.active { color: var(--success); }
.telegram-status.active .dot { background: var(--success); box-shadow: 0 0 6px var(--success); }
.telegram-status .dot { width: 7px; height: 7px; border-radius: 50%; }

.btn-telegram {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 44px;
  background: var(--blue);
  border-radius: var(--radius-sm);
  color: #fff;
  text-decoration: none;
  font-weight: 700;
  font-size: 14px;
  margin-bottom: 12px;
  transition: opacity 0.2s;
}
.btn-telegram:hover { opacity: 0.88; }

.warning-banner {
  background: rgba(255,170,0,0.1);
  border: 1px solid rgba(255,170,0,0.3);
  border-radius: 8px;
  padding: 10px 14px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
}
.warning-banner strong { color: var(--warning); }
.warning-banner span { color: var(--text-muted); }

/* ── Footer ──────────────────────────────────────────────────────────────── */
.footer {
  text-align: center;
  padding: 24px;
  border-top: 1px solid var(--glass-border);
  color: var(--text-muted);
  font-size: 12px;
}

/* ── Admin layout ────────────────────────────────────────────────────────── */
.admin-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 32px 24px;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}

.admin-title { font-size: 22px; font-weight: 800; }
.admin-sub { color: var(--text-muted); font-size: 13px; margin-top: 2px; }

.admin-actions { display: flex; gap: 10px; flex-wrap: wrap; }

.btn-outline {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  padding: 8px 18px;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s;
}
.btn-outline:hover { color: var(--text); border-color: rgba(255,255,255,0.25); }

.btn-danger-outline {
  background: rgba(255,107,107,0.08);
  border: 1px solid rgba(255,107,107,0.25);
  border-radius: var(--radius-sm);
  padding: 8px 18px;
  color: #ff9f9f;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-danger-outline:hover { background: rgba(255,107,107,0.15); }

/* ── Stats row ───────────────────────────────────────────────────────────── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius);
  padding: 18px;
}
.stat-card.warn {
  background: rgba(255,170,0,0.07);
  border-color: rgba(255,170,0,0.2);
}

.stat-label {
  color: var(--text-muted);
  font-size: 10px;
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.stat-card.warn .stat-label { color: rgba(255,170,0,0.7); }

.stat-value { font-size: 26px; font-weight: 800; }
.stat-card.warn .stat-value { color: var(--warning); }

/* ── File table ──────────────────────────────────────────────────────────── */
.file-table-wrap {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius);
  overflow: hidden;
}

.file-table-head {
  display: grid;
  grid-template-columns: 1fr 90px 100px 110px 70px;
  gap: 8px;
  padding: 11px 18px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  color: var(--text-muted);
  font-size: 10px;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.file-row {
  display: grid;
  grid-template-columns: 1fr 90px 100px 110px 70px;
  gap: 8px;
  padding: 13px 18px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  align-items: center;
  transition: background 0.15s;
}
.file-row:last-child { border-bottom: none; }
.file-row:hover { background: rgba(255,255,255,0.03); }
.file-row.expiring { background: rgba(255,170,0,0.04); }

.file-name {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.file-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
  background: var(--accent-1);
}
.file-name-text {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-size, .file-age { color: var(--text-muted); font-size: 13px; }

.file-expiry { font-size: 13px; }
.file-expiry.ok { color: var(--success); }
.file-expiry.warn { color: var(--warning); font-weight: 600; }

.btn-delete {
  background: rgba(255,107,107,0.12);
  color: #ff9f9f;
  border: none;
  border-radius: 6px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-delete:hover { background: rgba(255,107,107,0.25); }

.file-table-empty {
  padding: 48px;
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
}

/* ── Admin login ─────────────────────────────────────────────────────────── */
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 80vh;
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 380px;
}

.login-title { font-size: 22px; font-weight: 800; text-align: center; margin-bottom: 6px; }
.login-sub { color: var(--text-muted); text-align: center; font-size: 13px; margin-bottom: 28px; }

.form-label {
  display: block;
  color: var(--text-muted);
  font-size: 11px;
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.form-input {
  width: 100%;
  background: rgba(0,0,0,0.3);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  color: var(--text);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
  margin-bottom: 16px;
}
.form-input:focus { border-color: rgba(255,107,107,0.5); }

.login-error {
  background: rgba(255,107,107,0.1);
  border: 1px solid rgba(255,107,107,0.3);
  border-radius: 8px;
  padding: 10px 14px;
  color: #ff9f9f;
  font-size: 13px;
  margin-bottom: 16px;
  text-align: center;
}

/* ── Responsive ──────────────────────────────────────────────────────────── */
@media (max-width: 600px) {
  .navbar { padding: 12px 16px; }
  .hero { padding: 32px 16px 24px; }
  .stats-row { grid-template-columns: 1fr; }
  .file-table-head,
  .file-row { grid-template-columns: 1fr 70px 80px; }
  .file-table-head > *:nth-child(n+4),
  .file-row > *:nth-child(n+4) { display: none; }
}
```

- [ ] **Step 6.2: Commit**

```bash
git add static/css/custom.css
git commit -m "feat: Gradient Hero CSS design system"
```

---

## Task 7: Base Layout Template

**Files:**
- Rewrite: `templates/layout.html`

- [ ] **Step 7.1: Rewrite layout.html**

Replace entire file:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>VidGrab — Download Any Video</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='css/custom.css') }}">
</head>
<body>

<nav class="navbar">
  <a class="navbar-brand" href="/">
    <div class="brand-icon">⬇</div>
    <span class="brand-name">VidGrab</span>
  </a>
  <div class="navbar-links">
    {% if bot_active %}
      <span class="bot-status active">
        <span class="dot"></span> Bot Active
      </span>
    {% else %}
      <span class="bot-status inactive">
        <span class="dot"></span> Bot Offline
      </span>
    {% endif %}
    <a class="admin-link" href="{{ url_for('admin_panel') }}">⚙ Admin</a>
  </div>
</nav>

<main>
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% for category, message in messages %}
      <div class="flash-message flash-{{ category }}">{{ message }}</div>
    {% endfor %}
  {% endwith %}

  {% block content %}{% endblock %}
</main>

<footer class="footer">
  YouTube · Instagram · TikTok · Twitter · Reddit · Vimeo · and 1000+ more
</footer>

<script src="{{ url_for('static', filename='js/script.js') }}"></script>
</body>
</html>
```

- [ ] **Step 7.2: Commit**

```bash
git add templates/layout.html
git commit -m "feat: Gradient Hero base layout"
```

---

## Task 8: Main Page Template

**Files:**
- Rewrite: `templates/index.html`

- [ ] **Step 8.1: Rewrite index.html**

Replace entire file:
```html
{% extends "layout.html" %}

{% block content %}
<section class="hero">
  <div class="hero-badge">✨ Supports 1000+ websites</div>
  <h1 class="hero-title">
    Download Any Video,<br>
    <span class="gradient-text">Anywhere.</span>
  </h1>
  <p class="hero-subtitle">
    YouTube · Instagram · TikTok · Twitter · Reddit · Vimeo · and thousands more
  </p>

  <!-- Download card -->
  <div class="glass-card" style="max-width:620px;margin:0 auto;">
    <form id="download-form" method="POST" action="/download">
      <!-- URL input -->
      <div class="url-input-wrap" id="url-wrap">
        <span class="url-icon">🔗</span>
        <input
          id="url-input"
          name="url"
          type="url"
          placeholder="Paste any video URL here..."
          autocomplete="off"
          spellcheck="false"
        >
      </div>
      <div class="url-feedback" id="url-feedback"></div>

      <!-- Hidden format id -->
      <input type="hidden" name="format_id" id="selected-format-id" value="">

      <!-- Format picker panel (shown after URL is analysed) -->
      <div id="format-panel">
        <div class="video-meta" id="video-meta"></div>
        <div class="formats-label">Select format &amp; quality</div>
        <div class="format-list" id="format-list"></div>
        <div style="margin-top:14px;"></div>
      </div>

      <!-- Download button -->
      <button type="submit" class="btn-download" id="download-btn" disabled>
        <span>⬇</span>
        <span id="download-btn-text">Download</span>
      </button>
    </form>
  </div>

  <!-- Platform icons -->
  <div class="platform-icons">
    <div class="platform-icon" style="background:#ff0000;" title="YouTube">▶</div>
    <div class="platform-icon" style="background:linear-gradient(45deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888);" title="Instagram"></div>
    <div class="platform-icon" style="background:#000;border:1px solid #333;" title="TikTok">TK</div>
    <div class="platform-icon" style="background:#1da1f2;" title="Twitter">𝕏</div>
    <div class="platform-icon" style="background:#ff4500;" title="Reddit">r/</div>
    <div class="platform-icon" style="background:#1ab7ea;" title="Vimeo">V</div>
    <div class="platform-icon" style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);color:rgba(255,255,255,0.5);" title="1000+ more">+∞</div>
  </div>
</section>

<!-- Telegram bot card -->
{% if bot_active %}
<div class="telegram-card" style="max-width:620px;">
  <div class="telegram-header">
    <div class="telegram-icon">✈</div>
    <div>
      <div class="telegram-title">Download via Telegram Bot</div>
      <div class="telegram-sub">Prefer Telegram? Send links directly to the bot</div>
    </div>
    <div class="telegram-status active">
      <span class="dot"></span> Active
    </div>
  </div>
  <a class="btn-telegram" href="https://t.me/{{ bot_username }}" target="_blank" rel="noopener">
    <span>✈</span>
    <span>Open @{{ bot_username }} on Telegram</span>
  </a>
  <div class="warning-banner">
    <span style="font-size:16px;flex-shrink:0;">⚠️</span>
    <div>
      <strong>50 MB Limit</strong>
      <span> — Telegram bots can only send files up to 50 MB. For larger videos, use the web downloader above.</span>
    </div>
  </div>
</div>
{% else %}
<div class="telegram-card" style="max-width:620px;">
  <div class="telegram-header">
    <div class="telegram-icon" style="background:rgba(0,136,255,0.3);">✈</div>
    <div>
      <div class="telegram-title" style="opacity:0.6;">Telegram Bot</div>
      <div class="telegram-sub">Set TELEGRAM_BOT_TOKEN in .env to enable</div>
    </div>
    <div class="telegram-status inactive">
      <span class="dot" style="background:rgba(255,255,255,0.3);"></span> Offline
    </div>
  </div>
</div>
{% endif %}

<div style="height:48px;"></div>
{% endblock %}
```

- [ ] **Step 8.2: Commit**

```bash
git add templates/index.html
git commit -m "feat: Gradient Hero main page with format picker and Telegram card"
```

---

## Task 9: Admin Templates

**Files:**
- Create: `templates/admin_login.html`
- Create: `templates/admin.html`

- [ ] **Step 9.1: Create admin_login.html**

```html
{% extends "layout.html" %}

{% block content %}
<div class="login-page">
  <div class="glass-card login-card">
    <div class="login-title">⚙ Admin Panel</div>
    <div class="login-sub">Enter your admin password to continue</div>

    {% if error %}
      <div class="login-error">{{ error }}</div>
    {% endif %}

    <form method="POST" action="{{ url_for('admin_login') }}">
      <label class="form-label" for="password">Password</label>
      <input
        class="form-input"
        id="password"
        name="password"
        type="password"
        placeholder="Enter admin password"
        autofocus
      >
      <button type="submit" class="btn-download" style="font-size:14px;">
        Sign In
      </button>
    </form>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 9.2: Create admin.html**

```html
{% extends "layout.html" %}

{% block content %}
<div class="admin-page">
  <div class="admin-header">
    <div>
      <div class="admin-title">⚙ Admin Panel</div>
      <div class="admin-sub">Manage downloaded files · Auto-deleted after 7 days</div>
    </div>
    <div class="admin-actions">
      <button class="btn-danger-outline" onclick="deleteAll()">🗑 Delete All</button>
      <button class="btn-outline" onclick="location.reload()">↻ Refresh</button>
      <a class="btn-outline" href="{{ url_for('admin_logout') }}">Sign Out</a>
    </div>
  </div>

  <!-- Stats -->
  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-label">Total Files</div>
      <div class="stat-value">{{ files|length }}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Total Size</div>
      <div class="stat-value">{{ total_size }}</div>
    </div>
    <div class="stat-card {% if expiring_count > 0 %}warn{% endif %}">
      <div class="stat-label">Expiring Soon</div>
      <div class="stat-value">{{ expiring_count }}</div>
    </div>
  </div>

  <!-- File table -->
  <div class="file-table-wrap">
    {% if files %}
      <div class="file-table-head">
        <div>Filename</div>
        <div>Size</div>
        <div>Downloaded</div>
        <div>Expires In</div>
        <div>Action</div>
      </div>
      {% for f in files %}
        <div class="file-row {% if f.expiring_soon %}expiring{% endif %}">
          <div class="file-name">
            <div class="file-dot"></div>
            <span class="file-name-text" title="{{ f.filename }}">{{ f.filename }}</span>
          </div>
          <div class="file-size">{{ f.size_human }}</div>
          <div class="file-age">{{ f.age_human }} ago</div>
          <div class="file-expiry {% if f.expiring_soon %}warn{% else %}ok{% endif %}">
            {% if f.expiring_soon %}⚠ {% endif %}{{ f.expiry_human }}
          </div>
          <div>
            <button class="btn-delete" onclick="deleteFile('{{ f.filename }}', this)">
              Delete
            </button>
          </div>
        </div>
      {% endfor %}
    {% else %}
      <div class="file-table-empty">No downloaded files yet.</div>
    {% endif %}
  </div>
</div>

<script>
async function deleteFile(filename, btn) {
  if (!confirm('Delete ' + filename + '?')) return;
  btn.disabled = true;
  const resp = await fetch('/admin/delete', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({filename}),
  });
  if (resp.ok) btn.closest('.file-row').remove();
  else { alert('Delete failed'); btn.disabled = false; }
}

async function deleteAll() {
  if (!confirm('Delete ALL files? This cannot be undone.')) return;
  const resp = await fetch('/admin/delete-all', {method: 'POST'});
  if (resp.ok) location.reload();
  else alert('Failed to delete files');
}
</script>
{% endblock %}
```

- [ ] **Step 9.3: Commit**

```bash
git add templates/admin_login.html templates/admin.html
git commit -m "feat: admin panel templates — file management with expiry UI"
```

---

## Task 10: Frontend JavaScript

**Files:**
- Rewrite: `static/js/script.js`

- [ ] **Step 10.1: Rewrite script.js**

Replace entire file:
```javascript
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
    urlFeedback.textContent = `✓ ${data.extractor}`;
    urlFeedback.className = 'url-feedback ok';

    // Thumbnail / meta
    const thumbHtml = data.thumbnail
      ? `<img class="video-thumb" src="${esc(data.thumbnail)}" alt="" loading="lazy">`
      : `<div class="video-thumb-placeholder">🎬</div>`;

    const dur = data.duration ? formatDuration(data.duration) : '';
    videoMeta.innerHTML = `
      ${thumbHtml}
      <div class="video-meta-info">
        <div class="video-title">${esc(data.title)}</div>
        <div class="video-sub">${dur ? dur + ' · ' : ''}${esc(data.extractor)}</div>
        <span class="platform-badge">${esc(data.extractor)}</span>
      </div>
    `;

    // Format list
    formatList.innerHTML = '';
    let firstId = '';

    data.formats.forEach((fmt, i) => {
      const sizeText = fmt.filesize_approx ? '~' + humanSize(fmt.filesize_approx) : '';
      const bestBadge = fmt.is_best ? '<span class="best-badge">BEST</span>' : '';
      const codecText = fmt.label === 'Audio only'
        ? 'MP3 · audio extracted'
        : `MP4 · ${fmt.vcodec ? fmt.vcodec.split('.')[0] : ''}`;

      const item = document.createElement('div');
      item.className = 'format-item' + (fmt.is_best ? ' selected' : '');
      item.dataset.formatId = fmt.format_id;
      item.innerHTML = `
        <div class="format-radio"></div>
        <div class="format-info">
          <div class="format-label">${esc(fmt.label)}${bestBadge}</div>
          <div class="format-codec">${codecText}</div>
        </div>
        <div class="format-size">${sizeText}</div>
      `;
      item.addEventListener('click', () => selectFormat(item, fmt));
      formatList.appendChild(item);

      if (fmt.is_best || i === 0) {
        firstId = fmt.format_id;
        if (fmt.is_best) selectFormat(item, fmt);
      }
    });

    if (!selectedFormatId && firstId) {
      const firstItem = formatList.querySelector('.format-item');
      const firstFmt = data.formats[0];
      selectFormat(firstItem, firstFmt);
    }

    formatPanel.classList.add('visible');
    enableDownload();
  }

  function selectFormat(item, fmt) {
    formatList.querySelectorAll('.format-item').forEach(el => el.classList.remove('selected'));
    item.classList.add('selected');
    selectedFormatId = fmt.format_id;
    hiddenFormat.value = fmt.format_id;

    const sizeText = fmt.filesize_approx ? ' · ~' + humanSize(fmt.filesize_approx) : '';
    downloadText.textContent = `Download ${fmt.label}${sizeText}`;
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
      urlFeedback.innerHTML = '<div class="spinner" style="width:14px;height:14px;display:inline-block;"></div> Fetching video info…';
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
    downloadText.textContent = 'Downloading…';
    downloadBtn.innerHTML = '<div class="spinner"></div><span>Downloading…</span>';
    // Re-enable after a delay so users can retry if browser doesn't navigate away
    setTimeout(() => {
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
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${m}:${String(s).padStart(2, '0')}`;
  }
})();
```

- [ ] **Step 10.2: Commit**

```bash
git add static/js/script.js
git commit -m "feat: format picker JS — AJAX video info, format selection, download"
```

---

## Task 11: Docker

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 11.1: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    -o /usr/local/bin/yt-dlp && chmod +x /usr/local/bin/yt-dlp

WORKDIR /app

# Install Python deps before copying app code (layer cache)
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    flask \
    gunicorn \
    python-telegram-bot

# Copy app
COPY . .

# Downloads volume
RUN mkdir -p /app/downloads
VOLUME ["/app/downloads"]

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "main:app"]
```

- [ ] **Step 11.2: Create docker-compose.yml**

```yaml
services:
  web:
    build: .
    ports:
      - "5000:5000"
    env_file:
      - .env
    volumes:
      - ./downloads:/app/downloads
    restart: unless-stopped
```

- [ ] **Step 11.3: Verify Dockerfile syntax**

```bash
docker build --no-cache -t vidgrab-test . 2>&1 | tail -5
```
Expected: `Successfully built <id>` or similar. Fix any errors before continuing.

- [ ] **Step 11.4: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: Docker + docker-compose.yml for Linux deployment"
```

---

## Task 12: Final Wiring Check & Full Test Run

- [ ] **Step 12.1: Run full test suite**

```bash
pytest -v
```
Expected: all tests PASS. Fix any failures before proceeding.

- [ ] **Step 12.2: Verify app starts locally**

```bash
python main.py
```
Open http://localhost:5000 in browser. Confirm:
- Gradient Hero UI renders
- Navbar shows bot status
- Pasting a YouTube URL shows the spinner then format list
- Admin link goes to `/admin/login`
- Login with ADMIN_PASSWORD from .env works
- Admin panel shows files table (empty is fine)
- Logout redirects back to login

- [ ] **Step 12.3: Verify Docker Compose**

```bash
cp .env.example .env
# Edit .env — set ADMIN_PASSWORD and optionally TELEGRAM_BOT_TOKEN
docker-compose up --build
```
Open http://localhost:5000 — same checks as above.

- [ ] **Step 12.4: Final commit**

```bash
git add -A
git commit -m "feat: VidGrab overhaul complete — Gradient Hero UI, format picker, admin panel, Docker"
```
