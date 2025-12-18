import os
import sys
import json
import time
import subprocess
import speech_recognition as sr
from dotenv import load_dotenv
from google import genai
from google.genai import types
from gtts import gTTS

# Get absolute path of the script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables from the script directory
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("❌ Error: GEMINI_API_KEY not found in .env")
    sys.exit(1)

# Initialize Gemini Client
client = genai.Client(api_key=API_KEY)

MEMORY_FILE = os.path.join(SCRIPT_DIR, "memory.json")
ALSA_DEVICE = "bluealsa" # For Pi Lite Bluetooth

import datetime

# ... (imports remain)

# --- MEMORY FUNCTIONS ---
def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {"user_facts": []}
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Migration check: if facts are strings, convert to objects
            if data["user_facts"] and isinstance(data["user_facts"][0], str):
                today = datetime.date.today().isoformat()
                data["user_facts"] = [{"text": f, "created_at": today} for f in data["user_facts"]]
                save_memory(data)
            return data
    except json.JSONDecodeError:
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
        # 1. Generate MP3
        tts = gTTS(text=text, lang=lang)
        tts.save(mp3_filename)
        
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
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=sys_prompt,
                response_mime_type="application/json"
            ),
            contents=user_input
        )
        if response.text:
            data = json.loads(response.text)
            new_fact_text = data.get("new_fact")
            
            if new_fact_text:
                # Check for duplicates (by text)
                existing_texts = [f["text"] for f in current_memory["user_facts"]]
                if new_fact_text not in existing_texts:
                    today = datetime.date.today().isoformat()
                    new_entry = {"text": new_fact_text, "created_at": today}
                    
                    print(f"🧠 [Memory]: Запомнил -> {new_fact_text} ({today})")
                    current_memory["user_facts"].append(new_entry)
                    save_memory(current_memory)
    except Exception as e:
        print(f"⚠️ Memory Error: {e}")

def ai_chat_friend(user_input, memory_data):
    """AI #1: Funny Friend (Chat)."""
    
    # Format facts with dates
    facts_list = "\n".join([f"- [{f['created_at']}] {f['text']}" for f in memory_data["user_facts"]])
    
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
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(system_instruction=sys_prompt),
            contents=user_input
        )
        return response.text
    except Exception as e:
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
    print("   🎙️  Voice AI Bro (Gemini 2.5 + Memory)")
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
    r.dynamic_energy_threshold = True

    # Initial greeting
    speak("Привет, бро! Я на связи.", 'ru')

    try:
        # Use specific mic if set, else default
        with sr.Microphone(device_index=mic_index) as source:
            print("🎤 Calibrating noise...")
            r.adjust_for_ambient_noise(source, duration=2)
            print("✅ Ready! Speak.")
            
            while True:
                try:
                    print("\n👂 Listening...")
                    audio = r.listen(source, timeout=None)
                    
                    print("⏳ Recognizing...")
                    user_text = r.recognize_google(audio, language="ru-RU")
                    print(f"🗣️  You: {user_text}")

                    if not user_text: continue

                    # 1. Memory AI
                    ai_memory_observer(user_text, memory)
                    
                    # 2. Chat AI
                    ai_response = ai_chat_friend(user_text, memory)
                    print(f"🤖 AI: {ai_response}")
                    
                    # 3. Speak Response
                    speak(ai_response, 'ru')

                except sr.UnknownValueError:
                    print("🤷 Не расслышал...")
                except sr.RequestError:
                    print("⚠️ Ошибка сети (STT)")
                except Exception as e:
                    print(f"❌ Error: {e}")
                    
    except KeyboardInterrupt:
        print("\n👋 Bye!")
    except OSError as e:
        print(f"❌ Microphone Error: {e}")
        print("💡 Try setting MIC_INDEX in .env to one of the numbers listed above.")

if __name__ == "__main__":
    main()
