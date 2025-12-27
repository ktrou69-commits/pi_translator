import os
import json
import threading
import time
import pyaudio
import websocket
from pynput import keyboard
from dotenv import load_dotenv

# Load environment
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(SCRIPT_DIR, ".env.local")
if not os.path.exists(ENV_FILE):
    ENV_FILE = os.path.join(SCRIPT_DIR, ".env")
load_dotenv(ENV_FILE)

SERVER_IP = os.getenv("SERVER_IP", "localhost")
WS_URL = f"ws://{SERVER_IP}:8000/ws"

# Audio config
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024

# Playback config (Server sends 24kHz)
PLAYBACK_RATE = 24000

class StreamingVoiceClient:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.ws = None
        self.connected = False
        self.is_recording = False
        self.is_playing = False
        self.running = True

        # Input stream (mic)
        self.input_stream = self.p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
            start=False
        )

        # Output stream (speakers)
        self.output_stream = self.p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=PLAYBACK_RATE,
            output=True,
            frames_per_buffer=CHUNK
        )

        # Start WebSocket
        self.ws_thread = threading.Thread(target=self.init_ws)
        self.ws_thread.daemon = True
        self.ws_thread.start()

        # Keyboard listener
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()

    def init_ws(self):
        def on_message(ws, message):
            if isinstance(message, bytes):
                # Receive audio chunk and play
                self.output_stream.write(message)
                self.is_playing = True
            else:
                data = json.loads(message)
                if data.get("user_transcription"):
                    print(f"\r\x1b[K🗣️  Юзер: {data['user_transcription']}")
                if data.get("assistant_text"):
                    print(f"\r\x1b[K🤖 AI: {data['assistant_text']}")
                if data.get("start"):
                    print(f"\r\x1b[K🤖 Ассистент отвечает...", end="", flush=True)
                    self.is_playing = True
                if data.get("end"):
                    self.is_playing = False
                    print(f"\n✅ Готово! Нажми ПРОБЕЛ, чтобы сказать что-то.")

        def on_error(ws, error):
            print(f"\n❌ Ошибка соединения: {error}")
            self.connected = False

        def on_close(ws, close_status_code, close_msg):
            print("\n👋 Соединение закрыто. Переподключение...")
            self.connected = False
            time.sleep(2)
            if self.running:
                self.init_ws()

        def on_open(ws):
            print("\n🚀 Подключено к серверу!")
            self.connected = True

        self.ws = websocket.WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        self.ws.run_forever()

    def on_press(self, key):
        if key == keyboard.Key.space and not self.is_recording:
            self.start_recording()

    def on_release(self, key):
        if key == keyboard.Key.space and self.is_recording:
            self.stop_recording()

    def start_recording(self):
        print(f"\r\x1b[K🎤 Запись... (отпусти ПРОБЕЛ)", end="", flush=True)
        self.is_recording = True
        if self.connected:
            self.ws.send(json.dumps({"start": True}))
        
        self.input_stream.start_stream()
        threading.Thread(target=self.recording_loop).start()

    def stop_recording(self):
        self.is_recording = False
        print(f"\r\x1b[K🛑 Обработка...", end="", flush=True)
        if self.connected:
            self.ws.send(json.dumps({"end": True}))
        self.input_stream.stop_stream()

    def recording_loop(self):
        while self.is_recording:
            try:
                data = self.input_stream.read(CHUNK, exception_on_overflow=False)
                if self.connected:
                    self.ws.send(data, opcode=websocket.ABNF.OPCODE_BINARY)
            except Exception as e:
                print(f"Error in recording loop: {e}")
                break

    def run(self):
        print("\n" + "="*50)
        print("   🤖  01-Style Voice Assistant (STREAMING)")
        print("="*50)
        print("Ожидание подключения...")
        while not self.connected:
            time.sleep(0.1)

        print("✅ Готово! ЗАЖМИ [ПРОБЕЛ] и говори.")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            print("\n👋 Выход...")
            self.input_stream.close()
            self.output_stream.close()
            self.p.terminate()

if __name__ == "__main__":
    client = StreamingVoiceClient()
    client.run()
