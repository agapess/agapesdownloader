import os
import logging
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
