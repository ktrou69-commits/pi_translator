import os
import sys
import time
import speech_recognition as sr
from deep_translator import GoogleTranslator
from gtts import gTTS
from requests.exceptions import ConnectionError, Timeout

def play_audio(filename):
    """Plays audio file using mpg123 (lightweight player)."""
    # -q for quiet mode
    os.system(f"mpg123 -q {filename}")

def speak(text, lang):
    """Synthesizes speech and plays it."""
    try:
        tts = gTTS(text=text, lang=lang)
        filename = "output.mp3"
        tts.save(filename)
        play_audio(filename)
        os.remove(filename) # Clean up
    except Exception as e:
        print(f"❌ TTS Error: {e}")

def main():
    print("\n" + "="*50)
    print("   🎙️  Voice Translator (STT -> Translate -> TTS)")
    print("="*50)

    # Initialize Recognizer
    r = sr.Recognizer()
    
    # Adjust for ambient noise (optional, but good for Pi)
    r.dynamic_energy_threshold = True 

    # Language Setup
    # We will listen in Russian and translate to English/German
    # Or we can make it interactive. Let's start with RU -> EN default.
    
    input_lang = 'ru-RU'
    target_lang_code = 'en' # for translator
    tts_lang = 'en'         # for TTS
    
    print(f"🔹 Mode: 🇷🇺 Russian (Voice) -> 🇺🇸 English (Speech)")
    print("🔹 Press Ctrl+C to exit.")
    print("-" * 50)

    # Check for microphone
    try:
        with sr.Microphone() as source:
            print("🎤 Calibrating background noise... (please wait)")
            r.adjust_for_ambient_noise(source, duration=2)
            print("✅ Ready! Speak now.")
            
            while True:
                try:
                    print("\n👂 Listening...")
                    audio = r.listen(source, timeout=None) # Wait indefinitely for speech
                    
                    print("⏳ Recognizing...")
                    # Recognize speech using Google Speech Recognition
                    text_in = r.recognize_google(audio, language=input_lang)
                    print(f"🇷🇺  You said: {text_in}")
                    
                    if not text_in:
                        continue

                    # Translate
                    translator = GoogleTranslator(source='auto', target=target_lang_code)
                    translation = translator.translate(text_in)
                    print(f"🇺🇸  Translation: {translation}")
                    
                    # Speak
                    speak(translation, tts_lang)

                except sr.UnknownValueError:
                    print("🤷 Could not understand audio")
                except sr.RequestError as e:
                    print(f"⚠️  STT Service Error: {e}")
                except (ConnectionError, Timeout):
                     print("⚠️  Network Error")
                except KeyboardInterrupt:
                    print("\n👋 Goodbye!")
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
                    # Don't crash on temporary errors, just loop
                    
    except OSError as e:
        print(f"❌ Microphone Error: {e}")
        print("💡 Hint: Ensure USB microphone is connected and configured.")
        print("💡 Try running: 'arecord -l' to list devices.")
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
