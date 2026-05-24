# VidGrab Overhaul — Design Spec
**Date:** 2026-05-23  
**Status:** Approved

## Overview

Complete overhaul of the existing Flask-based video downloader app. Goals: beautiful Gradient Hero UI, format/resolution picker with size estimates, download from any yt-dlp-supported site, Telegram bot auto-start as background thread, password-protected admin panel with 7-day auto-deletion, and Linux Docker Compose deployment.

---

## 1. UI — Gradient Hero Style

**Theme:** Deep blue-to-purple gradient background (`#1e3a5f → #0d1b2a → #1a0a2e`), warm orange/red CTAs (`#ff6b6b → #ff8c42`), glassmorphism cards.

**Layout — `templates/layout.html`:**
- Nav bar: VidGrab logo (left) · bot status indicator · Admin link (right)
- Flash message display
- Footer: supported platform icons

**Main page — `templates/index.html`:**
- Hero: badge ("Supports 1000+ websites"), headline "Download Any Video, Anywhere.", subtext listing platforms
- Glassmorphism input card: URL field → triggers format fetch on input · Format picker panel (hidden until info loads) · Download button
- Platform icons row (YouTube, Instagram, TikTok, Twitter, Reddit, Vimeo, +∞)
- Telegram bot card: link to `@BotUsername`, ⚠️ 50 MB warning banner

**Format picker panel (appears after URL paste):**
- Thumbnail + title + duration + platform badge
- Radio list of available formats: resolution label, codec info, estimated file size
- "BEST" badge on recommended format (usually best quality under 1080p)
- Audio-only MP3 option always shown if available
- Download button updates dynamically: "Download 1080p · ~580 MB"

---

## 2. Format Picker — Backend

**New endpoint: `POST /ajax/video-info`**
- Accepts `{ url }` 
- Runs `yt-dlp --dump-json <url>` to get full metadata
- Returns: `{ title, thumbnail, duration, platform, formats: [{ format_id, resolution, ext, filesize_approx, vcodec, acodec, label }] }`
- Filters to unique resolutions + audio-only; sorts best-first
- Estimates file size from `filesize_approx` or `filesize`; falls back to bitrate × duration if missing

**Updated `POST /download`:**
- Accepts `format_id` alongside `url`
- Passes `-f <format_id>` to yt-dlp
- Falls back to `bestvideo+bestaudio/best` if no format_id given

**`utils/downloader.py` changes:**
- Remove all platform-specific functions (`download_youtube`, `download_instagram`, etc.)
- Single `download_video(url, folder, format_id=None)` function using yt-dlp directly
- Any URL accepted — if yt-dlp can't handle it, return a clear error
- Audio-only: if format is audio-only, run yt-dlp with `--extract-audio --audio-format mp3`

---

## 3. Telegram Bot — Auto-start Background Thread

**`telegram_bot.py` changes:**
- Add `run_bot_thread()` function that starts the bot in a `threading.Thread(daemon=True)`
- Bot reads `TELEGRAM_BOT_TOKEN` from environment (via `.env`)
- If token missing, thread exits silently (no crash)
- Bot handles any URL (not just specific platforms) using the shared `download_video()` utility
- 50 MB limit enforced: if file exceeds limit, reply with message explaining the web app alternative

**`app.py` changes:**
- Bot and cleanup threads started via a module-level `_start_background_services()` call, guarded by `os.environ.get('WERKZEUG_RUN_MAIN') != 'false'` so it runs once per process (not twice in Flask dev reloader). Works correctly with gunicorn single-worker.
- Remove `/telegram/start`, `/telegram/stop`, `/telegram/status` routes
- Bot username read from env `TELEGRAM_BOT_USERNAME`; falls back to "YourBot" if not set

**Nav status indicator:**
- Shows "🟢 Bot Active" if `TELEGRAM_BOT_TOKEN` is set, "⚪ Bot Offline" if not

---

## 4. Admin Panel

**Route: `GET/POST /admin/login`**
- Simple HTML form, checks password against `ADMIN_PASSWORD` env var
- On success: sets `session['admin'] = True`, redirects to `/admin`

**Route: `GET /admin`**
- Requires `session['admin']` — redirects to `/admin/login` if not set
- Reads all files in `downloads/` folder
- Computes: filename, size (human-readable), modified time ("X ago"), expiry (7 days from mtime, "Xd Yh left")
- Files expiring within 24h highlighted orange
- Stats: total file count, total size, expiring-soon count

**Route: `POST /admin/delete`**
- Accepts `{ filename }` — deletes single file from `downloads/`
- Admin-session required

**Route: `POST /admin/delete-all`**
- Deletes all files in `downloads/`
- Admin-session required

**Route: `GET /admin/logout`**
- Clears session, redirects to `/admin/login`

**Auto-deletion background thread:**
- Started at app launch alongside bot thread
- Runs every hour, deletes any file in `downloads/` older than 7 days
- Logs deleted filenames

---

## 5. Docker Compose

**`Dockerfile`:**
- Base: `python:3.11-slim`
- Installs: `ffmpeg` (via apt), `yt-dlp` (via pip)
- Copies app, installs Python deps from `pyproject.toml`
- Exposes port `5000`
- CMD: `gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 4 main:app` (single worker required — multiple workers would spawn competing bot polling processes)

**`docker-compose.yml`:**
- Single service `web`
- `env_file: .env`
- Volume: `./downloads:/app/downloads`
- Port: `5000:5000`
- Restart policy: `unless-stopped`

**`.env.example`:**
```
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_BOT_USERNAME=YourBotName
SECRET_KEY=change_me_to_a_random_string
ADMIN_PASSWORD=change_me
```

**`.gitignore` additions:** `.env`, `downloads/`, `cert.pem`, `key.pem`

---

## 6. Files Changed / Created

| File | Action |
|------|--------|
| `templates/layout.html` | Rewrite — Gradient Hero base template |
| `templates/index.html` | Rewrite — hero, format picker, Telegram card |
| `templates/admin_login.html` | New — login form |
| `templates/admin.html` | New — file management panel |
| `static/css/custom.css` | Rewrite — Gradient Hero design system |
| `static/js/script.js` | Rewrite — format picker flow, AJAX video-info |
| `utils/downloader.py` | Refactor — single universal download_video(), remove platform funcs |
| `app.py` | Update — new routes, bot thread startup, auto-delete thread |
| `telegram_bot.py` | Update — thread-safe runner, any-URL support |
| `Dockerfile` | New |
| `docker-compose.yml` | New |
| `.env.example` | New |
| `.gitignore` | Update |

---

## 7. Out of Scope

- User accounts or per-user download history
- Download queue / progress streaming (downloads complete before file is sent)
- Thumbnail caching between requests
- HTTPS termination (handled by reverse proxy in production)
