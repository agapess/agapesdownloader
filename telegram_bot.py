import os
import logging
import asyncio
import time
from datetime import datetime

from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

from utils.downloader import is_valid_url, get_platform, download_video

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Set higher logging level for httpx to avoid debug logs
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Replace with your actual bot token
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Create downloads directory if it doesn't exist
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! 👋\n\n"
        f"I'm a Video Downloader Bot. Send me a link to a YouTube, Instagram, or Twitter/X video, "
        f"and I'll download it for you.\n\n"
        f"Try sending a video URL now!"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = (
        "*Video Downloader Bot Help*\n\n"
        "I can download videos from these platforms:\n"
        "• YouTube\n"
        "• Instagram\n"
        "• Twitter/X\n\n"
        "*How to use:*\n"
        "1. Simply send me a video URL\n"
        "2. Wait for me to download it\n"
        "3. I'll send you the video file\n\n"
        "*Commands:*\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/about - Information about the bot\n"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /about is issued."""
    about_text = (
        "*Video Downloader Bot*\n\n"
        "This bot can download videos from YouTube, Instagram, and Twitter/X.\n\n"
        "Built with Python using python-telegram-bot and youtube-dl.\n"
    )
    await update.message.reply_text(about_text, parse_mode=ParseMode.MARKDOWN)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle video URLs sent by users."""
    # Get URL from message
    url = update.message.text.strip()
    
    # Check if it's a valid URL
    if not is_valid_url(url):
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid URL. Please send a valid video link."
        )
        return
    
    # Identify platform
    platform = get_platform(url)
    if not platform:
        await update.message.reply_text(
            "⚠️ Unsupported platform. I can only download videos from YouTube, Instagram, and Twitter/X."
        )
        return
    
    # Send acknowledgement
    platform_emoji = {
        "youtube": "▶️ YouTube",
        "instagram": "📸 Instagram",
        "twitter": "🐦 Twitter/X"
    }
    
    status_message = await update.message.reply_text(
        f"📥 Downloading {platform_emoji.get(platform, platform)} video...\nPlease wait, this may take a moment."
    )
    
    try:
        # Start download
        download_start_time = time.time()
        
        # Download the video
        result = download_video(url, DOWNLOAD_FOLDER)
        
        if result["success"]:
            download_time = time.time() - download_start_time
            file_path = result["path"]
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # Convert to MB
            
            # Edit status message
            await status_message.edit_text(
                f"✅ Download complete! Size: {file_size:.1f} MB, Time: {download_time:.1f}s\n"
                f"Now uploading to Telegram..."
            )
            
            # Check file size (Telegram has 50MB limit for bots)
            if file_size > 50:
                await update.message.reply_text(
                    f"⚠️ Sorry, the video is too large ({file_size:.1f} MB) for me to send. "
                    f"Telegram has a 50 MB file size limit for bots."
                )
                return
                
            # Send the video file
            upload_start_time = time.time()
            with open(file_path, "rb") as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"📹 Here's your video from {platform_emoji.get(platform, platform)}!",
                    filename=result["filename"],
                    write_timeout=300,  # 5 minutes timeout for uploading
                )
            
            upload_time = time.time() - upload_start_time
            
            # Update status message
            await status_message.edit_text(
                f"✅ Success!\n"
                f"Download: {file_size:.1f} MB in {download_time:.1f}s\n"
                f"Upload: {file_size:.1f} MB in {upload_time:.1f}s\n"
            )
            
            # Log success
            logger.info(
                f"Successfully processed {platform} video for {update.effective_user.id}. "
                f"Size: {file_size:.1f}MB"
            )
            
        else:
            # Download failed
            error_message = result.get("error", "Unknown error")
            await status_message.edit_text(
                f"❌ Download failed: {error_message}\n"
                f"Please try again with a different video."
            )
            logger.error(f"Download failed: {error_message} for URL: {url}")
    
    except Exception as e:
        # Handle unexpected errors
        logger.exception(f"Error processing video: {str(e)}")
        await status_message.edit_text(
            f"❌ An error occurred: {str(e)}\n"
            f"Please try again later."
        )

def main() -> None:
    """Start the bot."""
    # Check if token is available
    if not TELEGRAM_BOT_TOKEN:
        logger.error("No TELEGRAM_BOT_TOKEN provided. Set the environment variable.")
        return
    
    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    
    # Add URL handler - will respond to any message that looks like a URL
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
