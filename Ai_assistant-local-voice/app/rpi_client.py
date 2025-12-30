"""
Raspberry Pi Voice Client
Main client module for Raspberry Pi Zero 2W
Connects to Mac server via WebSocket and handles voice interaction
"""
import websocket
import threading
import time
from typing import Optional
from app.rpi_audio import RPiMicrophone, RPiSpeaker, AudioConfig
from app import rpi_config


class RPiVoiceClient:
    """
    Main voice client for Raspberry Pi
    Manages WebSocket connection, audio streaming, and response handling
    """
    
    def __init__(self):
        # Audio configuration
        self.audio_config = AudioConfig(
            mic_device=rpi_config.MIC_DEVICE,
            speaker_device=rpi_config.SPEAKER_DEVICE,
            sample_rate=rpi_config.SAMPLE_RATE,
            chunk_size=rpi_config.CHUNK_SIZE
        )
        
        # Audio components
        self.microphone = RPiMicrophone(self.audio_config)
        self.speaker = RPiSpeaker(self.audio_config)
        
        # WebSocket connection
        self.ws: Optional[websocket.WebSocket] = None
        self.connected = False
        self.running = True
        
        # State management
        self.is_recording = False
        self.recording_thread: Optional[threading.Thread] = None
        
        print(f"🤖 RPi Voice Client initialized")
        print(f"   Server: {rpi_config.WS_URL}")
        print(f"   Mic: {rpi_config.MIC_DEVICE}")
        print(f"   Speaker: {rpi_config.SPEAKER_DEVICE}")
    
    def connect(self):
        """
        Connect to WebSocket server with auto-reconnect
        """
        retry_delay = rpi_config.RECONNECT_DELAY_INITIAL
        
        while self.running:
            try:
                print(f"\n🔌 Connecting to {rpi_config.WS_URL}...")
                
                # Create WebSocket connection
                self.ws = websocket.WebSocket()
                self.ws.connect(rpi_config.WS_URL)
                self.connected = True
                
                print("✅ Connected to server!")
                
                # Start speaker worker
                self.speaker.start()
                
                # Start listening for responses
                response_thread = threading.Thread(target=self._response_loop, daemon=True)
                response_thread.start()
                
                # Reset retry delay on successful connection
                retry_delay = rpi_config.RECONNECT_DELAY_INITIAL
                
                # Keep connection alive
                while self.connected and self.running:
                    time.sleep(0.1)
                
            except Exception as e:
                print(f"❌ Connection error: {e}")
                self.connected = False
                
                if self.running:
                    print(f"🔄 Reconnecting in {retry_delay}s...")
                    time.sleep(retry_delay)
                    
                    # Exponential backoff
                    retry_delay = min(
                        retry_delay * rpi_config.RECONNECT_BACKOFF_MULTIPLIER,
                        rpi_config.RECONNECT_DELAY_MAX
                    )
    
    def _response_loop(self):
        """
        Background thread that receives audio responses from server
        """
        try:
            while self.connected and self.running:
                # Receive audio chunk from server
                opcode, data = self.ws.recv_data()
                
                if opcode == websocket.ABNF.OPCODE_BINARY:
                    # Audio data from TTS
                    if data:
                        self.speaker.play(data)
                
                elif opcode == websocket.ABNF.OPCODE_TEXT:
                    # Text message (for debugging/status)
                    message = data.decode('utf-8')
                    if message.startswith("🗣️"):
                        print(message)  # User transcription
                    elif message.startswith("🤖"):
                        print(message)  # AI response text
                
        except websocket.WebSocketConnectionClosedException:
            print("🔌 Server disconnected")
            self.connected = False
        except Exception as e:
            print(f"❌ Response loop error: {e}")
            self.connected = False
    
    def start_recording(self):
        """
        Start recording and streaming to server
        """
        if self.is_recording:
            print("⚠️ Already recording")
            return
        
        if not self.connected:
            print("⚠️ Not connected to server")
            return
        
        self.is_recording = True
        self.recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
        self.recording_thread.start()
        print("🎤 Recording started... (release button to send)")
    
    def _recording_loop(self):
        """
        Background thread that streams microphone audio to server
        """
        try:
            for chunk in self.microphone.start_recording():
                if not self.is_recording:
                    break
                
                if self.connected:
                    # Send audio chunk to server
                    self.ws.send(chunk, opcode=websocket.ABNF.OPCODE_BINARY)
                else:
                    print("⚠️ Connection lost during recording")
                    break
        
        except Exception as e:
            print(f"❌ Recording error: {e}")
        finally:
            self.microphone.stop_recording()
    
    def stop_recording(self):
        """
        Stop recording and wait for server response
        """
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        # Wait for recording thread to finish
        if self.recording_thread:
            self.recording_thread.join(timeout=2)
        
        print("🛑 Recording stopped. Processing...")
    
    def shutdown(self):
        """
        Graceful shutdown
        """
        print("\n👋 Shutting down...")
        self.running = False
        
        # Stop recording if active
        if self.is_recording:
            self.stop_recording()
        
        # Stop speaker
        self.speaker.stop()
        
        # Close WebSocket
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
        
        print("✅ Shutdown complete")


def main():
    """
    Main entry point for RPi client (keyboard control mode)
    """
    import sys
    
    print("\n" + "="*50)
    print("   🤖 RPi Voice Assistant (Keyboard Mode)")
    print("="*50)
    print("\nPress SPACE to start recording, release to send")
    print("Press Ctrl+C to exit\n")
    
    client = RPiVoiceClient()
    
    # Start connection in background
    connection_thread = threading.Thread(target=client.connect, daemon=True)
    connection_thread.start()
    
    # Wait for connection
    while not client.connected and client.running:
        time.sleep(0.1)
    
    if not client.connected:
        print("❌ Failed to connect to server")
        return
    
    try:
        # Keyboard control loop
        from pynput import keyboard
        
        def on_press(key):
            if key == keyboard.Key.space:
                client.start_recording()
        
        def on_release(key):
            if key == keyboard.Key.space:
                client.stop_recording()
            elif key == keyboard.Key.esc:
                return False  # Stop listener
        
        print("✅ Ready! Press SPACE to talk.")
        
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    
    except KeyboardInterrupt:
        pass
    finally:
        client.shutdown()


if __name__ == "__main__":
    main()
