#!/bin/bash

echo "🍓 Installing dependencies for AI Keychain (Pi Zero 2 W)..."

# 1. System Dependencies
echo "📦 Installing System Packages..."
sudo apt-get update
sudo apt-get install -y \
    python3-opencv libopencv-dev \
    python3-pyaudio portaudio19-dev \
    mpg123 alsa-utils flac sox libsox-fmt-all \
    ffmpeg python3-gpiozero python3-lgpio

# 2. Python Dependencies
echo "🐍 Installing Python Libraries..."
pip install -r requirements.txt

echo "✅ Done! All dependencies installed."
echo "📝 Don't forget to create .env files in each project folder!"
