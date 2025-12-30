#!/bin/bash
# Launch script for Raspberry Pi Voice Client with GPIO Button
# Usage: bash scripts/run_rpi_gpio.sh

cd "$(dirname "$0")/.."

echo "🚀 Starting RPi Voice Client (GPIO Button Mode)..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the GPIO-enabled client
python3 app/rpi_client_gpio.py
