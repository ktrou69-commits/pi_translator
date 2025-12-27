import os
import json

class MemoryManager:
    def __init__(self, memory_file="memory.json"):
        # Get the directory of the root project (one level up from app/core)
        self.memory_file = memory_file

    def load_memory(self):
        if not os.path.exists(self.memory_file):
            return {"user_facts": []}
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except (json.JSONDecodeError, KeyError):
            return {"user_facts": []}

    def save_memory(self, memory_data):
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(memory_data, f, ensure_ascii=False, indent=2)
