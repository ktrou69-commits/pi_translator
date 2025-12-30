"""
Raspberry Pi Client Configuration
Centralized configuration management for RPi client
"""
import os
from dotenv import load_dotenv

# Load environment variables
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(SCRIPT_DIR, ".env.rpi")
if not os.path.exists(ENV_FILE):
    ENV_FILE = os.path.join(SCRIPT_DIR, ".env.local")
if not os.path.exists(ENV_FILE):
    ENV_FILE = os.path.join(SCRIPT_DIR, ".env")

load_dotenv(ENV_FILE)

# Server connection
SERVER_IP = os.getenv("SERVER_IP", "192.168.1.100")  # Mac server IP
WS_URL = f"ws://{SERVER_IP}:8000/ws"

# Audio devices
MIC_DEVICE = os.getenv("MIC_DEVICE", "hw:1,0")  # USB microphone
SPEAKER_DEVICE = os.getenv("SPEAKER_DEVICE", "bluealsa")  # Bluetooth speaker

# Audio parameters
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))  # 16kHz for Whisper
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1024"))  # Bytes per chunk
AUDIO_FORMAT = "S16_LE"  # 16-bit signed little-endian
CHANNELS = 1  # Mono

# GPIO configuration
GPIO_BUTTON_PIN = int(os.getenv("GPIO_BUTTON_PIN", "17"))  # GPIO 17 (Pin 11)
GPIO_DEBOUNCE_MS = int(os.getenv("GPIO_DEBOUNCE_MS", "50"))  # 50ms debounce

# Connection settings
RECONNECT_DELAY_INITIAL = 1  # seconds
RECONNECT_DELAY_MAX = 30  # seconds
RECONNECT_BACKOFF_MULTIPLIER = 2

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Print configuration on import (for debugging)
if __name__ == "__main__":
    print("=== RPi Client Configuration ===")
    print(f"Server: {WS_URL}")
    print(f"Microphone: {MIC_DEVICE}")
    print(f"Speaker: {SPEAKER_DEVICE}")
    print(f"GPIO Button: Pin {GPIO_BUTTON_PIN}")
    print(f"Sample Rate: {SAMPLE_RATE}Hz")
    print(f"Chunk Size: {CHUNK_SIZE} bytes")
