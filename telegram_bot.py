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

    platform = get_platform(url) or 'Unknown site'
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
