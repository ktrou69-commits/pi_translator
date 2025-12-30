"""
Raspberry Pi GPIO Control
Handles physical button for voice recording control
"""
import time
from typing import Callable, Optional

try:
    import gpiod
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("⚠️ gpiod not available. GPIO control disabled.")

from app import rpi_config


class ButtonHandler:
    """
    GPIO button handler with debounce and hold detection
    Uses modern gpiod library (compatible with Raspberry Pi OS Bookworm)
    """
    
    def __init__(
        self,
        pin: int = rpi_config.GPIO_BUTTON_PIN,
        debounce_ms: int = rpi_config.GPIO_DEBOUNCE_MS,
        on_press: Optional[Callable] = None,
        on_release: Optional[Callable] = None
    ):
        """
        Initialize button handler
        
        Args:
            pin: GPIO pin number (BCM numbering)
            debounce_ms: Debounce time in milliseconds
            on_press: Callback when button is pressed
            on_release: Callback when button is released
        """
        if not GPIO_AVAILABLE:
            raise RuntimeError("gpiod library not available. Install with: sudo apt install python3-libgpiod")
        
        self.pin = pin
        self.debounce_ms = debounce_ms
        self.on_press = on_press
        self.on_release = on_release
        
        # GPIO setup
        self.chip = gpiod.Chip('gpiochip0')
        self.line = self.chip.get_line(pin)
        
        # Configure as input with pull-up resistor
        self.line.request(consumer="voice_button", type=gpiod.LINE_REQ_DIR_IN, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
        
        # State tracking
        self.is_pressed = False
        self.last_change_time = 0
        self.running = False
        
        print(f"🔘 Button handler initialized on GPIO {pin}")
    
    def start(self):
        """Start monitoring button state"""
        self.running = True
        print("👂 Listening for button press...")
        
        try:
            while self.running:
                current_state = self.line.get_value() == 0  # 0 = pressed (pull-up)
                current_time = time.time() * 1000  # milliseconds
                
                # Debounce check
                if current_time - self.last_change_time < self.debounce_ms:
                    time.sleep(0.01)
                    continue
                
                # State change detection
                if current_state != self.is_pressed:
                    self.is_pressed = current_state
                    self.last_change_time = current_time
                    
                    if self.is_pressed and self.on_press:
                        self.on_press()
                    elif not self.is_pressed and self.on_release:
                        self.on_release()
                
                time.sleep(0.01)  # 10ms polling interval
        
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
    
    def stop(self):
        """Stop monitoring and cleanup"""
        self.running = False
        if self.line:
            self.line.release()
        print("🔘 Button handler stopped")


def test_button():
    """Test GPIO button functionality"""
    print("\n=== GPIO Button Test ===")
    print(f"Testing GPIO pin {rpi_config.GPIO_BUTTON_PIN}")
    print("Press the button to test...")
    print("Press Ctrl+C to exit\n")
    
    def on_press():
        print("🔴 Button PRESSED")
    
    def on_release():
        print("⚪ Button RELEASED")
    
    handler = ButtonHandler(on_press=on_press, on_release=on_release)
    handler.start()


if __name__ == "__main__":
    test_button()
