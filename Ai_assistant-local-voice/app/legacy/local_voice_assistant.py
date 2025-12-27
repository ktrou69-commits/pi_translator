import os
import sys
import json
import time
import subprocess
import speech_recognition as sr
from dotenv import load_dotenv
import ollama
import edge_tts
import asyncio
import datetime

try:
    from gpiozero import Button
    GPIO_AVAILABLE = True
except (ImportError, OSError):
    GPIO_AVAILABLE = False

# Get absolute path of the script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables from the script directory
# Use .env.local if .env is blocked/ignored
ENV_FILE = os.path.join(SCRIPT_DIR, ".env.local")
if not os.path.exists(ENV_FILE):
    ENV_FILE = os.path.join(SCRIPT_DIR, ".env")
load_dotenv(ENV_FILE)

MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")

MEMORY_FILE = os.path.join(SCRIPT_DIR, "memory.json")
ALSA_DEVICE = "bluealsa" # For Pi Lite Bluetooth
BUTTON_PIN = 17          # GPIO 17 (Pin 11)
TEMP_WAV = os.path.join(SCRIPT_DIR, "input.wav")

# --- MEMORY FUNCTIONS ---
def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {"user_facts": []}
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Migration check: if facts are strings, convert to objects
            if data.get("user_facts") and isinstance(data["user_facts"][0], str):
                today = datetime.date.today().isoformat()
                data["user_facts"] = [{"text": f, "created_at": today} for f in data["user_facts"]]
                save_memory(data)
            return data
    except (json.JSONDecodeError, KeyError):
        return {"user_facts": []}

def save_memory(memory_data):
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(memory_data, f, ensure_ascii=False, indent=2)

# --- AUDIO FUNCTIONS ---
TTS_SPEED = 1.25 # Speed multiplier (1.0 = normal, 1.5 = fast)

def speak(text, lang='ru'):
    """TTS with cross-platform support and SPEED CONTROL."""
    mp3_filename = os.path.join(SCRIPT_DIR, "output_tts.mp3")
    wav_filename = os.path.join(SCRIPT_DIR, "output_tts.wav")

    try:
        # 1. Generate MP3 with EdgeTTS
        voice = "ru-RU-SvetlanaNeural" if lang == 'ru' else "en-US-AvaNeural"
        communicate = edge_tts.Communicate(text, voice)
        asyncio.run(communicate.save(mp3_filename))
        
        if sys.platform == "darwin": # macOS
            subprocess.run(['afplay', '--rate', str(TTS_SPEED), mp3_filename], check=True)
            
        else: # Linux (Raspberry Pi)
            # 1. Try converting to WAV using ffmpeg (Most robust for Pi)
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", mp3_filename, wav_filename],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
                )
                
                # 2. Play using aplay via BlueALSA
                try:
                    subprocess.run(['aplay', '-D', 'bluealsa', wav_filename], 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                except:
                    # Fallback to default device
                    subprocess.run(['aplay', wav_filename], 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                                 
            except Exception as e:
                print(f"⚠️ ffmpeg/aplay error: {e}")
                # Fallback to mpg123 if ffmpeg fails
                subprocess.run(
                    ['mpg123', '-a', 'bluealsa', mp3_filename], 
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )

    except Exception as e:
        print(f"❌ TTS Error: {e}")
    
    finally:
        if os.path.exists(mp3_filename): os.remove(mp3_filename)
        if os.path.exists(wav_filename): os.remove(wav_filename)

# --- AI LOGIC ---
def ai_memory_observer(user_input, current_memory):
    """AI #2: Observer (Extracts facts)."""
    sys_prompt = """
    Ты - ИИ-Архивариус. Твоя задача - извлекать факты о пользователе.
    Если пользователь сообщает что-то о себе, верни JSON: {"new_fact": "факт"}.
    Иначе верни: {}
    ОТВЕЧАЙ ТОЛЬКО В ФОРМАТЕ JSON.
    """
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {'role': 'system', 'content': sys_prompt},
                {'role': 'user', 'content': user_input}
            ],
            format='json'
        )
        content = response['message']['content']
        if content:
            data = json.loads(content)
            new_fact_text = data.get("new_fact")
            
            if new_fact_text:
                # Check for duplicates (by text)
                existing_texts = [f["text"] for f in current_memory.get("user_facts", [])]
                if new_fact_text not in existing_texts:
                    today = datetime.date.today().isoformat()
                    new_entry = {"text": new_fact_text, "created_at": today}
                    
                    print(f"🧠 [Memory]: Запомнил -> {new_fact_text} ({today})")
                    if "user_facts" not in current_memory:
                        current_memory["user_facts"] = []
                    current_memory["user_facts"].append(new_entry)
                    save_memory(current_memory)
    except Exception as e:
        print(f"⚠️ Memory Error: {e}")

