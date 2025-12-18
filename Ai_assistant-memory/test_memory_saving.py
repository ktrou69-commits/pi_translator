import os
import json
from ai_assistant import ai_memory_observer, load_memory, MEMORY_FILE

def test_fact_saving():
    print("🧪 Starting Memory Save Test...")
    
    # 1. Load initial memory
    initial_memory = load_memory()
    initial_count = len(initial_memory["user_facts"])
    print(f"📊 Initial facts count: {initial_count}")
    
    # 2. Define a test input with a clear fact
    test_input = "Я только что купил красный велосипед."
    print(f"🗣️  Simulated User Input: '{test_input}'")
    
    # 3. Run the observer
    print("⏳ Running AI Memory Observer...")
    ai_memory_observer(test_input, initial_memory)
    
    # 4. Verify in memory object
    new_count = len(initial_memory["user_facts"])
    print(f"📊 Facts count after update: {new_count}")
    
    if new_count > initial_count:
        print("✅ Success: Fact added to memory object.")
        print(f"📝 Newest fact: {initial_memory['user_facts'][-1]}")
    else:
        print("❌ Failure: Fact was NOT added to memory object.")
        
    # 5. Verify file persistence
    print(f"📂 Checking file: {MEMORY_FILE}")
    with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
        file_data = json.load(f)
        file_count = len(file_data["user_facts"])
        
    if file_count == new_count:
        print("✅ Success: Fact persisted to memory.json.")
    else:
        print(f"❌ Failure: File count ({file_count}) does not match memory object count ({new_count}).")

if __name__ == "__main__":
    test_fact_saving()
