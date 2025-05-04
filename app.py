import os
import logging
import threading
import subprocess
from flask import Flask, render_template, request, jsonify, send_from_directory, flash, redirect, url_for
from utils.downloader import download_video, is_valid_url, get_platform

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key_for_dev")

# Create downloads directory if it doesn't exist
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Telegram bot process
telegram_bot_process = None

def start_telegram_bot():
    """Start the Telegram bot in a separate process"""
    global telegram_bot_process
    if telegram_bot_process and telegram_bot_process.poll() is None:
        # Bot is already running
        return False
    
    # Start the bot
    try:
        telegram_bot_process = subprocess.Popen(["python", "telegram_bot.py"])
        return True
    except Exception as e:
        logger.exception(f"Failed to start Telegram bot: {str(e)}")
        return False

def stop_telegram_bot():
    """Stop the Telegram bot process"""
    global telegram_bot_process
    if telegram_bot_process and telegram_bot_process.poll() is None:
        telegram_bot_process.terminate()
        telegram_bot_process = None
        return True
    return False

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    """Handle video download request"""
    video_url = request.form.get('url', '').strip()
    
    if not video_url:
        flash('Please enter a video URL', 'danger')
        return redirect(url_for('index'))
    
    if not is_valid_url(video_url):
        flash('Invalid URL format', 'danger')
        return redirect(url_for('index'))
    
    platform = get_platform(video_url)
    if not platform:
        flash('URL not supported. Please enter a YouTube, Instagram, or Twitter/X video URL', 'danger')
        return redirect(url_for('index'))
    
    try:
        result = download_video(video_url, DOWNLOAD_FOLDER)
        if result['success']:
            flash(f'Video successfully downloaded as {result["filename"]}', 'success')
            return send_from_directory(
                DOWNLOAD_FOLDER, 
                result['filename'], 
                as_attachment=True,
                download_name=result['filename']
            )
        else:
            flash(f'Download failed: {result["error"]}', 'danger')
            return redirect(url_for('index'))
    except Exception as e:
        logger.exception("Error during download")
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('index'))

@app.route('/ajax/platform-check', methods=['POST'])
def platform_check():
    """Check which platform a URL belongs to"""
    url = request.json.get('url', '')
    if not url:
        return jsonify({"valid": False, "platform": None})
    
    valid = is_valid_url(url)
    platform = get_platform(url) if valid else None
    
    return jsonify({
        "valid": valid,
        "platform": platform
    })

@app.route('/telegram/start', methods=['POST'])
def telegram_start():
    """Start the Telegram bot"""
    # Check if Telegram bot token is set
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        flash("Telegram bot token not set. Please set the TELEGRAM_BOT_TOKEN environment variable.", "danger")
        return redirect(url_for('index'))
    
    # Start the bot
    success = start_telegram_bot()
    if success:
        flash("Telegram bot started successfully! You can now interact with it on Telegram.", "success")
    else:
        flash("Telegram bot is already running or failed to start.", "warning")
    
    return redirect(url_for('index'))

@app.route('/telegram/stop', methods=['POST'])
def telegram_stop():
    """Stop the Telegram bot"""
    success = stop_telegram_bot()
    if success:
        flash("Telegram bot stopped successfully.", "success")
    else:
        flash("Telegram bot is not running.", "warning")
    
    return redirect(url_for('index'))

@app.route('/telegram/status', methods=['GET'])
def telegram_status():
    """Check if the Telegram bot is running"""
    is_running = telegram_bot_process is not None and telegram_bot_process.poll() is None
    bot_token_set = os.environ.get("TELEGRAM_BOT_TOKEN") is not None
    
    return jsonify({
        "running": is_running,
        "token_set": bot_token_set
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
