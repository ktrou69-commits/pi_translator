import os
import sys
from deep_translator import GoogleTranslator
from gtts import gTTS
from requests.exceptions import ConnectionError, Timeout

def play_audio(filename):
    """Plays audio file using mpg123."""
    # -q for quiet mode
    if sys.platform == "darwin": # Mac
        os.system(f"afplay {filename}")
    else: # Linux/Pi
        os.system(f"mpg123 -q {filename}")

def speak(text, lang):
    """Synthesizes speech and plays it."""
    try:
        tts = gTTS(text=text, lang=lang)
        filename = "output_tts.mp3"
        tts.save(filename)
        play_audio(filename)
        os.remove(filename) 
    except Exception as e:
        print(f"❌ TTS Error: {e}")

def main():
    print("\n" + "="*50)
    print("   🗣️  Text-to-Speech Translator")
    print("   (Type text -> Hear translation)")
    print("="*50)
    
    try:
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

            # Translate
            translation = translator.translate(text)
            print(f"🇺🇸 Translation: {translation}")
            
            # Speak
            print("🔈 Speaking...")
            speak(translation, 'en')
            print("-" * 20)

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except (ConnectionError, Timeout):
            print("⚠️  Network Error.")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
