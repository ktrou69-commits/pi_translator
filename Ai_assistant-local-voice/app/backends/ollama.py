import datetime
import json
import ollama
from stream2sentence import generate_sentences
from .base import BaseBackend

class OllamaBackend(BaseBackend):
    def __init__(self, model_name="qwen2.5-coder:3b"):
        self.model_name = model_name

    def chat_stream(self, user_input, memory_data, tools=None):
        facts_list = "\n".join([f"- [{f['created_at']}] {f['text']}" for f in memory_data.get("user_facts", [])])
        current_date = datetime.date.today().strftime("%Y-%m-%d")
        
        sys_prompt = f"""
        Ты - всезнающий персональный ассистент. Твои ответы должны основываться на ПАМЯТИ О ПОЛЬЗОВАТЕЛЕ.
        СЕГОДНЯШНЯЯ ДАТА: {current_date}
        
        ПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ (это абсолютная истина):
        {facts_list}
        
        ИНСТРУКЦИИ:
        1. Если в памяти есть ответ на вопрос пользователя (например, про планы) - отвечай прямо: "У тебя в понедельник тест". 
        2. НИКОГДА не говори "Я не знаю", если информация есть в ПАМЯТИ.
        3. Стиль: Краткий, четкий, без вступлений. Максимум 15-20 слов.
        """
        
        def generate():
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': sys_prompt},
                    {'role': 'user', 'content': user_input}
                ],
                stream=True
            )
            for chunk in response:
                yield chunk['message']['content']

        for sentence in generate_sentences(generate()):
            yield sentence

    def memory_observer(self, user_input, current_memory, save_callback):
        sys_prompt = """
        Ты - аналитик персональных данных. Твоя задача: находить КОНКРЕТНЫЕ факты о ПОЛЬЗОВАТЕЛЕ.
        Верни JSON: {"new_fact": "текст факта в 3-м лице или null"}
        """
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': sys_prompt},
                    {'role': 'user', 'content': user_input}
                ],
                format='json'
            )
            content = response['message']['content']
            if content:
                data = json.loads(content)
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
                        print(f"🧠 [Ollama-Memory]: Запомнил -> {new_fact_text}")
        except Exception as e:
            print(f"⚠️ Ollama Memory Error: {e}")
