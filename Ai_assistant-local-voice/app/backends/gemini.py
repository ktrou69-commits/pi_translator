import datetime
import json
from google import genai
from stream2sentence import generate_sentences
from .base import BaseBackend

class GeminiBackend(BaseBackend):
    def __init__(self, api_key, model_name="gemini-2.5-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def chat_stream(self, user_input, memory_data):
        facts_list = "\n".join([f"- [{f['created_at']}] {f['text']}" for f in memory_data.get("user_facts", [])])
        current_date = datetime.date.today().strftime("%Y-%m-%d")
        
        sys_prompt = f"""
        Ты - персональный ассистент Gemini. Твои ответы основаны на ПАМЯТИ О ПОЛЬЗОВАТЕЛЕ.
        СЕГОДНЯШНЯЯ ДАТА: {current_date}
        ПАМЯТЬ:
        {facts_list}
        ИНСТРУКЦИИ: Используй память. Отвечай кратко (до 20 слов), четко, без воды.
        """
        
        def generate():
            # In google-genai, we use generate_content_stream for streaming
            response = self.client.models.generate_content_stream(
                model=self.model_name,
                config={'system_instruction': sys_prompt},
                contents=user_input
            )
            for chunk in response:
                yield chunk.text

        for sentence in generate_sentences(generate()):
            yield sentence

    def memory_observer(self, user_input, current_memory, save_callback):
        sys_prompt = """
        Ты - аналитик данных. Найди факты о ПОЛЬЗОВАТЕЛЕ. 
        Верни ТОЛЬКО JSON: {"new_fact": "текст факта в 3-м лице или null"}
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                config={'system_instruction': sys_prompt, 'response_mime_type': 'application/json'},
                contents=user_input
            )
            if response.text:
                data = json.loads(response.text)
                new_fact_text = data.get("new_fact")
                if new_fact_text:
                    existing_texts = [f["text"] for f in current_memory.get("user_facts", [])]
                    if new_fact_text not in existing_texts:
                        today = datetime.date.today().isoformat()
                        new_entry = {"text": new_fact_text, "created_at": today}
                        if "user_facts" not in current_memory:
                            current_memory["user_facts"] = []
                        current_memory["user_facts"].append(new_entry)
                        save_callback(current_memory)
                        print(f"🧠 [Gemini-Memory]: Запомнил -> {new_fact_text}")
        except Exception as e:
            print(f"⚠️ Gemini Memory Error: {e}")
