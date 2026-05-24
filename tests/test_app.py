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
            {'format_id': '137', 'label': '1080p', 'resolution': '1920x1080',
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


def test_admin_delete_rejects_absolute_path(admin_client, tmp_path):
    with patch('app.DOWNLOAD_FOLDER', str(tmp_path)):
        resp = admin_client.post('/admin/delete',
                                  json={'filename': '/etc/passwd'})
    assert resp.status_code == 400


def test_admin_delete_rejects_forward_slash_subdir(admin_client, tmp_path):
    with patch('app.DOWNLOAD_FOLDER', str(tmp_path)):
        resp = admin_client.post('/admin/delete',
                                  json={'filename': 'subdir/file.mp4'})
    assert resp.status_code == 400


def test_admin_logout_clears_session(admin_client):
    resp = admin_client.get('/admin/logout', follow_redirects=False)
    assert resp.status_code == 302
    # After logout, /admin should redirect to login
    resp2 = admin_client.get('/admin', follow_redirects=False)
    assert resp2.status_code == 302
