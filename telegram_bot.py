import logging
import os
import threading
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                           MessageHandler, filters, ContextTypes)

from utils.downloader import download_video, get_platform, get_video_info, is_valid_url

logger = logging.getLogger(__name__)

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), 'downloads')
TELEGRAM_MAX_BYTES = 50 * 1024 * 1024  # 50 MB


def _fmt_size(n):
    if not n:
        return ''
    if n < 1024 * 1024:
        return f'{n / 1024:.0f} KB'
    if n < 1024 * 1024 * 1024:
        return f'{n / 1024 / 1024:.0f} MB'
    return f'{n / 1024 / 1024 / 1024:.1f} GB'


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '👋 Hi! I\'m VidGrab Bot.\n\n'
        'Send me any video link — I\'ll show you available qualities to choose from.\n\n'
        '⚠️ *Telegram limit: 50 MB per file.* For larger videos, use the web app.',
        parse_mode='Markdown',
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        '*How to use:*\n'
        '1. Paste any video URL\n'
        '2. Pick your preferred quality or MP3 only\n'
        '3. I\'ll download and send the file\n\n'
        'Supports YouTube, Instagram, TikTok, Twitter, Reddit, Vimeo, and 1000+ more sites.\n\n'
        '⚠️ *50 MB limit* — larger files must be downloaded via the web app.',
        parse_mode='Markdown',
    )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not is_valid_url(url):
        await update.message.reply_text(
            '❌ That doesn\'t look like a valid URL. Please send a video link.')
        return

    platform = get_platform(url) or 'Unknown site'
    status_msg = await update.message.reply_text(f'🔍 Fetching formats from {platform}…')

    try:
        info = get_video_info(url)
    except RuntimeError as e:
        await status_msg.edit_text(f'❌ Could not fetch video info: {e}')
        return

    formats = info['formats']
    if not formats:
        await status_msg.edit_text('❌ No downloadable formats found for this URL.')
        return

    # Store URL + formats so the callback handler can use them
    context.user_data['pending_url'] = url
    context.user_data['pending_formats'] = formats

    # Build inline keyboard — up to 4 video qualities + MP3
    video_fmts = [f for f in formats if f['label'] != 'Audio only'][:4]
    audio_fmts = [f for f in formats if f['label'] == 'Audio only']

    buttons = []
    for fmt in video_fmts:
        size = _fmt_size(fmt.get('filesize_approx'))
        size_str = f' (~{size})' if size else ''
        star = ' ⭐' if fmt.get('is_best') else ''
        idx = formats.index(fmt)
        buttons.append([InlineKeyboardButton(
            f'🎬 {fmt["label"]}{star}{size_str}',
            callback_data=f'fmt:{idx}',
        )])

    for fmt in audio_fmts:
        size = _fmt_size(fmt.get('filesize_approx'))
        size_str = f' (~{size})' if size else ''
        idx = formats.index(fmt)
        buttons.append([InlineKeyboardButton(
            f'🎵 MP3 only{size_str}',
            callback_data=f'fmt:{idx}',
        )])

    dur = info.get('duration', 0)
    dur_str = f' · {int(dur) // 60}:{int(dur) % 60:02d}' if dur else ''

    await status_msg.edit_text(
        f'*{info["title"]}*\n'
        f'_{platform}{dur_str}_\n\n'
        'Choose a format to download:',
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='Markdown',
    )


async def handle_format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    idx = int(query.data.split(':')[1])
    formats = context.user_data.get('pending_formats', [])
    url = context.user_data.get('pending_url', '')

    if not url or idx >= len(formats):
        await query.edit_message_text('❌ Session expired. Please send the URL again.')
        return

    fmt = formats[idx]
    label = fmt['label']

    await query.edit_message_text(f'⬇️ Downloading {label}…')

    start = time.time()
    result = download_video(url, DOWNLOAD_FOLDER, format_id=fmt['format_id'])

    if not result['success']:
        await query.edit_message_text(f'❌ Download failed: {result["error"]}')
        return

    filepath = result['path']
    filesize = os.path.getsize(filepath)

    if filesize > TELEGRAM_MAX_BYTES:
        await query.edit_message_text(
            f'⚠️ File is {filesize / 1024 / 1024:.1f} MB — too large for Telegram (50 MB limit).\n'
            'Please download it from the web app instead.'
        )
        return

    elapsed = time.time() - start
    await query.edit_message_text('📤 Uploading…')

    try:
        with open(filepath, 'rb') as f:
            await query.message.reply_document(
                document=f,
                filename=result['filename'],
                caption=f'✅ {label} · {elapsed:.1f}s · {filesize / 1024 / 1024:.1f} MB',
            )
        await query.delete_message()
    except Exception as e:
        logger.exception('Failed to send file via Telegram')
        await query.edit_message_text(f'❌ Failed to send file: {e}')


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
    app.add_handler(CallbackQueryHandler(handle_format_callback, pattern='^fmt:'))

    logger.info('Telegram bot starting polling')
    await app.run_polling(drop_pending_updates=True, stop_signals=None)


if __name__ == '__main__':
    import asyncio
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        print('Set TELEGRAM_BOT_TOKEN environment variable')
    else:
        asyncio.run(_start_bot(token))
