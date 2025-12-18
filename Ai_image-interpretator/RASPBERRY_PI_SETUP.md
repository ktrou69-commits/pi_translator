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
    Look for "card 1" or similar.

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
    MIC_INDEX=1  # Change this to what the diagnostic script showed!
    CAMERA_INDEX=0
    ```

## 4. Running the AI
```bash
python image_interpreter.py
```

## 💡 Troubleshooting
*   **"Connection refused"**: PulseAudio is fighting BlueALSA. Try `pulseaudio -k` (kill) or `pulseaudio --start`.
*   **Mic Silence**: Check `alsamixer` again. USB mics often default to 0 volume.
*   **Slow TTS**: The script tries to speed up audio. If `sox` fails, it falls back to normal speed. Ensure `libsox-fmt-all` is installed.
