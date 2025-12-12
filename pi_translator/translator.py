import sys
from deep_translator import GoogleTranslator
from requests.exceptions import ConnectionError, Timeout

def main():
    print("\n" + "="*40)
    print("   🌍 Free Google Translator for Pi")
    print("="*40)
    
    # Initialize translator
    # source='auto' is good, but specifying 'ru' can be slightly faster/more accurate if we know input is RU.
    # Let's stick to auto for flexibility, or 'ru' if user strictly said "RU -> EN".
    # User said: "Запрос пользователя (текст на русском) -> перевод"
    # Let's use auto to be safe, or allow user to switch? 
    # Simple is best: Auto -> English.
    
    try:
        translator = GoogleTranslator(source='auto', target='en')
        print("✅ Ready! No API Key needed.")
    except Exception as e:
        print(f"❌ Initialization Error: {e}")
        sys.exit(1)

    print("\n🔹 Ready to translate (Auto -> EN).")
    print("🔹 Type 'exit' or press Ctrl+C to quit.\n")

    while True:
        try:
            text = input("📝 Enter text: ").strip()
            
            if text.lower() in ('exit', 'quit'):
                print("👋 Goodbye!")
                break
            
            if not text:
                continue

            # Perform translation
            translation = translator.translate(text)
            
            print(f"🇺🇸 Translation: {translation}")
            print("-" * 20)

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except (ConnectionError, Timeout):
            print("⚠️  Network Error: Check your internet connection.")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
