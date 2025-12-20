import os
import subprocess
import speech_recognition as sr
from gtts import gTTS
import time

def print_header(text):
    print("\n" + "="*40)
    print(f"   {text}")
    print("="*40)

def check_microphone():
    print_header("🎤 MICROPHONE CHECK")
    mics = sr.Microphone.list_microphone_names()
    
    if not mics:
        print("❌ No microphones found!")
        return None

    print("Available Microphones:")
    usb_mic_index = None
    
    for i, name in enumerate(mics):
        print(f"[{i}] {name}")
        if "USB" in name or "PnP" in name:
            usb_mic_index = i
            
    if usb_mic_index is not None:
        print(f"\n✅ Found likely USB Mic at Index: {usb_mic_index}")
        return usb_mic_index
    else:
        print("\n⚠️ No obvious USB mic found. Please identify yours from the list.")
        return 0

def check_speaker():
    print_header("🔊 SPEAKER CHECK (BlueALSA)")
    
    text = "Проверка звука на Raspberry Pi."
    tts = gTTS(text=text, lang='ru')
    tts.save("test_audio.mp3")
    
    print("Attempting to play via 'aplay -D bluealsa'...")
    
    # Convert to WAV for aplay (using ffmpeg as it's robust)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", "test_audio.mp3", "test_audio.wav"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
        )
    except FileNotFoundError:
        print("❌ 'ffmpeg' not found. Please install: sudo apt install ffmpeg")
        return

    # Play
    try:
        subprocess.run(["aplay", "-D", "bluealsa", "test_audio.wav"], check=True)
        print("✅ Audio command executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Audio playback failed: {e}")
        print("Try running: aplay -D bluealsa test_audio.wav")

    # Cleanup
    if os.path.exists("test_audio.mp3"): os.remove("test_audio.mp3")
    if os.path.exists("test_audio.wav"): os.remove("test_audio.wav")

def check_button():
    print_header("🔘 BUTTON CHECK (GPIO 17 / Pin 11)")
    try:
        from gpiozero import Button
        button = Button(17)
        print("Waiting for button press... (Press it now!)")
        button.wait_for_press(timeout=10)
        if button.is_pressed:
            print("✅ Button press DETECTED!")
        else:
            print("❌ Timeout: No button press detected.")
    except Exception as e:
        print(f"⚠️ Button check failed: {e}")
        print("Ensure 'gpiozero' is installed and you are on a Raspberry Pi.")

def main():
    print("🍓 Raspberry Pi Audio Diagnostic Tool 🍓")
    
    mic_idx = check_microphone()
    check_speaker()
    check_button()
    
    print_header("📝 SUGGESTED .env CONFIG")
    print(f"MIC_INDEX={mic_idx if mic_idx is not None else 0}")
    print(f"MIC_DEVICE=hw:{mic_idx if mic_idx is not None else 1},0")
    print("CAMERA_INDEX=0")
    print("\nCopy these values to your .env file!")

if __name__ == "__main__":
    main()
