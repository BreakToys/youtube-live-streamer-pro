import os
import tempfile
import requests
import subprocess
import signal
import re
import threading
import time

def extract_file_id(gdrive_url):
    """Extract the file ID from various Google Drive URL formats."""
    patterns = [
        r'https://drive\.google\.com/file/d/([\w-]+)',
        r'https://drive\.google\.com/open\?id=([\w-]+)',
        r'https://drive\.google\.com/uc\?id=([\w-]+)',
        r'id=([\w-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, gdrive_url)
        if match:
            return match.group(1)
    return None

def download_file(gdrive_url):
    """
    Download the file from a public Google Drive link.
    Returns a tuple of (file_path, error_message).
    file_path will be None if there was an error.
    """
    temp_path = None
    try:
        # Extract file ID from the URL
        file_id = extract_file_id(gdrive_url)
        
        if not file_id:
            return None, "Invalid Google Drive URL format"

        # Construct the direct download URL
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

        # Create a temporary file to store the downloaded video
        temp_fd, temp_path = tempfile.mkstemp(suffix=".mp4")
        os.close(temp_fd)

        # Download the file with a streaming request
        response = requests.get(download_url, stream=True)
        
        if response.status_code == 404:
            return None, "Video file not found. Make sure the file exists and is publicly accessible."
        elif response.status_code != 200:
            return None, f"Failed to download file. Status code: {response.status_code}"

        # Check content type to ensure it's a video file
        content_type = response.headers.get('content-type', '')
        if not content_type.startswith(('video/', 'application/octet-stream')):
            return None, "The provided file is not a video file"

        # Write the file in chunks to handle large files
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return temp_path, None

    except requests.exceptions.RequestException as e:
        return None, f"Network error: {str(e)}"
    except Exception as e:
        return None, f"Error downloading file: {str(e)}"
    finally:
        if temp_path and os.path.exists(temp_path) and 'error' in locals():
            try:
                os.remove(temp_path)
            except:
                pass

def start_ffmpeg_stream(file_path, stream_key, resolution="720", orientation="horizontal", auto_stop_hours=None):
    """
    Start the FFmpeg process to stream the downloaded file to YouTube.
    Returns a tuple of (process, error_message).
    process will be None if there was an error.
    """
    try:
        if not os.path.exists(file_path):
            return None, "Video file not found"

        if not stream_key:
            return None, "Stream key is required"

        # Get video dimensions
        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            file_path
        ]
        
        probe_output = subprocess.check_output(probe_cmd, universal_newlines=True)
        original_width, original_height = map(int, probe_output.strip().split(','))

        # Calculate dimensions based on orientation and resolution
        target_height = int(resolution)
        
        if orientation == "vertical":
            # For vertical video, swap width and height calculations
            target_width = int((target_height * 9) / 16)  # 9:16 aspect ratio
            vf_filters = [
                "transpose=1",  # Rotate 90 degrees clockwise
                f"scale={target_width}:{target_height}",
                "setdar=9/16"  # Set display aspect ratio
            ]
        else:
            # For horizontal video, maintain 16:9 aspect ratio
            target_width = int((target_height * 16) / 9)
            vf_filters = [
                f"scale={target_width}:{target_height}",
                "setdar=16/9"
            ]

        # Ensure dimensions are even numbers
        target_width = target_width - (target_width % 2)
        target_height = target_height - (target_height % 2)

        # Construct the RTMP URL
        rtmp_url = f"rtmp://a.rtmp.youtube.com/live2/{stream_key}"
        
        # Build the FFmpeg command
        cmd = [
            "ffmpeg",
            "-re",
            "-i", file_path,
            "-vf", ",".join(vf_filters),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-b:v", f"{target_height * 2}k",  # Adjust bitrate based on resolution
            "-maxrate", f"{target_height * 2.5}k",
            "-bufsize", f"{target_height * 4}k",
            "-c:a", "aac",
            "-b:a", "128k",
            "-f", "flv",
            rtmp_url
        ]

        # Start FFmpeg process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        # Store the temp file path with the process for cleanup
        process.temp_file = file_path
        
        # Check if process started successfully
        if process.poll() is not None:
            return None, "Failed to start FFmpeg process"

        # Set up auto-stop timer if specified
        if auto_stop_hours:
            stop_timer = threading.Timer(
                float(auto_stop_hours) * 3600,  # Convert hours to seconds
                stop_ffmpeg_stream,
                args=(process,)
            )
            stop_timer.daemon = True
            process.stop_timer = stop_timer
            stop_timer.start()

        return process, None

    except subprocess.CalledProcessError:
        return None, "Failed to get video information"
    except FileNotFoundError:
        return None, "FFmpeg is not installed or not found in system path"
    except Exception as e:
        return None, f"Error starting FFmpeg process: {str(e)}"

def stop_ffmpeg_stream(process):
    """
    Stop the FFmpeg streaming process gracefully.
    Returns a tuple of (success, error_message).
    """
    try:
        if process is None or process.poll() is not None:
            return False, "No active streaming process found"

        # Cancel auto-stop timer if it exists
        if hasattr(process, 'stop_timer'):
            process.stop_timer.cancel()

        # Try graceful shutdown with SIGINT (Ctrl+C)
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
            return True, None
        except subprocess.TimeoutExpired:
            pass

        # If still running, try SIGTERM
        process.terminate()
        try:
            process.wait(timeout=5)
            return True, None
        except subprocess.TimeoutExpired:
            pass

        # If still running, force kill
        process.kill()
        process.wait()
        return True, None

    except Exception as e:
        return False, f"Error stopping FFmpeg process: {str(e)}"
    finally:
        # Clean up any temporary files
        try:
            if hasattr(process, 'temp_file') and os.path.exists(process.temp_file):
                os.remove(process.temp_file)
        except:
            pass

def get_time_remaining(process):
    """
    Get the remaining time for auto-stop if set.
    Returns remaining time in seconds or None if no auto-stop is set.
    """
    if hasattr(process, 'stop_timer') and process.stop_timer.is_alive():
        return process.stop_timer._when - time.time()
    return None
