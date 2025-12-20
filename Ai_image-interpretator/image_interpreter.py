import os
import sys
import json
import time
import datetime
import subprocess
import cv2
import speech_recognition as sr
from dotenv import load_dotenv
from google import genai
from google.genai import types
from gtts import gTTS
from PIL import Image

try:
    from gpiozero import Button
    GPIO_AVAILABLE = True
except (ImportError, OSError):
    GPIO_AVAILABLE = False

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

# Shared Memory Path (Absolute)
MEMORY_FILE = os.path.join(SCRIPT_DIR, "../Ai_assistant-memory-voice/memory.json")
ALSA_DEVICE = "bluealsa" # For Pi Lite Bluetooth
TTS_SPEED = 1.25
BUTTON_PIN = 22          # GPIO 22 (Pin 15)
TEMP_WAV = os.path.join(SCRIPT_DIR, "input.wav")

# --- MEMORY FUNCTIONS ---
def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {"user_facts": []}
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"user_facts": []}

def save_memory(memory_data):
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(memory_data, f, ensure_ascii=False, indent=2)

# --- AUDIO FUNCTIONS ---
def speak(text, lang='ru'):
    """TTS with cross-platform support and SPEED CONTROL."""
    mp3_filename = os.path.join(SCRIPT_DIR, "output_tts.mp3")
    wav_filename = os.path.join(SCRIPT_DIR, "output_tts.wav")

    try:
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
                # Try explicit bluealsa device first, then default
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

# --- CAMERA FUNCTIONS ---
def take_photo(filename="capture.jpg", camera_index=0):
    """Captures a single frame from the webcam."""
    print(f"📸 Opening camera [{camera_index}]...")
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"❌ Error: Could not open camera {camera_index}.")
        return False
    
    # Warmup
    time.sleep(0.5)
    
    ret, frame = cap.read()
    cap.release()
    
    if ret:
        cv2.imwrite(filename, frame)
        print(f"✅ Photo saved: {filename}")
        return True
    else:
        print("❌ Error: Could not read frame.")
        return False

# --- AI LOGIC ---
def analyze_image_and_voice(image_path, user_voice_text, current_memory):
    """Gemini 2.5 Flash Multimodal Analysis."""
    
    # Prepare Memory Context
    facts_list = "\n".join([f"- [{f['created_at']}] {f['text']}" for f in current_memory["user_facts"]])
    current_date = datetime.date.today().strftime("%Y-%m-%d")

    sys_prompt = f"""
    Ты - ИИ-Кент с глазами. 
    СЕГОДНЯ: {current_date}
    
    ТВОЯ ЗАДАЧА:
    1. Посмотреть на фото.
    2. Послушать вопрос пользователя: "{user_voice_text}"
    3. Ответить максимально лаконично и по делу. Только суть.
    4. ИЗВЛЕЧЬ ФАКТЫ из увиденного, если это важно.
    
    ФОРМАТ ОТВЕТА (JSON):
    {{
        "response": "Текст ответа для озвучки",
        "new_fact": "Текст нового факта (или null, если ничего нового)"
    }}
    
    ПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ:
    {facts_list}
    """

    try:
        # Load Image
        image = Image.open(image_path)
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=sys_prompt,
                response_mime_type="application/json"
            ),
            contents=[user_voice_text, image]
        )
        
        if response.text:
            data = json.loads(response.text)
            ai_resp = data.get("response", "Не понял, бро.")
            new_fact = data.get("new_fact")
            
            # Save Fact if present
            if new_fact:
                existing_texts = [f["text"] for f in current_memory["user_facts"]]
                if new_fact not in existing_texts:
                    today = datetime.date.today().isoformat()
                    print(f"🧠 [Memory]: Запомнил -> {new_fact}")
                    current_memory["user_facts"].append({"text": new_fact, "created_at": today})
                    save_memory(current_memory)
            
            return ai_resp
            
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return "Бро, я ослеп... Что-то с сервером."

