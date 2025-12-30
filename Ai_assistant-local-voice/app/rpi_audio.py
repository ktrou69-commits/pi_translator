"""
Raspberry Pi Audio Subsystem
Manages audio recording (USB mic via arecord) and playback (Bluetooth via aplay/bluealsa)
"""
import subprocess
import threading
import queue
import time
from dataclasses import dataclass
from typing import Optional, Generator


@dataclass
class AudioConfig:
    """Audio configuration for Raspberry Pi"""
    mic_device: str = "hw:1,0"  # USB microphone (card 1, device 0)
    speaker_device: str = "bluealsa"  # Bluetooth speaker via BlueALSA
    sample_rate: int = 16000  # 16kHz for Whisper STT
    chunk_size: int = 1024  # Bytes per chunk
    format: str = "S16_LE"  # 16-bit signed little-endian
    channels: int = 1  # Mono


class RPiMicrophone:
    """
    USB Microphone recorder using ALSA (arecord)
    Streams audio chunks in real-time for WebSocket transmission
    """
    
    def __init__(self, config: AudioConfig):
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.is_recording = False
        self._chunk_queue = queue.Queue()
        self._reader_thread: Optional[threading.Thread] = None
    
    def start_recording(self) -> Generator[bytes, None, None]:
        """
        Start recording and yield audio chunks
        
        Yields:
            bytes: Audio chunks (1024 bytes each, 16kHz mono PCM)
        """
        if self.is_recording:
            raise RuntimeError("Already recording")
        
        # Build arecord command
        cmd = [
            "arecord",
            "-D", self.config.mic_device,
            "-f", self.config.format,
            "-r", str(self.config.sample_rate),
            "-c", str(self.config.channels),
            "-t", "raw",  # Raw PCM output
            "--buffer-size", str(self.config.chunk_size * 4),  # Buffer for smooth streaming
        ]
        
        try:
            # Start arecord subprocess
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=self.config.chunk_size
            )
            self.is_recording = True
            print(f"🎤 [RPi-Mic] Recording started from {self.config.mic_device}")
            
            # Read chunks from stdout
            while self.is_recording and self.process.poll() is None:
                chunk = self.process.stdout.read(self.config.chunk_size)
                if chunk:
                    yield chunk
                else:
                    break
                    
        except Exception as e:
            print(f"❌ [RPi-Mic] Recording error: {e}")
            self.stop_recording()
            raise
    
    def stop_recording(self):
        """Stop recording and cleanup"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            finally:
                self.process = None
        
        print("🛑 [RPi-Mic] Recording stopped")


class RPiSpeaker:
    """
    Bluetooth Speaker playback using ALSA (aplay + bluealsa)
    Plays TTS responses received from server
    """
    
    def __init__(self, config: AudioConfig):
        self.config = config
        self.is_playing = False
        self._play_queue = queue.Queue()
        self._player_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def start(self):
        """Start the playback worker thread"""
        if self._player_thread and self._player_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._player_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self._player_thread.start()
        print(f"🔊 [RPi-Speaker] Playback worker started for {self.config.speaker_device}")
    
    def play(self, audio_data: bytes):
        """
        Queue audio data for playback
        
        Args:
            audio_data: Raw PCM audio bytes (24kHz mono from EdgeTTS)
        """
        self._play_queue.put(audio_data)
    
    def _playback_worker(self):
        """Background worker that plays queued audio"""
        while not self._stop_event.is_set():
            try:
                # Wait for audio data (timeout to check stop event)
                audio_data = self._play_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            
            # Play audio via aplay
            self._play_chunk(audio_data)
            self._play_queue.task_done()
    
    def _play_chunk(self, audio_data: bytes):
        """
        Play a single audio chunk via aplay
        
        Args:
            audio_data: Raw PCM audio bytes
        """
        if not audio_data:
            return
        
        # Build aplay command
        # Note: EdgeTTS sends 24kHz audio, so we use that rate
        cmd = [
            "aplay",
            "-D", self.config.speaker_device,
            "-f", self.config.format,
            "-r", "24000",  # EdgeTTS output rate
            "-c", str(self.config.channels),
            "-t", "raw",
        ]
        
        try:
            self.is_playing = True
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Write audio data to stdin
            process.stdin.write(audio_data)
            process.stdin.close()
            process.wait()
            
        except Exception as e:
            print(f"❌ [RPi-Speaker] Playback error: {e}")
        finally:
            self.is_playing = False
    
    def stop(self):
        """Stop the playback worker"""
        self._stop_event.set()
        if self._player_thread:
            self._player_thread.join(timeout=2)
        
        # Clear any remaining queued audio
        while not self._play_queue.empty():
            try:
                self._play_queue.get_nowait()
            except queue.Empty:
                break
        
        print("🛑 [RPi-Speaker] Playback worker stopped")
    
    def wait_until_done(self):
        """Block until all queued audio is played"""
        self._play_queue.join()


# Test function for local audio loop (record → playback)
def test_audio_loop():
    """
    Test audio subsystem locally without server
    Records 5 seconds and plays it back through Bluetooth
    """
    import tempfile
    
    config = AudioConfig()
    mic = RPiMicrophone(config)
    speaker = RPiSpeaker(config)
    
    print("\n=== RPi Audio Test ===")
    print("Recording 5 seconds from USB mic...")
    
    # Record to temporary file
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as tmp:
        tmp_path = tmp.name
        
        # Record for 5 seconds
        chunk_count = 0
        max_chunks = (config.sample_rate * 5) // config.chunk_size
        
        for chunk in mic.start_recording():
            tmp.write(chunk)
            chunk_count += 1
            if chunk_count >= max_chunks:
                break
        
        mic.stop_recording()
    
    print(f"✅ Recorded {chunk_count} chunks to {tmp_path}")
    print("Playing back through Bluetooth...")
    
    # Read and play back
    speaker.start()
    with open(tmp_path, "rb") as f:
        while True:
            chunk = f.read(config.chunk_size)
            if not chunk:
                break
            speaker.play(chunk)
    
    speaker.wait_until_done()
    speaker.stop()
    
    print("✅ Audio test complete!")
    
    # Cleanup
    import os
    os.remove(tmp_path)


if __name__ == "__main__":
    # Run local test
    test_audio_loop()
