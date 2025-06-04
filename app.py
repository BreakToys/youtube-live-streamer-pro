from flask import Flask, request, render_template, jsonify, send_file
import os
import threading
import signal
from utils import download_file, start_ffmpeg_stream, stop_ffmpeg_stream, get_time_remaining

app = Flask(__name__)

# Global variables
ffmpeg_process = None
process_lock = threading.Lock()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video/<path:filename>')
def serve_video(filename):
    """Serve the video file for preview"""
    return send_file(filename)

@app.route('/start-stream', methods=['POST'])
def start_stream():
    global ffmpeg_process
    try:
        data = request.get_json()
        drive_link = data.get('drive_link')
        stream_key = data.get('stream_key')
        resolution = data.get('resolution', '720')
        auto_stop = data.get('auto_stop')

        if not drive_link or not stream_key:
            return jsonify({"error": "Missing drive_link or stream_key"}), 400

        # Validate resolution
        if resolution not in ['360', '480', '720', '1080', '2160']:
            return jsonify({"error": "Invalid resolution"}), 400

        # Validate auto-stop time
        if auto_stop is not None:
            try:
                auto_stop = float(auto_stop)
                if auto_stop <= 0 or auto_stop > 24:
                    return jsonify({"error": "Auto-stop time must be between 0 and 24 hours"}), 400
            except ValueError:
                return jsonify({"error": "Invalid auto-stop time"}), 400

        # Download the video file from Google Drive
        local_file, download_error = download_file(drive_link)
        if download_error:
            return jsonify({"error": download_error}), 400

        with process_lock:
            # Check if a streaming process is already running
            if ffmpeg_process is not None and ffmpeg_process.poll() is None:
                return jsonify({"error": "Streaming already in progress"}), 400

            # Get orientation setting
            orientation = data.get('orientation', 'horizontal')
            if orientation not in ['horizontal', 'vertical']:
                return jsonify({"error": "Invalid orientation"}), 400

            # Start the ffmpeg streaming process
            process, stream_error = start_ffmpeg_stream(
                local_file, 
                stream_key, 
                resolution=resolution,
                orientation=orientation,
                auto_stop_hours=auto_stop
            )
            
            if stream_error:
                return jsonify({"error": stream_error}), 500

            ffmpeg_process = process

        response_data = {
            "message": "Streaming started successfully",
            "resolution": f"{resolution}p",
            "video_path": local_file
        }

        if auto_stop:
            response_data["auto_stop"] = {
                "hours": auto_stop,
                "seconds": auto_stop * 3600
            }

        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/stop-stream', methods=['POST'])
def stop_stream():
    global ffmpeg_process
    try:
        with process_lock:
            if ffmpeg_process is None or ffmpeg_process.poll() is not None:
                return jsonify({"error": "No streaming process is running"}), 400

            # Stop the streaming process gracefully
            success, error = stop_ffmpeg_stream(ffmpeg_process)
            ffmpeg_process = None

            if not success:
                return jsonify({"error": error or "Failed to stop streaming"}), 500

        return jsonify({"message": "Streaming stopped successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/stream-status', methods=['GET'])
def stream_status():
    global ffmpeg_process
    try:
        with process_lock:
            if ffmpeg_process is None or ffmpeg_process.poll() is not None:
                return jsonify({
                    "status": "stopped",
                    "time_remaining": None
                })

            time_remaining = get_time_remaining(ffmpeg_process)
            return jsonify({
                "status": "streaming",
                "time_remaining": time_remaining
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True, threaded=True)
