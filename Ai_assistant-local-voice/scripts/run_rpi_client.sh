#!/bin/bash
# Launch script for Raspberry Pi Voice Client
# Usage: bash scripts/run_rpi_client.sh

cd "$(dirname "$0")/.."

echo "🚀 Starting RPi Voice Client..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the client
python3 app/rpi_client.py
