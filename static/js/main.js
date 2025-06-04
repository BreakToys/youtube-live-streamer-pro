document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const streamForm = document.getElementById('streamForm');
    const startButton = document.getElementById('startButton');
    const stopButton = document.getElementById('stopButton');
    const streamStatus = document.getElementById('streamStatus');
    const statusDot = streamStatus.querySelector('.status-dot');
    const statusText = streamStatus.querySelector('.status-text');
    const previewVideo = document.getElementById('previewVideo');
    const videoOverlay = document.getElementById('videoOverlay');
    const muteButton = document.getElementById('muteButton');
    const fullscreenButton = document.getElementById('fullscreenButton');
    const streamDuration = document.getElementById('streamDuration');
    const timeRemainingValue = document.getElementById('timeRemainingValue');
    const streamQuality = document.getElementById('streamQuality');
    const togglePasswordBtn = document.querySelector('.toggle-password');
    const streamKeyInput = document.getElementById('stream_key');

    let statusCheckInterval = null;
    let durationInterval = null;
    let startTime = null;

    // Toggle password visibility
    togglePasswordBtn.addEventListener('click', function() {
        const type = streamKeyInput.type === 'password' ? 'text' : 'password';
        streamKeyInput.type = type;
        togglePasswordBtn.innerHTML = type === 'password' ? 
            '<i class="fas fa-eye"></i>' : 
            '<i class="fas fa-eye-slash"></i>';
    });

    // Video preview controls
    muteButton.addEventListener('click', function() {
        previewVideo.muted = !previewVideo.muted;
        muteButton.innerHTML = previewVideo.muted ? 
            '<i class="fas fa-volume-mute"></i>' : 
            '<i class="fas fa-volume-up"></i>';
    });

    fullscreenButton.addEventListener('click', function() {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            previewVideo.requestFullscreen();
        }
    });

    // Format time function
    function formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }

    // Update stream duration
    function updateDuration() {
        if (startTime) {
            const duration = Math.floor((Date.now() - startTime) / 1000);
            streamDuration.textContent = formatTime(duration);
        }
    }

    // Update stream status
    function updateStreamStatus(status, type = 'info') {
        statusDot.className = 'status-dot';
        if (type === 'live') {
            statusDot.classList.add('live');
            statusText.textContent = 'Live';
        } else {
            statusText.textContent = status;
        }
    }

    // Setup video preview
    function setupVideoPreview(videoPath) {
        previewVideo.src = `/video/${encodeURIComponent(videoPath)}`;
        previewVideo.load();
        previewVideo.play().catch(error => {
            console.error('Error playing video:', error);
        });
        videoOverlay.style.display = 'none';
    }

    // Check stream status
    async function checkStreamStatus() {
        try {
            const response = await fetch('/stream-status');
            const data = await response.json();

            if (data.error) {
                clearInterval(statusCheckInterval);
                updateStreamStatus('Error', 'error');
                toggleButtons(false);
                return;
            }

            if (data.status === 'streaming') {
                updateStreamStatus('Streaming', 'live');
                if (data.time_remaining !== null) {
                    timeRemainingValue.textContent = formatTime(data.time_remaining);
                }
            } else {
                clearInterval(statusCheckInterval);
                clearInterval(durationInterval);
                updateStreamStatus('Ready');
                toggleButtons(false);
                videoOverlay.style.display = 'flex';
                if (previewVideo.srcObject) {
                    previewVideo.srcObject.getTracks().forEach(track => track.stop());
                    previewVideo.srcObject = null;
                }
            }
        } catch (error) {
            console.error('Error checking stream status:', error);
        }
    }

    // Toggle button states
    function toggleButtons(isStreaming) {
        startButton.disabled = isStreaming;
        stopButton.disabled = !isStreaming;
        if (isStreaming) {
            startButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Streaming...';
        } else {
            startButton.innerHTML = '<i class="fas fa-play"></i> Start Streaming';
            stopButton.innerHTML = '<i class="fas fa-stop"></i> Stop Streaming';
            streamDuration.textContent = '00:00:00';
            timeRemainingValue.textContent = '--:--:--';
        }
    }

    // Handle start streaming
    startButton.addEventListener('click', async function() {
        const driveLink = document.getElementById('drive_link').value.trim();
        const streamKey = document.getElementById('stream_key').value.trim();
        const resolution = document.getElementById('resolution').value;
        const autoStop = document.getElementById('auto_stop').value;

        if (!driveLink || !streamKey) {
            updateStreamStatus('Missing required fields', 'error');
            return;
        }

        try {
            toggleButtons(true);
            updateStreamStatus('Starting stream...');
            startButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';

            const response = await fetch('/start-stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    drive_link: driveLink,
                    stream_key: streamKey,
                    resolution: resolution,
                    orientation: orientation,
                    auto_stop: autoStop || null
                })
            });

            const data = await response.json();

            if (response.ok) {
                updateStreamStatus('Streaming', 'live');
                const orientation = document.getElementById('orientation').value;
                streamQuality.textContent = `${resolution}p (${orientation})`;
                startTime = Date.now();
                statusCheckInterval = setInterval(checkStreamStatus, 1000);
                durationInterval = setInterval(updateDuration, 1000);

                // Set up video preview
                if (data.video_path) {
                    previewVideo.src = `/video/${encodeURIComponent(data.video_path)}`;
                    previewVideo.load();
                    previewVideo.play().catch(error => {
                        console.error('Error playing video:', error);
                    });
                    videoOverlay.style.display = 'none';
                }
            } else {
                updateStreamStatus(data.error, 'error');
                toggleButtons(false);
            }
        } catch (error) {
            updateStreamStatus('Failed to start stream', 'error');
            toggleButtons(false);
            console.error('Error:', error);
        }
    });

    // Handle stop streaming
    stopButton.addEventListener('click', async function() {
        try {
            updateStreamStatus('Stopping stream...');
            stopButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Stopping...';
            stopButton.disabled = true;

            const response = await fetch('/stop-stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();

            if (response.ok) {
                updateStreamStatus('Ready');
                toggleButtons(false);
                clearInterval(statusCheckInterval);
                clearInterval(durationInterval);
                startTime = null;
                
                // Stop video preview
                previewVideo.pause();
                previewVideo.src = '';
                videoOverlay.style.display = 'flex';
            } else {
                updateStreamStatus(data.error, 'error');
                stopButton.disabled = false;
                stopButton.innerHTML = '<i class="fas fa-stop"></i> Stop Streaming';
            }
        } catch (error) {
            updateStreamStatus('Failed to stop stream', 'error');
            stopButton.disabled = false;
            stopButton.innerHTML = '<i class="fas fa-stop"></i> Stop Streaming';
            console.error('Error:', error);
        }
    });

    // Resolution change handler
    document.getElementById('resolution').addEventListener('change', function(e) {
        streamQuality.textContent = `${e.target.value}p`;
    });

    // Auto-stop input validation
    const autoStopInput = document.getElementById('auto_stop');
    autoStopInput.addEventListener('input', function() {
        const value = parseFloat(autoStopInput.value);
        if (value && (value <= 0 || value > 24)) {
            autoStopInput.setCustomValidity('Please enter a value between 0 and 24 hours');
        } else {
            autoStopInput.setCustomValidity('');
        }
    });

    // Initialize
    updateStreamStatus('Ready');
    previewVideo.muted = true;
});
