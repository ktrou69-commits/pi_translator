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
from app.backends.groq import GroqBackend
from app.core.memory import MemoryManager
from app.core.executor import executor, TOOL_DEFINITIONS
import asyncio

# --- ARGPARSE ---
parser = argparse.ArgumentParser(description="AI Assistant Server")
parser.add_argument("--profile", type=str, choices=["local", "gemini", "groq"], default="local", help="LLM Profile to use")
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
elif args.profile == "groq":
    GROQ_KEY = os.getenv("GROQ_API_KEY")
    if not GROQ_KEY:
        print("❌ Error: GROQ_API_KEY not found in environment!")
        exit(1)
    backend = GroqBackend(api_key=GROQ_KEY)
    print("⚡ Using Profile: GROQ")
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
        model="small",
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
    
    response_items = []
    for item in backend.chat_stream(request.user_text, memory, tools=TOOL_DEFINITIONS):
        if isinstance(item, str):
            response_items.append(item)
        else:
            # Execute tool
            func_name = item.name
            func_args = item.args
            if func_name == "open_url":
                executor.open_url(**func_args)
            elif func_name == "open_path":
                executor.open_path(**func_args)
            elif func_name == "run_app":
                executor.run_app(**func_args)
            response_items.append(f"[🛠️ {func_name}]")
            
    return {"response": " ".join(response_items)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🚀 WebSocket connection established")
    
    stt = websocket.app.state.stt_recorder
    tts = websocket.app.state.tts_stream

    audio_chunks_received = 0
    current_processing_task: asyncio.Task = None

    async def process_voice_command(text: str):
        """Async task to process voice command and generate response"""
        try:
            if text.strip():
                print(f"🗣️  User: {text}")
                await websocket.send_json({"user_transcription": text})
                
                memory = memory_manager.load_memory()
                
                print(f"🤖 AI ({args.profile}) is generating response...")
                for response_item in backend.chat_stream(text, memory, tools=TOOL_DEFINITIONS):
                    # Check for cancellation
                    await asyncio.sleep(0) 
                    
                    if isinstance(response_item, str):
                        # This is text for TTS
                        print(f"⏩ Sending sentence: {response_item}")
                        await websocket.send_json({"assistant_text": response_item})
                        
                        chunk_count = 0
                        async for chunk in tts.engine.async_generate(response_item):
                            await websocket.send_bytes(chunk)
                            chunk_count += 1
                        print(f"🔊 Sent {chunk_count} audio chunks for sentence.")
                    else:
                        # This is a FunctionCall object from the LLM
                        func_name = response_item.name
                        func_args = response_item.args
                        print(f"🛠️  Model requested tool: {func_name}({func_args})")
                        
                        # Execute action
                        if func_name == "open_url":
                            executor.open_url(**func_args)
                        elif func_name == "open_path":
                            executor.open_path(**func_args)
                        elif func_name == "run_app":
                            executor.run_app(**func_args)
                        
                        # We can send a notification to the client that a tool was used
                        await websocket.send_json({"assistant_text": f"[🛠️ {func_name}]"})
                
                await websocket.send_json({"end": True})
                print("✅ Response sent completely.")
                # Run memory observer in background (non-blocking)
                background_tasks = BackgroundTasks()
                background_tasks.add_task(backend.memory_observer, text, memory, memory_manager.save_memory)
                await backend.memory_observer(text, memory, memory_manager.save_memory)
                
        except asyncio.CancelledError:
            print("🛑 Processing task CANCELLED by new request")
            raise
        except Exception as e:
             print(f"❌ Error in processing task: {e}")

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
                    # Cancel previous task if valid
                    if current_processing_task and not current_processing_task.done():
                        print("⚡ Cancelling previous processing task!")
                        current_processing_task.cancel()
                        # Optional: Wait for it to clear? Usually not needed if we fire-and-forget
                        
                    # Stop any current TTS playback (best effort)
                    if hasattr(tts.engine, "stop"):
                        tts.engine.stop()

                    audio_chunks_received = 0
                    stt.start()
                
                elif request_data.get("end"):
                    print(f"🛑 Recording ended. Received {audio_chunks_received} chunks. Processing...")
                    stt.stop()
                    user_text = stt.text()
                    
                    # Start new processing task
                    current_processing_task = asyncio.create_task(process_voice_command(user_text))
                    
    except WebSocketDisconnect:
        print("👋 WebSocket connection closed")
        import traceback
        traceback.print_exc()

@app.get("/status")
async def status():
    return {"status": "ok", "profile": args.profile}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
