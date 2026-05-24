import logging
import os
import threading
import time

from flask import (Flask, flash, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)

import utils.downloader as _downloader
from utils.downloader import is_valid_url

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
        info = _downloader.get_video_info(url)
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
        result = _downloader.download_video(url, DOWNLOAD_FOLDER, format_id=format_id)
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
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    filename = (request.json or {}).get('filename', '')
    if not filename:
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400
    resolved = os.path.realpath(os.path.join(DOWNLOAD_FOLDER, filename))
    safe_root = os.path.realpath(DOWNLOAD_FOLDER)
    if not resolved.startswith(safe_root + os.sep):
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400
    # Only allow bare filenames — no subdirectory component
    if os.path.dirname(resolved) != safe_root:
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400

    if not os.path.isfile(resolved):
        return jsonify({'success': False, 'error': 'File not found'}), 404

    os.remove(resolved)
    return jsonify({'success': True})


@app.route('/admin/delete-all', methods=['POST'])
def admin_delete_all():
    redir = _require_admin()
    if redir:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

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
