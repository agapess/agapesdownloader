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


# ── get_platform ────────────────────────────────────────────────────────────

def test_get_platform_returns_none_for_unknown():
    from utils.downloader import get_platform
    assert get_platform('https://example.com/some/video') is None


def test_get_platform_returns_youtube_for_youtube():
    from utils.downloader import get_platform
    assert get_platform('https://youtube.com/watch?v=abc') == 'YouTube'
