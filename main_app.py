import os
import sys
import time
import json
import datetime
import subprocess
import cv2
import speech_recognition as sr
from dotenv import load_dotenv
from google import genai
from google.genai import types
from gtts import gTTS
from PIL import Image
from deep_translator import GoogleTranslator

try:
    from gpiozero import Button
    GPIO_AVAILABLE = True
except (ImportError, OSError):
    GPIO_AVAILABLE = False

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, ".env")) # Root .env

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("❌ Error: GEMINI_API_KEY not found in .env")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

# Paths
MEMORY_FILE = os.path.join(SCRIPT_DIR, "Ai_assistant-memory-voice/memory.json")
PHOTOS_DIR = os.path.join(SCRIPT_DIR, "Ai_image-interpretator/photos")
TEMP_WAV = os.path.join(SCRIPT_DIR, "temp_input.wav")

# Pins
BTN_ASSISTANT_PIN = 17 # Button 1 (Pin 11)
BTN_TRANSLATOR_PIN = 27 # Button 2 (Pin 13)
BTN_VISION_PIN = 22     # Button 3 (Pin 15)

# Audio Settings
ALSA_DEVICE = "bluealsa"
TTS_SPEED = 1.25
MIC_DEVICE = os.getenv("MIC_DEVICE", "hw:1,0")

# Translator State
trans_modes = [
    {"in": "ru-RU", "out": "en", "label": "🇷🇺 RU -> 🇺🇸 EN"},
    {"in": "en-US", "out": "ru", "label": "🇺🇸 EN -> 🇷🇺 RU"}
]
current_trans_idx = 0

# --- HELPERS ---
def load_memory():
    if not os.path.exists(MEMORY_FILE): return {"user_facts": []}
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except: return {"user_facts": []}

