# 🍓 Raspberry Pi Zero 2 W Setup Guide

This guide is tailored for your setup: **Pi Zero 2 W + Bluetooth Headphones (BlueALSA) + USB Microphone**.

## 1. System Dependencies
Install necessary packages for audio and image processing.

```bash
sudo apt-get update
sudo apt-get install -y \
    python3-opencv libopencv-dev \
    python3-pyaudio portaudio19-dev \
    mpg123 alsa-utils flac sox libsox-fmt-all \
    ffmpeg
```

## 2. Audio Configuration (The "Pain" Part)

### Bluetooth Audio (Output)
Ensure your Bluetooth headphones are connected and `bluealsa` is running.
If you have issues with PulseAudio blocking access:
```bash
pulseaudio --start
# OR if that fails, try sending audio directly to BlueALSA:
mpg123 -o alsa -a bluealsa "test.mp3"
```

### USB Microphone (Input)
1.  Plug in your USB Mic.
2.  Check if it's visible:
    ```bash
    arecord -l
    ```
    Look for "card 1" or similar. Usually it's `hw:1,0`.

### Physical Buttons (Control)
*   **Pin 6**: Connect to one side of ALL three buttons (GND).
*   **Pin 11 (GPIO 17)**: Button 1 (Voice AI Bro).
*   **Pin 13 (GPIO 27)**: Button 2 (Voice Translator).
*   **Pin 15 (GPIO 22)**: Button 3 (Image Interpreter).
*   **Logic**: The scripts use internal pull-up, so no resistors are needed.

3.  **Adjust Volume:**
    ```bash
    alsamixer
    ```
    *   Press `F6` -> Select USB Mic.
    *   Press `F4` -> Raise Capture volume to ~85%.
    *   Ensure it says `CAPTUR` (red), not just `L R`. Press `Space` to toggle.

## 3. Project Setup

1.  **Navigate to folder:**
    ```bash
    cd ~/Ai_image-interpretator
    ```

2.  **Install Python Libs:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run Diagnostic:**
    Use the helper script to find your correct Mic Index.
    ```bash
    python pi_audio_check.py
    ```

4.  **Configure `.env`:**
    Create/Edit `.env` file:
    ```bash
    nano .env
    ```
    Content:
    ```ini
    GEMINI_API_KEY=your_key_here
    MIC_INDEX=1   # For SpeechRecognition
    MIC_DEVICE=hw:1,0  # For arecord (Hold-to-record)
    CAMERA_INDEX=0
    ```

## 4. Running the AI
```bash
python image_interpreter.py
```

## 💡 Troubleshooting
*   **"Failed to add edge detection"**: This is a common issue on Pi OS Bookworm. 
    *   Fix: `sudo apt install python3-lgpio` and `pip install rpi-lgpio`.
    *   The script now has a **Polling Fallback**, so it should work even if edge detection fails.
*   **ALSA Warnings**: If you see many `ALSA lib...` errors, **ignore them**. This is normal on Pi Lite. As long as you see your USB Mic in the list, it will work.
*   **"Connection refused"**: PulseAudio is fighting BlueALSA. Try `pulseaudio -k` (kill) or `pulseaudio --start`.
*   **Mic Silence**: Check `alsamixer` again. USB mics often default to 0 volume.