def ai_chat_friend(user_input, memory_data):
    """AI #1: Funny Friend (Chat)."""
    
    # Format facts with dates
    facts_list = "\n".join([f"- [{f['created_at']}] {f['text']}" for f in memory_data.get("user_facts", [])])
    
    current_date = datetime.date.today().strftime("%Y-%m-%d")
    
    sys_prompt = f"""
    Ты - мой лучший кент, ИИ-братан.
    СЕГОДНЯШНЯЯ ДАТА: {current_date}
    
    Стиль: на "ты", с юмором, сленг (в меру), кратко (для озвучки).
    Твои ответы должны быть живыми, не роботскими.
    
    ПАМЯТЬ ОБО МНЕ (с датами создания):
    {facts_list}
    
    Используй память и даты! Если факт старый (например, год назад), можешь спросить "как там с этим?".
    Если факт свежий (сегодня/вчера) - реагируй актуально.
    """
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {'role': 'system', 'content': sys_prompt},
                {'role': 'user', 'content': user_input}
            ]
        )
        return response['message']['content']
    except Exception as e:
        print(f"⚠️ Chat Error: {e}")
        return "Бро, связь лагает..."

# --- MAIN LOOP ---
def list_microphones():
    """Lists all available microphones."""
    print("\n🎤 Available Microphones:")
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        print(f"[{index}] {name}")
    print("-" * 30)

def main():
    print("\n" + "="*50)
    print(f"   🎙️  Local Voice AI Bro (Ollama: {MODEL_NAME} + Memory)")
    print("="*50)

    # List mics so user knows index
    list_microphones()

    # Get Mic Index from env
    mic_index = os.getenv("MIC_INDEX")
    if mic_index:
        mic_index = int(mic_index)
        print(f"🔹 Using Microphone Index: {mic_index}")
    else:
        print("🔹 Using Default Microphone")

    memory = load_memory()
    r = sr.Recognizer()
    
    # Get Mic Device for arecord (e.g., "hw:1,0")
    mic_device = os.getenv("MIC_DEVICE", "hw:1,0")

    # Initial greeting
    speak("Привет, локальный бро! Я на связи.", 'ru')

    if GPIO_AVAILABLE:
        try:
            button = Button(BUTTON_PIN)
            print(f"✅ Button initialized on GPIO {BUTTON_PIN} (Pin 11)")
            USE_POLLING = False
        except Exception as e:
            print(f"⚠️ Button event error: {e}. Switching to POLLING mode.")
            button = None
            USE_POLLING = True
        
        print("👉 HOLD button to speak, RELEASE to process.")
    else:
        print("⚠️ GPIO not available. Falling back to ENTER key.")
        print("👉 Press ENTER to speak, then ENTER again to stop.")

    try:
        while True:
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
                input("\n[ENTER] Начать запись...")

            # --- START RECORDING ---
            print("🎤 Listening...")
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
            print("⏳ Processing...")

            # --- STT ---
            try:
                if os.path.exists(TEMP_WAV):
                    with sr.AudioFile(TEMP_WAV) as source:
                        audio = r.record(source)
                    user_text = r.recognize_google(audio, language="ru-RU")
                    print(f"🗣️  You: {user_text}")

                    if user_text:
                        # 1. Memory AI
                        ai_memory_observer(user_text, memory)
                        
                        # 2. Chat AI
                        ai_response = ai_chat_friend(user_text, memory)
                        print(f"🤖 AI: {ai_response}")
                        
                        # 3. Speak Response
                        speak(ai_response, 'ru')
                else:
                    print("⚠️ No audio recorded.")

            except sr.UnknownValueError:
                print("🤷 Не расслышал...")
            except Exception as e:
                print(f"❌ Error: {e}")
            finally:
                if os.path.exists(TEMP_WAV): os.remove(TEMP_WAV)
                    
    except KeyboardInterrupt:
        print("\n👋 Bye!")
    except OSError as e:
        print(f"❌ Microphone Error: {e}")

if __name__ == "__main__":
    main()
