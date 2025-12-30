"""
Raspberry Pi Voice Client with GPIO Button Control
Main entry point for button-controlled voice interaction
"""
import sys
from app.rpi_client import RPiVoiceClient
from app.rpi_gpio import ButtonHandler, GPIO_AVAILABLE
import threading
import time


def main():
    """
    Main entry point for RPi client with GPIO button control
    """
    print("\n" + "="*50)
    print("   🤖 RPi Voice Assistant (Button Mode)")
    print("="*50)
    
    if not GPIO_AVAILABLE:
        print("\n❌ GPIO library not available!")
        print("   Install with: sudo apt install python3-libgpiod")
        print("   Or use keyboard mode: python app/rpi_client.py")
        sys.exit(1)
    
    print("\nHold button to record, release to send")
    print("Press Ctrl+C to exit\n")
    
    # Initialize client
    client = RPiVoiceClient()
    
    # Start connection in background
    connection_thread = threading.Thread(target=client.connect, daemon=True)
    connection_thread.start()
    
    # Wait for connection
    print("⏳ Connecting to server...")
    while not client.connected and client.running:
        time.sleep(0.1)
    
    if not client.connected:
        print("❌ Failed to connect to server")
        sys.exit(1)
    
    print("✅ Connected! Ready to use button.\n")
    
    # Setup GPIO button
    def on_button_press():
        client.start_recording()
    
    def on_button_release():
        client.stop_recording()
    
    try:
        button = ButtonHandler(
            on_press=on_button_press,
            on_release=on_button_release
        )
        button.start()  # Blocking call
    
    except KeyboardInterrupt:
        print("\n")
    finally:
        client.shutdown()


if __name__ == "__main__":
    main()
