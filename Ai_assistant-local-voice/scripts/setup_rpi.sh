#!/bin/bash
# Raspberry Pi Setup Script
# Installs all dependencies for RPi Voice Client
# Run this on your Raspberry Pi Zero 2W

set -e  # Exit on error

echo "🔧 Setting up Raspberry Pi Voice Client..."
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📦 Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    alsa-utils \
    bluealsa \
    libgpiod2 \
    python3-libgpiod \
    ffmpeg \
    python3-pip \
    python3-venv

echo ""
echo "🐍 Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

echo ""
echo "📚 Installing Python dependencies..."
pip install --upgrade pip
pip install \
    websocket-client \
    python-dotenv \
    pynput

echo ""
echo "⚙️  Creating configuration file..."
if [ ! -f ".env.rpi" ]; then
    cp .env.rpi.example .env.rpi
    echo "✅ Created .env.rpi (please edit with your server IP)"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Edit .env.rpi and set SERVER_IP to your Mac's IP address"
    echo "   2. Run: arecord -l  (to find your USB mic device)"
    echo "   3. Run: bash scripts/run_rpi_client.sh"
else
    echo "ℹ️  .env.rpi already exists (skipping)"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎤 Audio device check:"
echo "   Microphones:"
arecord -l || echo "   ⚠️  No recording devices found"
echo ""
echo "   Speakers:"
aplay -l || echo "   ⚠️  No playback devices found"
echo ""
echo "💡 Don't forget to:"
echo "   - Connect your Bluetooth headphones (run bt-audio-start.sh if you have it)"
echo "   - Update SERVER_IP in .env.rpi"
echo "   - Start the server on your Mac first!"
