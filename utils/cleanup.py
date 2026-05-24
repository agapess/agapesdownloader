import logging
import os
import subprocess
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


def update_ytdlp():
    """Run yt-dlp -U to self-update. Returns True on success."""
    try:
        result = subprocess.run(
            ['yt-dlp', '-U'],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            logger.info('yt-dlp update: %s', result.stdout.strip() or 'up to date')
        else:
            logger.warning('yt-dlp update failed: %s', result.stderr.strip())
        return result.returncode == 0
    except Exception as e:
        logger.warning('yt-dlp update error: %s', e)
        return False


def start_ytdlp_updater_thread(interval_seconds=86400):
    """Start a daemon thread that updates yt-dlp every interval_seconds (default 24h)."""

    def _loop():
        # Run once at startup, then every interval
        update_ytdlp()
        while True:
            time.sleep(interval_seconds)
            update_ytdlp()

    t = threading.Thread(target=_loop, daemon=True, name='ytdlp-updater')
    t.start()
    return t
