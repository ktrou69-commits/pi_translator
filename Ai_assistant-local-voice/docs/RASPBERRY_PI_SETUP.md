# 🍓 Raspberry Pi Voice Client Setup Guide

This guide describes how to set up your Raspberry Pi Zero 2W (or any other RPi) as a wireless voice client for the AI Assistant.

## 📋 Prerequisites

### Hardware
- **Raspberry Pi Zero 2W** (recommended) or RPi 3/4/5
- **USB Microphone** (standard PnP audio device)
- **Bluetooth Headphones** / Speaker
- **MicroSD Card** (8GB+) with Raspberry Pi OS (Bookworm recommended)
- **Power Supply** (reliable 2A+)

### Optional (for Button Operation)
- **Tactile Switch (Button)**
- **Jumper Wires** (Female-to-Female if using GPIO header)

## 🔌 GPIO Wiring (Button)
Connect the button between **GPIO 17 (Pin 11)** and **GND (Pin 9 or 6)**.

```
       RPi GPIO Header
      +-----------------+
      |                 |
      | [ ] [ ] 5V      |
      | [ ] [ ] 5V      |
      | [ ] [X] GND <-----+
      | [X] [ ] GPIO 17 <-+--[ BUTTON ]
      | [ ] [ ]         |
      | ...             |
```

## 🚀 Installation

### 1. Clone the Repository (on Raspberry Pi)
```bash
git clone <your-repo-url>
cd Ai_assistant-local-voice
```

### 2. Run the Setup Script
This script installs all necessary system packages (ALSA, BlueALSA, GPIO) and Python dependencies.
```bash
bash scripts/setup_rpi.sh
```

### 3. Configure Network & Devices
The setup script creates a `.env.rpi` file. Edit it:
```bash
nano .env.rpi
```

**Key settings:**
- `SERVER_IP`: IP address of your Mac running the server (e.g., `192.168.1.100`)
- `MIC_DEVICE`: Run `arecord -l` to find it (usually `hw:1,0`)
- `SPEAKER_DEVICE`: Usually `bluealsa` (ensure BT is connected!)

---

## 🎧 Audio Setup (Bluetooth Headphones)
Before running the client, ensure your Bluetooth headphones are paired and connected.

**Helper Script:** If you have `bt-audio-start.sh` from previous projects (pi_translator), run it:
```bash
./bt-audio-start.sh
```

**Manual Test:**
```bash
# Test Speaker
aplay -D bluealsa /usr/share/sounds/alsa/Front_Center.wav

# Test Mic (record 5s)
arecord -D hw:1,0 -f S16_LE -r 16000 -d 5 test.wav
aplay -D bluealsa test.wav
```

---

## 🏃‍♂️ Running the Client

### Option A: GPIO Button Mode (Recommended)
Hold the button to talk, release to send.
```bash
bash scripts/run_rpi_gpio.sh
```

### Option B: Keyboard Mode (Testing)
Press **SPACE** to record, release to send.
```bash
bash scripts/run_rpi_client.sh
```

---

## 🛠️ Troubleshooting

### "Connection Refused"
- Ensure the server is running on Mac: `bash run_groq.sh`
- Check `SERVER_IP` in `.env.rpi`
- Ensure both devices are on the same WiFi network

### "BlueALSA not found"
- Restart the Bluetooth service: `sudo systemctl restart bluetooth`
- Reconnect headphones

### "GPIO not available"
- Ensure you installed `libgpiod2`: `sudo apt install libgpiod2`
- Check wiring

### Audio Latency / Glitches
- The default chunk size is 1024. If audio stutters, try increasing `CHUNK_SIZE` in `.env.rpi`.
