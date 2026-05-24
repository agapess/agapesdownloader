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
