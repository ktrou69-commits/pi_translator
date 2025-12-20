import os
import sys
import time
import subprocess
import speech_recognition as sr
from deep_translator import GoogleTranslator
from gtts import gTTS

try:
    from gpiozero import Button
    GPIO_AVAILABLE = True
except (ImportError, OSError):
    GPIO_AVAILABLE = False

# --- SETTINGS ---
BUTTON_PIN = 27          # GPIO 27 (Pin 13)
TEMP_WAV = "input.wav"
ALSA_DEVICE = "bluealsa" # For Pi Lite Bluetooth

def speak(text, lang):
    """Synthesizes speech and plays it using robust Pi logic."""
    mp3_filename = "output_tts.mp3"
    wav_filename = "output_tts.wav"

    try:
        tts = gTTS(text=text, lang=lang)
        tts.save(mp3_filename)
        
        if sys.platform == "darwin": # macOS
            subprocess.run(['afplay', mp3_filename], check=True)
        else: # Linux (Raspberry Pi)
            # 1. Convert to WAV
            subprocess.run(["ffmpeg", "-y", "-i", mp3_filename, wav_filename],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # 2. Play via BlueALSA
            try:
                subprocess.run(['aplay', '-D', ALSA_DEVICE, wav_filename], 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            except:
                subprocess.run(['aplay', wav_filename], 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    except Exception as e:
        print(f"❌ TTS Error: {e}")
    finally:
        if os.path.exists(mp3_filename): os.remove(mp3_filename)
        if os.path.exists(wav_filename): os.remove(wav_filename)

def main():
    print("\n" + "="*50)
    print("   🎙️  Voice Translator (Button 2 Support)")
    print("="*50)

    r = sr.Recognizer()
    
    # Translation Modes
    modes = [
        {"in": "ru-RU", "out": "en", "label": "🇷🇺 RU -> 🇺🇸 EN"},
        {"in": "en-US", "out": "ru", "label": "🇺🇸 EN -> 🇷🇺 RU"}
    ]
    current_mode_idx = 0

    def toggle_mode():
        nonlocal current_mode_idx
        current_mode_idx = (current_mode_idx + 1) % len(modes)
        mode = modes[current_mode_idx]
        print(f"\n🔄 Switched to: {mode['label']}")
        speak("Режим изменен" if mode['out'] == 'ru' else "Mode changed", mode['out'])

    if GPIO_AVAILABLE:
        try:
            button = Button(BUTTON_PIN)
            button.when_double_clicked = toggle_mode
            print(f"✅ Button 2 initialized on GPIO {BUTTON_PIN} (Pin 13)")
            print("👉 HOLD to record, DOUBLE-CLICK to toggle language.")
            USE_POLLING = False
        except Exception as e:
            print(f"⚠️ Button error: {e}. Switching to POLLING mode.")
            button = None
            USE_POLLING = True
    else:
        print("⚠️ GPIO not available. Use ENTER to record, D to toggle.")
        USE_POLLING = False

    try:
        while True:
            mode = modes[current_mode_idx]
            
            if GPIO_AVAILABLE:
                if not USE_POLLING:
                    button.wait_for_press()
                else:
                    import RPi.GPIO as GPIO
                    GPIO.setmode(GPIO.BCM)
                    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                    while GPIO.input(BUTTON_PIN) == GPIO.HIGH:
                        time.sleep(0.05)
            else:
                cmd_in = input(f"\n[{mode['label']}] Press ENTER to record (or 'd' to toggle): ").strip().lower()
                if cmd_in == 'd':
                    toggle_mode()
                    continue

            # --- START RECORDING ---
            print("🎤 Listening...")
            mic_device = os.getenv("MIC_DEVICE", "hw:1,0")
            cmd = ["arecord", "-D", mic_device, "-f", "S16_LE", "-r", "16000", "-c", "1", TEMP_WAV]
            
            if sys.platform == "darwin":
                print("☁️ (Simulating recording on macOS...)")
                time.sleep(2)
                process = None
            else:
                process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if GPIO_AVAILABLE:
                if not USE_POLLING:
                    button.wait_for_release()
                else:
                    import RPi.GPIO as GPIO
                    while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                        time.sleep(0.05)
            else:
                input("🎤 ЗАПИСЬ... [ENTER] Остановить")

            # --- STOP RECORDING ---
            if process:
                process.terminate()
                process.wait()
            print("⏳ Translating...")

            # --- STT & TRANSLATE ---
            try:
                if os.path.exists(TEMP_WAV):
                    with sr.AudioFile(TEMP_WAV) as source:
                        audio = r.record(source)
                    text_in = r.recognize_google(audio, language=mode['in'])
                    print(f"🗣️  In: {text_in}")

                    if text_in:
                        translator = GoogleTranslator(source='auto', target=mode['out'])
                        translation = translator.translate(text_in)
                        print(f"🌍 Out: {translation}")
                        speak(translation, mode['out'])
                else:
                    print("⚠️ No audio recorded.")
            except Exception as e:
                print(f"❌ Error: {e}")
            finally:
                if os.path.exists(TEMP_WAV): os.remove(TEMP_WAV)

    except KeyboardInterrupt:
        print("\n👋 Bye!")

if __name__ == "__main__":
    main()
