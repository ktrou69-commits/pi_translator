from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import os
import json
import datetime
import argparse
from dotenv import load_dotenv
from app.engines.tts_edge import EdgeEngine
from app.backends.ollama import OllamaBackend
from app.backends.gemini import GeminiBackend
from app.core.memory import MemoryManager
import asyncio

# --- ARGPARSE ---
parser = argparse.ArgumentParser(description="AI Assistant Server")
parser.add_argument("--profile", type=str, choices=["local", "gemini"], default="local", help="LLM Profile to use")
args, unknown = parser.parse_known_args()

# Load environment
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(SCRIPT_DIR, ".env.local")
if not os.path.exists(ENV_FILE):
    ENV_FILE = os.path.join(SCRIPT_DIR, ".env")
load_dotenv(ENV_FILE)

MEMORY_FILE = os.path.join(SCRIPT_DIR, "memory.json")
memory_manager = MemoryManager(MEMORY_FILE)

# --- BACKEND SELECTION ---
if args.profile == "gemini":
    GEMINI_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_KEY:
        print("❌ Error: GEMINI_API_KEY not found in environment!")
        exit(1)
    backend = GeminiBackend(api_key=GEMINI_KEY)
    print("✨ Using Profile: GEMINI")
else:
    MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")
    backend = OllamaBackend(model_name=MODEL_NAME)
    print(f"🏠 Using Profile: LOCAL (Ollama: {MODEL_NAME})")

from contextlib import asynccontextmanager

# --- AI COMPONENTS SETUP ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    from RealtimeSTT import AudioToTextRecorder
    from RealtimeTTS import TextToAudioStream
    
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

@app.post("/chat")
async def chat(request: ChatRequest, background_tasks: BackgroundTasks):
    memory = memory_manager.load_memory()
    background_tasks.add_task(backend.memory_observer, request.user_text, memory, memory_manager.save_memory)
    full_response = " ".join(list(backend.chat_stream(request.user_text, memory)))
    return {"response": full_response}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🚀 WebSocket connection established")
    
    stt = websocket.app.state.stt_recorder
    tts = websocket.app.state.tts_stream

    audio_chunks_received = 0

    try:
        while True:
            message = await websocket.receive()
            
            if "bytes" in message:
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
                    
                    if user_text.strip():
                        print(f"🗣️  User: {user_text}")
                        await websocket.send_json({"user_transcription": user_text})
                        
                        memory = memory_manager.load_memory()
                        await websocket.send_json({"role": "assistant", "type": "audio", "start": True})
                        
                        print(f"🤖 AI ({args.profile}) is generating response...")
                        for sentence in backend.chat_stream(user_text, memory):
                            print(f"⏩ Sending sentence: {sentence}")
                            await websocket.send_json({"assistant_text": sentence})
                            
                            chunk_count = 0
                            async for chunk in tts.engine.async_generate(sentence):
                                await websocket.send_bytes(chunk)
                                chunk_count += 1
                            print(f"🔊 Sent {chunk_count} audio chunks for sentence.")
                        
                        await websocket.send_json({"end": True})
                        print("✅ Response sent completely.")
                        backend.memory_observer(user_text, memory, memory_manager.save_memory)
                
    except WebSocketDisconnect:
        print("👋 WebSocket connection closed")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        import traceback
        traceback.print_exc()

@app.get("/status")
async def status():
    return {"status": "ok", "profile": args.profile}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
