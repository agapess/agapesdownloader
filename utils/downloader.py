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
    """Return a display-friendly platform name, or None for unrecognised URLs."""
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
    return None


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
            'resolution': f'{f.get("width", "?")}x{height}',
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
