#!/bin/bash

# Exit on error
set -e

echo "Installing YouTube Live Streamer Pro..."

# Update package list
sudo apt-get update

# Install required system dependencies
echo "Installing system dependencies..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg

# Create virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p downloads

# Set up systemd service
echo "Setting up systemd service..."
cat > youtube-streamer.service << EOL
[Unit]
Description=YouTube Live Streamer Pro
After=network.target

[Service]
User=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin:$PATH"
ExecStart=$(pwd)/venv/bin/python -m flask run --host=0.0.0.0 --port=8000
Restart=always

[Install]
WantedBy=multi-user.target
EOL

sudo mv youtube-streamer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable youtube-streamer
sudo systemctl start youtube-streamer

echo "Installation completed successfully!"
echo "The application is now running on http://your-server-ip:8000"
echo "To check the service status, run: sudo systemctl status youtube-streamer"
