import asyncio
import threading
from RealtimeTTS.engines import BaseEngine
import edge_tts

class EdgeEngine(BaseEngine):
    def __init__(self, voice="ru-RU-SvetlanaNeural", speed=1.1):
        super().__init__()
        self.voice = voice
        self.speed = speed
        self.rate = f"{int((speed-1)*100):+d}%"

    def get_stream_info(self):
        # EdgeTTS usually outputs at 24000Hz, 16-bit, mono
        return 24000, 16, 1

    async def async_generate(self, text):
        """
        Asynchronous version of audio synthesis that yields raw PCM.
        """
        if not text.strip():
            return
            
        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
        
        # We'll use ffmpeg to decode the MP3 stream from edge-tts to raw PCM
        import subprocess

        command = [
            'ffmpeg',
            '-i', 'pipe:0',           # Read from stdin
            '-f', 's16le',            # Output format: raw PCM 16-bit little-endian
            '-acodec', 'pcm_s16le',
            '-ar', '24000',           # Sample rate: 24kHz
            '-ac', '1',               # Channels: mono
            'pipe:1'                  # Write to stdout
        ]

        # Use a non-blocking pipe if possible, but simplest is to feed in a thread
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        async def feed_ffmpeg():
            try:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        process.stdin.write(chunk["data"])
                process.stdin.close()
            except Exception as e:
                print(f"Error feeding ffmpeg: {e}")
                process.stdin.close()

        import threading
        # We can't easily wait for feed_ffmpeg in this async generator while reading stdout
        # So we run it in the event loop as a task
        feed_task = asyncio.create_task(feed_ffmpeg())

        # Read PCM chunks from stdout
        while True:
            # Read in small blocks (e.g., 2048 bytes)
            chunk = await asyncio.get_event_loop().run_in_executor(None, process.stdout.read, 2048)
            if not chunk:
                break
            yield chunk

        await feed_task
        process.wait()

    def _generate(self, text):
        """
        Synchronous version for RealtimeTTS compatibility.
        Now also yields raw PCM.
        """
        if not text.strip():
            return

        loop = asyncio.new_event_loop()
        try:
            gen = self.async_generate(text)
            while True:
                try:
                    chunk = loop.run_until_complete(gen.__anext__())
                    yield chunk
                except StopAsyncIteration:
                    break
        finally:
            loop.close()