def save_memory(data):
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def speak(text, lang='ru'):
    print(f"🤖 AI ({lang}): {text}")
    mp3 = os.path.join(SCRIPT_DIR, "output.mp3")
    wav = os.path.join(SCRIPT_DIR, "output.wav")
    try:
        gTTS(text=text, lang=lang).save(mp3)
        if sys.platform == "darwin":
            subprocess.run(['afplay', '--rate', str(TTS_SPEED), mp3])
        else:
            subprocess.run(["ffmpeg", "-y", "-i", mp3, wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                subprocess.run(['aplay', '-D', ALSA_DEVICE, wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            except:
                subprocess.run(['aplay', wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e: print(f"❌ TTS Error: {e}")
    finally:
        for f in [mp3, wav]:
            if os.path.exists(f): os.remove(f)

def record_voice(button_pin, use_polling):
    print("🎤 Listening...")
    cmd = ["arecord", "-D", MIC_DEVICE, "-f", "S16_LE", "-r", "16000", "-c", "1", TEMP_WAV]
    if sys.platform == "darwin":
        print("(Simulating recording...)"); time.sleep(2); return True
    
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if GPIO_AVAILABLE:
        if not use_polling:
            Button(button_pin).wait_for_release()
        else:
            import RPi.GPIO as GPIO
            while GPIO.input(button_pin) == GPIO.LOW: time.sleep(0.05)
    else:
        input("🎤 Recording... Press ENTER to stop")
    
    process.terminate()
    process.wait()
    return os.path.exists(TEMP_WAV)

def get_stt(lang="ru-RU"):
    r = sr.Recognizer()
    try:
        with sr.AudioFile(TEMP_WAV) as source:
            audio = r.record(source)
        return r.recognize_google(audio, language=lang)
    except: return None

# --- CORE LOGIC ---
def handle_assistant(memory, use_polling):
    if record_voice(BTN_ASSISTANT_PIN, use_polling):
        text = get_stt("ru-RU")
        if not text: return
        print(f"🗣️ You: {text}")
        
        # 1. Observer (Fact Extraction)
        sys_obs = "Ты - ИИ-Архивариус. Если пользователь сказал факт о себе, верни JSON: {\"new_fact\": \"факт\"}. Иначе {}"
        try:
            resp = client.models.generate_content(model="gemini-2.5-flash", config=types.GenerateContentConfig(system_instruction=sys_obs, response_mime_type="application/json"), contents=text)
            new_fact = json.loads(resp.text).get("new_fact")
            if new_fact:
                today = datetime.date.today().isoformat()
                memory["user_facts"].append({"text": new_fact, "created_at": today})
                save_memory(memory); print(f"🧠 Saved: {new_fact}")
        except: pass

        # 2. Chat
        facts = "\n".join([f"- {f['text']}" for f in memory["user_facts"]])
        sys_chat = f"Ты - лучший кент, ИИ-братан. Стиль: на 'ты', юмор, кратко. ПАМЯТЬ:\n{facts}"
        try:
            resp = client.models.generate_content(model="gemini-2.5-flash", config=types.GenerateContentConfig(system_instruction=sys_chat), contents=text)
            speak(resp.text, 'ru')
        except: speak("Бро, связь лагает...", 'ru')

def handle_translator(use_polling):
    mode = trans_modes[current_trans_idx]
    if record_voice(BTN_TRANSLATOR_PIN, use_polling):
        text = get_stt(mode["in"])
        if not text: return
        print(f"🗣️ In: {text}")
        try:
            translation = GoogleTranslator(source='auto', target=mode["out"]).translate(text)
            speak(translation, mode["out"])
        except: print("❌ Translation error")

def handle_vision(memory, use_polling):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    photo_path = os.path.join(PHOTOS_DIR, f"photo_{timestamp}.jpg")
    
    # Take Photo
    cap = cv2.VideoCapture(int(os.getenv("CAMERA_INDEX", 0)))
    time.sleep(0.5); ret, frame = cap.read(); cap.release()
    if not ret: speak("Камера не пашет", 'ru'); return
    cv2.imwrite(photo_path, frame); print(f"📸 Photo: {photo_path}")

    # Check for hold
    is_holding = False
    time.sleep(0.3)
    if GPIO_AVAILABLE:
        import RPi.GPIO as GPIO
        if GPIO.input(BTN_VISION_PIN) == GPIO.LOW: is_holding = True
    
    user_text = "Что на фото?"
    if is_holding:
        if record_voice(BTN_VISION_PIN, use_polling):
            user_text = get_stt("ru-RU") or user_text
    
    # Analyze
    facts = "\n".join([f"- {f['text']}" for f in memory["user_facts"]])
    sys_vision = f"Ты - ИИ-Кент с глазами. Ответь кратко и с юмором. ПАМЯТЬ:\n{facts}"
    try:
        img = Image.open(photo_path)
        resp = client.models.generate_content(model="gemini-2.5-flash", config=types.GenerateContentConfig(system_instruction=sys_vision), contents=[user_text, img])
        speak(resp.text, 'ru')
    except: speak("Я ослеп, бро...", 'ru')

# --- MAIN ---
def main():
    print("\n🚀 AI Keychain Unified App Starting...")
    if not os.path.exists(PHOTOS_DIR): os.makedirs(PHOTOS_DIR)
    
    memory = load_memory()
    use_polling = False
    
    if GPIO_AVAILABLE:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        for pin in [BTN_ASSISTANT_PIN, BTN_TRANSLATOR_PIN, BTN_VISION_PIN]:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        use_polling = True # Using manual polling for maximum reliability on Pi
        print("✅ Buttons ready (GPIO Polling Mode)")
    else:
        print("⚠️ GPIO not available. Running in PC mode.")

    speak("Система запущена. Я на связи!", 'ru')

    try:
        while True:
            if GPIO_AVAILABLE:
                import RPi.GPIO as GPIO
                if GPIO.input(BTN_ASSISTANT_PIN) == GPIO.LOW:
                    handle_assistant(memory, True)
                elif GPIO.input(BTN_TRANSLATOR_PIN) == GPIO.LOW:
                    # Check for double click or hold
                    start = time.time()
                    while GPIO.input(BTN_TRANSLATOR_PIN) == GPIO.LOW: time.sleep(0.01)
                    duration = time.time() - start
                    
                    if duration < 0.3: # Possible double click
                        time.sleep(0.2)
                        if GPIO.input(BTN_TRANSLATOR_PIN) == GPIO.LOW:
                            global current_trans_idx
                            current_trans_idx = (current_trans_idx + 1) % 2
                            mode = trans_modes[current_trans_idx]
                            speak(f"Режим {mode['label']}", 'ru')
                        else:
                            # Single click - do nothing or record? 
                            # User said: Hold to record, Double click to toggle.
                            pass
                    else: # Hold
                        handle_translator(True)
                
                elif GPIO.input(BTN_VISION_PIN) == GPIO.LOW:
                    handle_vision(memory, True)
                
                time.sleep(0.05)
            else:
                cmd = input("\n[1] Assistant [2] Translator [3] Vision [D] Toggle Lang: ").lower()
                if cmd == '1': handle_assistant(memory, False)
                elif cmd == '2': handle_translator(False)
                elif cmd == '3': handle_vision(memory, False)
                elif cmd == 'd':
                    current_trans_idx = (current_trans_idx + 1) % 2
                    print(f"Mode: {trans_modes[current_trans_idx]['label']}")
    except KeyboardInterrupt:
        print("\n👋 Bye!")

if __name__ == "__main__":
    main()
