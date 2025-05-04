import os
import re
import logging
import urllib.parse
import requests
from datetime import datetime
import pytube
import instaloader
import subprocess
import tempfile
import shutil

logger = logging.getLogger(__name__)

def is_valid_url(url):
    """Check if the URL is valid"""
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def get_platform(url):
    """Detect platform from URL"""
    url_lower = url.lower()
    
    if any(domain in url_lower for domain in ["youtube.com", "youtu.be"]):
        return "youtube"
    elif any(domain in url_lower for domain in ["instagram.com"]):
        return "instagram"
    elif any(domain in url_lower for domain in ["twitter.com", "x.com"]):
        return "twitter"
    else:
        return None

def sanitize_filename(filename):
    """Sanitize filename to remove invalid characters"""
    # Replace invalid characters with underscore
    sanitized = re.sub(r'[\\/*?:"<>|]', "_", filename)
    # Trim to reasonable length and add timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    max_length = 50  # Maximum length for base filename
    
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return f"{sanitized}_{timestamp}"

def download_youtube(url, download_folder):
    """Download YouTube video"""
    try:
        yt = pytube.YouTube(url)
        
        # Get the highest resolution stream with both video and audio
        stream = yt.streams.get_highest_resolution()
        
        # Create a safe filename
        title = sanitize_filename(yt.title)
        filename = f"{title}.mp4"
        full_path = os.path.join(download_folder, filename)
        
        # Download the video
        stream.download(output_path=download_folder, filename=filename)
        
        return {
            "success": True,
            "filename": filename,
            "path": full_path
        }
    except Exception as e:
        logger.exception(f"YouTube download error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def download_instagram(url, download_folder):
    """Download Instagram video"""
    try:
        # Initialize instaloader
        L = instaloader.Instaloader(
            dirname_pattern=download_folder,
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False
        )
        
        # Extract post shortcode from URL
        parsed_url = urllib.parse.urlparse(url)
        path_parts = parsed_url.path.strip('/').split('/')
        
        # Handle different URL formats
        shortcode = None
        for part in path_parts:
            if part != "p" and part != "reel" and len(part) > 5:
                shortcode = part
                break
        
        if not shortcode:
            raise ValueError("Could not extract Instagram post ID from URL")
        
        # Create a temporary directory to download
        with tempfile.TemporaryDirectory() as temp_dir:
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            
            if not post.is_video:
                raise ValueError("This Instagram post does not contain a video")
            
            # Download the post
            L.download_post(post, target=temp_dir)
            
            # Find the video file in the temp directory
            video_file = None
            for file in os.listdir(temp_dir):
                if file.endswith('.mp4'):
                    video_file = file
                    break
            
            if not video_file:
                raise FileNotFoundError("Could not find downloaded video file")
            
            # Create a safe filename
            safe_filename = f"instagram_{shortcode}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
            output_path = os.path.join(download_folder, safe_filename)
            
            # Copy from temp to final destination
            shutil.copy2(os.path.join(temp_dir, video_file), output_path)
            
            return {
                "success": True,
                "filename": safe_filename,
                "path": output_path
            }
    except Exception as e:
        logger.exception(f"Instagram download error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def download_twitter(url, download_folder):
    """Download Twitter/X video"""
    try:
        # Create a unique filename based on the URL and timestamp
        parsed_url = urllib.parse.urlparse(url)
        path_parts = parsed_url.path.strip('/').split('/')
        tweet_id = path_parts[-1] if path_parts else "unknown"
        
        filename = f"twitter_{tweet_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
        output_path = os.path.join(download_folder, filename)
        
        # Run youtube-dl command to download Twitter video
        # We'll use subprocess to call youtube-dl which handles Twitter videos well
        command = [
            "youtube-dl", 
            "--no-warnings",
            "-o", output_path,
            url
        ]
        
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
        
        if os.path.exists(output_path):
            return {
                "success": True,
                "filename": filename,
                "path": output_path
            }
        else:
            raise FileNotFoundError(f"Download seemed to succeed but file not found: {result.stdout}")
            
    except subprocess.CalledProcessError as e:
        logger.exception(f"Twitter download error (subprocess): {e.stderr}")
        return {
            "success": False,
            "error": f"Twitter download failed: {e.stderr}"
        }
    except Exception as e:
        logger.exception(f"Twitter download error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def download_video(url, download_folder):
    """Main function to download videos from different platforms"""
    platform = get_platform(url)
    
    if platform == "youtube":
        return download_youtube(url, download_folder)
    elif platform == "instagram":
        return download_instagram(url, download_folder)
    elif platform == "twitter":
        return download_twitter(url, download_folder)
    else:
        return {
            "success": False,
            "error": "Unsupported platform"
        }
