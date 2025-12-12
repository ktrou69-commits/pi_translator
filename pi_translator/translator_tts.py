import os
import sys
import subprocess
from deep_translator import GoogleTranslator
from gtts import gTTS
from requests.exceptions import ConnectionError, Timeout

# --- ГЛОБАЛЬНЫЕ НАСТРОЙКИ ALSA ---
# Принудительно используем ваше устройство BlueALSA
ALSA_DEVICE = "bluealsa" 
# ---

def speak(text, lang):
    """
    Синтезирует речь с помощью gTTS, конвертирует в WAV 
    и воспроизводит через системную утилиту aplay.
    Это надежный метод для Raspberry Pi OS Lite.
    """
    mp3_filename = "output_tts.mp3"
    wav_filename = "output_tts.wav"

    print("🔈 Generating TTS file...")

    try:
        # 1. ГЕНЕРАЦИЯ: gTTS -> MP3
        tts = gTTS(text=text, lang=lang)
        tts.save(mp3_filename)
        
        # 2. КОНВЕРТАЦИЯ: MP3 -> WAV (с помощью mpg123)
        print("🛠️ Converting MP3 to WAV...")
        subprocess.run(
            ['mpg123', '-w', wav_filename, mp3_filename], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL, 
            check=True
        )

        # 3. ВОСПРОИЗВЕДЕНИЕ: WAV -> BlueALSA (с помощью aplay)
        print("🔊 Playing via APLAY...")
        subprocess.run(
            ['aplay', '-D', ALSA_DEVICE, wav_filename],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )

    except subprocess.CalledProcessError as e:
        print(f"❌ Playback Error: mpg123 or aplay failed. Check if BlueALSA is running. Error: {e}")
    except FileNotFoundError:
        print("❌ System Error: Check if 'mpg123' and 'aplay' are installed.")
        print("Run (outside venv): sudo apt install mpg123 alsa-utils")
    except Exception as e:
        print(f"❌ TTS Error: {e}")
    
    finally:
        # 4. ОЧИСТКА: Удаляем временные файлы
        if os.path.exists(mp3_filename):
            os.remove(mp3_filename)
        if os.path.exists(wav_filename):
            os.remove(wav_filename)


def main():
    print("\n" + "="*50)
    print("  🗣️  Text-to-Speech Translator")
    print("  (Type text -> Hear translation)")
    print("="*50)
    
    try:
        # Инициализация переводчика
        translator = GoogleTranslator(source='auto', target='en')
        print("✅ Ready! Type in Russian, hear in English.")
    except Exception as e:
        print(f"❌ Initialization Error: {e}")
        sys.exit(1)

    print("🔹 Type 'exit' to quit.\n")

    while True:
        try:
            text = input("📝 Enter text: ").strip()

            if text.lower() in ('exit', 'quit'):
                print("👋 Goodbye!")
                break

            if not text:
                continue

            # 1. Translate
            translation = translator.translate(text)

            # 2. Output
            print(f"🇺🇸 Translation: {translation}")

            # 3. Speak (using the new reliable function)
            speak(translation, 'en')
            
        except ConnectionError:
            print("❌ Connection Error. Check your Internet connection.")
        except Timeout:
            print("❌ Request Timed Out. Please try again.")
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
        finally:
            print("-" * 20)

if __name__ == "__main__":
    main()
