import os
import json
import sys
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Get absolute path of the script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables from the script directory
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("❌ Error: GEMINI_API_KEY not found in .env")
    sys.exit(1)

# Initialize Client
client = genai.Client(api_key=API_KEY)

MEMORY_FILE = os.path.join(SCRIPT_DIR, "memory.json")

def load_memory():
    """Loads memory from JSON file."""
    if not os.path.exists(MEMORY_FILE):
        return {"user_facts": []}
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"user_facts": []}

def save_memory(memory_data):
    """Saves memory to JSON file."""
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(memory_data, f, ensure_ascii=False, indent=2)

def ai_memory_observer(user_input, current_memory):
    """
    AI #2: The Observer.
    Analyzes user input for new facts and updates memory.
    """
    
    # System prompt for the Memory AI
    sys_prompt = """
    Ты - ИИ-Архивариус. Твоя единственная задача - извлекать факты о пользователе из его сообщений.
    
    ТВОЯ ЦЕЛЬ:
    Если пользователь сообщает что-то о себе (вкусы, имя, питомцы, планы, работа, хобби), верни ЭТОТ ФАКТ в формате JSON.
    Если в сообщении нет фактов о пользователе (просто "привет", "как дела", вопрос к ИИ), верни пустой JSON: {}
    
    ФОРМАТ ОТВЕТА (JSON):
    {
      "new_fact": "строка с фактом"
    }
    
    ПРИМЕРЫ:
    User: "Меня зовут Костя" -> {"new_fact": "Зовут Костя"}
    User: "Я люблю пиццу с ананасами" -> {"new_fact": "Любит пиццу с ананасами"}
    User: "Какая погода?" -> {}
    User: "Завтра поеду на дачу" -> {"new_fact": "Завтра едет на дачу"}
    
    Не выдумывай ничего. Только то, что сказал пользователь.
    """

    # Retry logic for 503 errors
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash", # Using a fast model
                config=types.GenerateContentConfig(
                    system_instruction=sys_prompt,
                    response_mime_type="application/json"
                ),
                contents=user_input
            )
            
            if response.text:
                data = json.loads(response.text)
                new_fact = data.get("new_fact")
                
                if new_fact:
                    # Check for duplicates (simple check)
                    if new_fact not in current_memory["user_facts"]:
                        print(f"🧠 [Memory AI]: Запомнил -> {new_fact}")
                        current_memory["user_facts"].append(new_fact)
                        save_memory(current_memory)
                        return True
            return False # Success but no new fact
            
        except Exception as e:
            if "503" in str(e) or "overloaded" in str(e).lower():
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
            print(f"⚠️ Memory AI Error: {e}")
            return False

def ai_chat_friend(user_input, memory_data):
    """
    AI #1: The Funny Friend.
    Chats with the user using the stored memory context.
    """
    
    facts_list = "\n".join([f"- {fact}" for fact in memory_data["user_facts"]])
    
    sys_prompt = f"""
    Ты - мой лучший кент, ИИ-братан. 
    Твой стиль:
    - Общаешься на "ты", легко, с юмором, используешь сленг (но в меру).
    - Ты веселый, позитивный, всегда поддержишь любой кипиш.
    - Твои ответы не должны быть слишком длинными (как в чате).
    - Ты НИКОГДА не говоришь как робот ("Я языковая модель"). Ты - живой собеседник.
    
    ВОТ ЧТО ТЫ ЗНАЕШЬ ОБО МНЕ (ПАМЯТЬ):
    {facts_list}
    
    Используй эти факты в разговоре, чтобы показать, что ты помнишь меня. Если я спрашиваю "что я люблю?", отвечай на основе памяти.
    """

    # Retry logic for 503 errors
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                config=types.GenerateContentConfig(
                    system_instruction=sys_prompt
                ),
                contents=user_input
            )
            return response.text
        except Exception as e:
            if "503" in str(e) or "overloaded" in str(e).lower():
                if attempt < max_retries - 1:
                    print(f"⚠️ Model overloaded (503). Retrying in 2s... ({attempt+1}/{max_retries})")
                    time.sleep(2)
                    continue
            return f"Бро, что-то меня глючит... ({e})"

def main():
    print("\n" + "="*50)
    print("   🤖 AI Bro with Memory (Gemini 2.0)")
    print("="*50)
    
    memory = load_memory()
    print(f"📂 Память загружена. Фактов обо мне: {len(memory['user_facts'])}")
    print("🔹 Пиши 'exit', чтобы выйти.\n")

    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['exit', 'quit', 'выход']:
            print("AI: Давай, бро, на связи! 🤙")
            break
        
        if not user_input:
            continue

        # 1. Run Memory AI (Observer) first to catch new facts immediately
        # (Optional: run in background thread for speed, but sequential is safer for now)
        ai_memory_observer(user_input, memory)
        
        # Reload memory in case it changed (though we passed the dict ref, so it's updated)
        
        # 2. Run Chat AI
        response = ai_chat_friend(user_input, memory)
        print(f"AI: {response}")
        print("-" * 30)

if __name__ == "__main__":
    main()
