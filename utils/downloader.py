import os
import re
import logging
import urllib.parse
import requests
from datetime import datetime
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
    """Download YouTube video using youtube-dl"""
    try:
        # Extract video ID if possible for better filename
        video_id_match = re.search(r'(?:v=|\/)([-\w]+)', url)
        video_id = video_id_match.group(1) if video_id_match else "unknown"
        
        # Create a timestamped filename
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        temp_filename = f"youtube_{video_id}_{timestamp}.%(ext)s"
        output_path_template = os.path.join(download_folder, temp_filename)
        
        # Run youtube-dl command to download YouTube video
        command = [
            "youtube-dl", 
            "--no-warnings",
            "--format", "best",  # Get best quality
            "--output", output_path_template,
            url
        ]
        
        logger.info(f"Executing YouTube download: {' '.join(command)}")
        
        # Try multiple formats if needed
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True
            )
            
            logger.info(f"youtube-dl output: {result.stdout}")
            
            # Find the downloaded file
            downloaded_files = [f for f in os.listdir(download_folder) 
                              if f.startswith(f"youtube_{video_id}_{timestamp}")]
            
            if downloaded_files:
                actual_filename = downloaded_files[0]  # Take the first matching file
                actual_path = os.path.join(download_folder, actual_filename)
                
                if os.path.exists(actual_path) and os.path.getsize(actual_path) > 0:
                    return {
                        "success": True,
                        "filename": actual_filename,
                        "path": actual_path
                    }
            
            # If we got here, we couldn't find the downloaded file
            raise FileNotFoundError("Could not find downloaded video file")
            
        except subprocess.CalledProcessError as e:
            # If the first attempt fails, try with a different format
            logger.warning(f"First YouTube download attempt failed, trying with format 'mp4': {e.stderr}")
            
            # Try with mp4 format explicitly
            command[3] = "mp4"  # Change format to mp4
            
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True
            )
            
            # Find the downloaded file again
            downloaded_files = [f for f in os.listdir(download_folder) 
                              if f.startswith(f"youtube_{video_id}_{timestamp}")]
            
            if downloaded_files:
                actual_filename = downloaded_files[0]  # Take the first matching file
                actual_path = os.path.join(download_folder, actual_filename)
                
                if os.path.exists(actual_path) and os.path.getsize(actual_path) > 0:
                    return {
                        "success": True,
                        "filename": actual_filename,
                        "path": actual_path
                    }
            
            # Still couldn't find a downloaded file
            raise FileNotFoundError("Could not find downloaded video file after mp4 format attempt")
    
    except Exception as e:
        logger.exception(f"YouTube download error: {str(e)}")
        return {
            "success": False,
            "error": "Failed to download video. The video might be restricted or unavailable."
        }

def download_instagram(url, download_folder):
    """Download Instagram video using youtube-dl"""
    try:
        # Extract post shortcode from URL for better filename
        parsed_url = urllib.parse.urlparse(url)
        path_parts = parsed_url.path.strip('/').split('/')
        
        shortcode = None
        for part in path_parts:
            if part != "p" and part != "reel" and len(part) > 5:
                shortcode = part
                break
                
        if not shortcode:
            shortcode = "unknown"
        
        # Create a timestamped filename
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        temp_filename = f"instagram_{shortcode}_{timestamp}.%(ext)s"
        output_path_template = os.path.join(download_folder, temp_filename)
        
        # Run youtube-dl command to download Instagram video
        command = [
            "youtube-dl", 
            "--no-warnings",
            "--format", "best",
            "--output", output_path_template,
            url
        ]
        
        logger.info(f"Executing Instagram download: {' '.join(command)}")
        
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True
            )
            
            logger.info(f"youtube-dl output: {result.stdout}")
            
            # Find the downloaded file
            downloaded_files = [f for f in os.listdir(download_folder) 
                              if f.startswith(f"instagram_{shortcode}_{timestamp}")]
            
            if downloaded_files:
                actual_filename = downloaded_files[0]  # Take the first matching file
                actual_path = os.path.join(download_folder, actual_filename)
                
                if os.path.exists(actual_path) and os.path.getsize(actual_path) > 0:
                    return {
                        "success": True,
                        "filename": actual_filename,
                        "path": actual_path
                    }
            
            # If we got here, we couldn't find the downloaded file
            raise FileNotFoundError("Could not find downloaded video file")
            
        except subprocess.CalledProcessError as e:
            # If first attempt fails, try with cookies or different options
            logger.warning(f"First Instagram download attempt failed, trying with a different approach: {e.stderr}")
            
            # Try with bestvideo+bestaudio
            command[3] = "bestvideo+bestaudio"  # Change format
            
            try:
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    text=True
                )
                
                # Find the downloaded file again
                downloaded_files = [f for f in os.listdir(download_folder) 
                                 if f.startswith(f"instagram_{shortcode}_{timestamp}")]
                
                if downloaded_files:
                    actual_filename = downloaded_files[0]  # Take the first matching file
                    actual_path = os.path.join(download_folder, actual_filename)
                    
                    if os.path.exists(actual_path) and os.path.getsize(actual_path) > 0:
                        return {
                            "success": True,
                            "filename": actual_filename,
                            "path": actual_path
                        }
                
                # Still couldn't find a downloaded file
                raise FileNotFoundError("Could not find downloaded video file after format change attempt")
                
            except subprocess.CalledProcessError:
                # If that also fails, try with just 'mp4' format
                command[3] = "mp4"  # Change format to mp4
                
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    text=True
                )
                
                # Find the downloaded file one last time
                downloaded_files = [f for f in os.listdir(download_folder) 
                                 if f.startswith(f"instagram_{shortcode}_{timestamp}")]
                
                if downloaded_files:
                    actual_filename = downloaded_files[0]  # Take the first matching file
                    actual_path = os.path.join(download_folder, actual_filename)
                    
                    if os.path.exists(actual_path) and os.path.getsize(actual_path) > 0:
                        return {
                            "success": True,
                            "filename": actual_filename,
                            "path": actual_path
                        }
                
                # Final failure
                raise FileNotFoundError("Could not find downloaded video file after multiple attempts")
    
    except Exception as e:
        logger.exception(f"Instagram download error: {str(e)}")
        return {
            "success": False,
            "error": "Failed to download video. The post may be private or unavailable."
        }

