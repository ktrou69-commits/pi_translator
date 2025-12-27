import requests
import json

SERVER_URL = "http://localhost:8000/chat"

def test_memory(text):
    print(f"🧪 Testing extraction for: '{text}'")
    try:
        response = requests.post(SERVER_URL, json={"user_text": text})
        if response.status_code == 200:
            print(f"🤖 AI Response: {response.json().get('response')}")
            print("✅ Check your memory.json now!")
        else:
            print(f"❌ Error: {response.status_code}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    test_text = input("Введите факт для теста (например, 'Я люблю футбол'): ")
    test_memory(test_text)
