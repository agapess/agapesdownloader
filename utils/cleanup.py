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
