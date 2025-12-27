from abc import ABC, abstractmethod

class BaseBackend(ABC):
    @abstractmethod
    def chat_stream(self, user_input, memory_data):
        """Generates full sentences from the LLM stream."""
        pass

    @abstractmethod
    def memory_observer(self, user_input, current_memory, save_callback):
        """Extracts facts about the user."""
        pass
