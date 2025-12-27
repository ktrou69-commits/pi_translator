from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import os
import json
import datetime
import ollama
from dotenv import load_dotenv
from stream2sentence import generate_sentences
from RealtimeSTT import AudioToTextRecorder
from RealtimeTTS import TextToAudioStream
from edge_engine import EdgeEngine
import asyncio
import queue

# Load environment
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(SCRIPT_DIR, ".env.local")
if not os.path.exists(ENV_FILE):
    ENV_FILE = os.path.join(SCRIPT_DIR, ".env")
load_dotenv(ENV_FILE)

MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")
MEMORY_FILE = os.path.join(SCRIPT_DIR, "memory.json")

from contextlib import asynccontextmanager

# --- AI COMPONENTS SETUP ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialization
    print("🎙️ Initializing Realtime STT (Whisper) on Server...")
    app.state.stt_recorder = AudioToTextRecorder(
        model="base",
        language="ru",
        spinner=False,
        use_microphone=False
    )
    app.state.stt_recorder.stop()

    print("🔊 Initializing Realtime TTS (EdgeTTS) on Server...")
    app.state.tts_engine = EdgeEngine(voice="ru-RU-SvetlanaNeural")
    app.state.tts_stream = TextToAudioStream(app.state.tts_engine)
    
    yield
    
    # Shutdown
    print("🛑 Shutting down AI components...")
    app.state.stt_recorder.stop()

app = FastAPI(title="AI Assistant Server", lifespan=lifespan)

class ChatRequest(BaseModel):
    user_text: str

# --- MEMORY FUNCTIONS ---
def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {"user_facts": []}
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except (json.JSONDecodeError, KeyError):
        return {"user_facts": []}

def save_memory(memory_data):
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(memory_data, f, ensure_ascii=False, indent=2)

def ai_memory_observer(user_input, current_memory):
    """AI #1: Observer - Extracts facts about the user."""
    sys_prompt = """
    Ты - аналитик персональных данных. Твоя задача: находить КОНКРЕТНЫЕ факты о ПОЛЬЗОВАТЕЛЕ.
    
    ЧТО СЧИТАТЬ ФАКТОМ (ЗАПОМИНАТЬ):
    1. Личные планы и события: "в понедельник пати у друга", "тест в четверг", "еду в отпуск в июле".
    2. Желания и подарки: "хочу на др новые наушники", "люблю пиццу с ананасами".
    3. Имена, даты, предпочтения: "у сестры Кати день рождения 5 мая", "ненавижу холодную погоду".
    
    ЧТО НЕ ЗАПОМИНАТЬ:
    1. Твои собственные способности: "Я могу помочь", "Я ИИ-ассистент".
    2. Общие фразы: "Привет", "Как дела", "Спасибо".
    3. Факты обо всем мире, не связанные лично с пользователем.
    
    ОЧЕНЬ ВАЖНО: 
    Пиши факт кратко, в 3-м лице ("Пользователь хочет...", "У пользователя тест...").
    Если в тексте нет нового личного факта о пользователе - верни {"new_fact": null}.
    
    ПРАВИЛА:
    1. Верни JSON: {"new_fact": "текст факта в 3-м лице или null"}
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
            clean_content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_content)
            new_fact_text = data.get("new_fact")
            if new_fact_text:
                existing_texts = [f["text"] for f in current_memory.get("user_facts", [])]
                if new_fact_text not in existing_texts:
                    today = datetime.date.today().isoformat()
                    new_entry = {"text": new_fact_text, "created_at": today}
                    print(f"🧠 [Memory]: Запомнил -> {new_fact_text}")
                    if "user_facts" not in current_memory:
                        current_memory["user_facts"] = []
                    current_memory["user_facts"].append(new_entry)
                    save_memory(current_memory)
    except Exception as e:
        print(f"⚠️ Memory Error: {e}")

def ai_chat_stream(user_input, memory_data):
    """AI #2: Responder - Streams sentences."""
    facts_list = "\n".join([f"- [{f['created_at']}] {f['text']}" for f in memory_data.get("user_facts", [])])
    current_date = datetime.date.today().strftime("%Y-%m-%d")
    
    sys_prompt = f"""
    Ты - всезнающий персональный ассистент. Твои ответы должны основываться на ПАМЯТИ О ПОЛЬЗОВАТЕЛЕ.
    СЕГОДНЯШНЯЯ ДАТА: {current_date}
    
    ПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ (это абсолютная истина):
    {facts_list}
    
    ИНСТРУКЦИИ:
    1. Если в памяти есть ответ на вопрос пользователя (например, про планы) - отвечай прямо: "У тебя в понедельник тест". 
    2. НИКОГДА не говори "Я не знаю", если информация есть в ПАМЯТИ.
    3. Стиль: Краткий, четкий, без вступлений. Максимум 15-20 слов.
    """
    
    def generate():
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {'role': 'system', 'content': sys_prompt},
                {'role': 'user', 'content': user_input}
            ],
            stream=True
        )
        for chunk in response:
            yield chunk['message']['content']

    # Use stream2sentence to yield full sentences from the character stream
    for sentence in generate_sentences(generate()):
        yield sentence

@app.post("/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    memory = load_memory()
    background_tasks.add_task(ai_memory_observer, request.user_text, memory)
    # Fallback for old HTTP clients: collect all sentences
    full_response = " ".join(list(ai_chat_stream(request.user_text, memory)))
    return {"response": full_response}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🚀 WebSocket connection established")
    
    stt = websocket.app.state.stt_recorder
    tts = websocket.app.state.tts_stream

    output_queue = queue.Queue()
    audio_chunks_received = 0

    def on_tts_chunk(chunk):
        output_queue.put(chunk)

    try:
        while True:
            # Wait for message (can be text/json or bytes)
            message = await websocket.receive()
            
            if "bytes" in message:
                # 1. Received audio chunk from client
                stt.feed_audio(message["bytes"])
                audio_chunks_received += 1
            
            elif "text" in message:
                request_data = json.loads(message["text"])
                
                if request_data.get("start"):
                    print("🎤 Recording started...")
                    audio_chunks_received = 0
                    stt.start()
                
                elif request_data.get("end"):
                    print(f"🛑 Recording ended. Received {audio_chunks_received} chunks. Processing...")
                    stt.stop()
                    user_text = stt.text()
                    print(f"🔍 STT Result: '{user_text}'")
                    
                    if user_text.strip():
                        print(f"🗣️  User: {user_text}")
                        await websocket.send_json({"user_transcription": user_text})
                        
                        memory = load_memory()
                        
                        # Start TTS stream
                        await websocket.send_json({"role": "assistant", "type": "audio", "start": True})
                        
                        print("🤖 AI is generating response...")
                        # Process sentences and send chunks directly
                        for sentence in ai_chat_stream(user_text, memory):
                            print(f"⏩ Sending sentence: {sentence}")
                            # Send text to client for display
                            await websocket.send_json({"assistant_text": sentence})
                            
                            chunk_count = 0
                            async for chunk in tts.engine.async_generate(sentence):
                                await websocket.send_bytes(chunk)
                                chunk_count += 1
                            print(f"🔊 Sent {chunk_count} audio chunks for sentence.")
                        
                        await websocket.send_json({"end": True})
                        print("✅ Response sent completely.")
                        # Memory update
                        ai_memory_observer(user_text, memory)
                
    except WebSocketDisconnect:
        print("👋 WebSocket connection closed")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        import traceback
        traceback.print_exc()

@app.get("/status")
async def status():
    return {"status": "ok", "model": MODEL_NAME}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
