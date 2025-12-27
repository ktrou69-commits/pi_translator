import datetime
import json
from google import genai
from stream2sentence import generate_sentences
from .base import BaseBackend

class GeminiBackend(BaseBackend):
    def __init__(self, api_key, model_name="gemini-2.5-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def chat_stream(self, user_input, memory_data, tools=None):
        facts_list = "\n".join([f"- [{f['created_at']}] {f['text']}" for f in memory_data.get("user_facts", [])])
        current_date = datetime.date.today().strftime("%Y-%m-%d")
        
        sys_prompt = f"""
        Ты - персональный ассистент Gemini. Твои ответы основаны на ПАМЯТИ О ПОЛЬЗОВАТЕЛЕ.
        СЕГОДНЯШНЯЯ ДАТА: {current_date}
        
        ПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ:
        {facts_list}
        
        ИНСТРУКЦИИ:
        1. Используй память.
        2. Отвечай кратко и по делу.
        3. Если тебя просят что-то открыть или запустить, используй доступные ИНСТРУМЕНТЫ (Tools).
        """
        
        config = {'system_instruction': sys_prompt}
        if tools:
            # google-genai expects tools as a list of types.Tool or dicts with function_declarations
            config['tools'] = [{'function_declarations': tools}]

        def generate():
            try:
                response = self.client.models.generate_content_stream(
                    model=self.model_name,
                    config=config,
                    contents=user_input
                )
                for chunk in response:
                    # Check for function calls
                    if chunk.candidates and chunk.candidates[0].content.parts:
                        for part in chunk.candidates[0].content.parts:
                            if part.function_call:
                                yield part.function_call
                            elif part.text:
                                yield part.text
            except Exception as e:
                yield f"⚠️ Gemini Error: {e}"

        # We wrap in generate_sentences to ensure the client gets clean audio blocks
        # But we must be careful: if generate() yields a function call, generate_sentences might choke.
        # So we'll iterate manually and only group text.
        
        current_text = ""
        for item in generate():
            if isinstance(item, str):
                current_text += item
                # Check if we have enough for a sentence
                # (Standard sentence splitting logic or just pass through)
                # For simplicity, we'll yield text chunks, but the server expects sentences for TTS.
                # Let's keep generate_sentences for text only.
                pass
            else:
                # It's a function call (object)
                yield item
        
        # If we have remaining text, process it with generate_sentences
        if current_text:
            for sentence in generate_sentences([current_text]):
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