def download_twitter(url, download_folder):
    """Download Twitter/X video using youtube-dl"""
    try:
        # Extract tweet ID for better filename
        parsed_url = urllib.parse.urlparse(url)
        path_parts = parsed_url.path.strip('/').split('/')
        tweet_id = path_parts[-1] if path_parts else "unknown"
        
        # Create a timestamped filename
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        temp_filename = f"twitter_{tweet_id}_{timestamp}.%(ext)s"
        output_path_template = os.path.join(download_folder, temp_filename)
        
        # Run youtube-dl command to download Twitter video
        command = [
            "youtube-dl", 
            "--no-warnings",
            "--format", "best",  # Get best quality
            "--output", output_path_template,
            url
        ]
        
        logger.info(f"Executing Twitter download: {' '.join(command)}")
        
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True
            )
            
            logger.info(f"youtube-dl output: {result.stdout}")
            
            # Find the downloaded file
            downloaded_files = [f for f in os.listdir(download_folder) 
                              if f.startswith(f"twitter_{tweet_id}_{timestamp}")]
            
            if downloaded_files:
                actual_filename = downloaded_files[0]  # Take the first matching file
                actual_path = os.path.join(download_folder, actual_filename)
                
                if os.path.exists(actual_path) and os.path.getsize(actual_path) > 0:
                    return {
                        "success": True,
                        "filename": actual_filename,
                        "path": actual_path
                    }
            
            # If we got here, we couldn't find the downloaded file
            raise FileNotFoundError("Could not find downloaded video file")
            
        except subprocess.CalledProcessError as e:
            # If youtube-dl fails, try with a different format option
            logger.warning(f"First Twitter download attempt failed, trying with different format: {e.stderr}")
            
            # Try with mp4 format explicitly
            command[3] = "mp4"  # Change format to mp4
            
            try:
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    text=True
                )
                
                # Find the downloaded file again
                downloaded_files = [f for f in os.listdir(download_folder) 
                                  if f.startswith(f"twitter_{tweet_id}_{timestamp}")]
                
                if downloaded_files:
                    actual_filename = downloaded_files[0]  # Take the first matching file
                    actual_path = os.path.join(download_folder, actual_filename)
                    
                    if os.path.exists(actual_path) and os.path.getsize(actual_path) > 0:
                        return {
                            "success": True,
                            "filename": actual_filename,
                            "path": actual_path
                        }
                
                # Still couldn't find a downloaded file
                raise FileNotFoundError("Could not find downloaded video file after mp4 format attempt")
                
            except subprocess.CalledProcessError:
                # If that also fails, try with a different technique
                command[3] = "worstaudio+worstvideo"  # Sometimes lower quality works when better fails
                
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    text=True
                )
                
                # Find the downloaded file one last time
                downloaded_files = [f for f in os.listdir(download_folder) 
                                  if f.startswith(f"twitter_{tweet_id}_{timestamp}")]
                
                if downloaded_files:
                    actual_filename = downloaded_files[0]  # Take the first matching file
                    actual_path = os.path.join(download_folder, actual_filename)
                    
                    if os.path.exists(actual_path) and os.path.getsize(actual_path) > 0:
                        return {
                            "success": True,
                            "filename": actual_filename,
                            "path": actual_path
                        }
                
                # Final failure
                raise FileNotFoundError("Could not find downloaded video file after multiple attempts")
            
    except Exception as e:
        logger.exception(f"Twitter download error: {str(e)}")
        return {
            "success": False,
            "error": "Failed to download Twitter/X video. Please check if the tweet is publicly accessible."
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