# --- MAIN LOOP ---
def main():
    print("\n" + "="*50)
    print("   👁️  Vision AI Bro (Gemini 2.5 + Memory)")
    print("="*50)

    # Create photos directory (Absolute)
    PHOTOS_DIR = os.path.join(SCRIPT_DIR, "photos")
    if not os.path.exists(PHOTOS_DIR):
        os.makedirs(PHOTOS_DIR)
        print(f"📂 Created directory: {PHOTOS_DIR}")

    mic_index = os.getenv("MIC_INDEX")
    if mic_index: 
        mic_index = int(mic_index)
        print(f"🎤 Using Mic Index: {mic_index}")

    camera_index = os.getenv("CAMERA_INDEX")
    if camera_index:
        camera_index = int(camera_index)
        print(f"📷 Using Camera Index: {camera_index}")
    else:
        # Default to 0, but user can change this default here if needed
        camera_index = 2 
        print(f"📷 Using Default Camera ({camera_index})")

    memory = load_memory()
    r = sr.Recognizer()
    
    # Get Mic Device for arecord (e.g., "hw:1,0")
    mic_device = os.getenv("MIC_DEVICE", "hw:1,0")

    speak("Я готов. Нажми кнопку, чтобы сделать фото.", 'ru')

    if GPIO_AVAILABLE:
        try:
            button = Button(BUTTON_PIN)
            print(f"✅ Button 3 initialized on GPIO {BUTTON_PIN} (Pin 15)")
            USE_POLLING = False
        except Exception as e:
            print(f"⚠️ Button error: {e}. Switching to POLLING mode.")
            button = None
            USE_POLLING = True
        print("👉 CLICK to photo, HOLD to record voice.")
    else:
        print("⚠️ GPIO not available. Use ENTER to photo, then ENTER to record.")
        USE_POLLING = False

    while True:
        try:
            # Generate timestamped filename
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            photo_filename = os.path.join(PHOTOS_DIR, f"photo_{timestamp}.jpg")

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
                input("\n📸 Press ENTER to snap photo...")

            # STEP 1: SNAP PHOTO
            if not take_photo(photo_filename, camera_index):
                speak("Не могу сделать фото, проверь камеру.", 'ru')
                continue
            
            # STEP 2: WAIT FOR HOLD OR NEXT CLICK
            print("🎤 Waiting for HOLD to record voice (or CLICK for new photo)...")
            
            # We need to detect if the user HOLDS the button now
            # If they release quickly, it was just a photo.
            # If they keep holding, we start recording.
            
            is_holding = False
            start_time = time.time()
            
            if GPIO_AVAILABLE:
                # Wait a bit to see if it's a hold
                time.sleep(0.3) 
                if not USE_POLLING:
                    if button.is_pressed: is_holding = True
                else:
                    if GPIO.input(BUTTON_PIN) == GPIO.LOW: is_holding = True
            else:
                # On PC, we just ask
                ans = input("🎤 Hold to record? (y/n): ").lower()
                if ans == 'y': is_holding = True

            user_text = "Что ты видишь на фото?" # Default

            if is_holding:
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
                        while GPIO.input(BUTTON_PIN) == GPIO.LOW:
                            time.sleep(0.05)
                else:
                    input("🎤 ЗАПИСЬ... [ENTER] Остановить")

                # --- STOP RECORDING ---
                if process:
                    process.terminate()
                    process.wait()
                
                # --- STT ---
                try:
                    if os.path.exists(TEMP_WAV):
                        with sr.AudioFile(TEMP_WAV) as source:
                            audio = r.record(source)
                        user_text = r.recognize_google(audio, language="ru-RU")
                        print(f"🗣️  You: {user_text}")
                except Exception as e:
                    print(f"⚠️ STT Error: {e}")
                finally:
                    if os.path.exists(TEMP_WAV): os.remove(TEMP_WAV)

            # 4. Analyze
            print("🤔 Thinking...")
            response_text = analyze_image_and_voice(photo_filename, user_text, memory)
            
            # 5. Respond
            print(f"🤖 AI: {response_text}")
            speak(response_text, 'ru')

        except KeyboardInterrupt:
            print("\n👋 Bye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
