import datetime
import json
from groq import Groq
from stream2sentence import generate_sentences
from .base import BaseBackend

class MockFunctionCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args

class GroqBackend(BaseBackend):
    def __init__(self, api_key, model_name="llama-3.3-70b-versatile"):
        self.client = Groq(api_key=api_key)
        self.model_name = model_name

    def chat_stream(self, user_input, memory_data, tools=None):
        facts_list = "\n".join([f"- [{f['created_at']}] {f['text']}" for f in memory_data.get("user_facts", [])])
        current_date = datetime.date.today().strftime("%Y-%m-%d")
        
        sys_prompt = f"""
        Ты - "01", голосовой исполнительный ассистент. Ты можешь выполнить любую задачу. 
        Твой интерфейс — исключительно голосовой.
        СЕГОДНЯШНЯЯ ДАТА: {current_date}
        
        ПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ:
        {facts_list}
        
        ИНСТРУКЦИИ:
        - Будь КРАТКИМ. Твои сообщения читаются пользователю вслух. Отвечай не более 1-2 предложений.
        - НЕ СТРОЙ ПЛАНОВ. ДЕЙСТВУЙ БЫСТРО.
        - Не рассказывай пользователю, какой метод ты используешь. Сразу дай подтверждение и выполняй.
        - Если команда понятна (открой, запусти), вызывай инструмент НЕМЕДЛЕННО.
        - Используй "Память о пользователе" для контекста, но никогда не читай её целиком.
        - ТОЛЬКО ПРОСТОЙ ТЕКСТ. Никакого Markdown (никаких **, #, `), никаких специальных символов или формул.
        - Произноси специальные символы словами (например, "градусов" вместо °).
        - Для чисто текстовых задач (цитаты, ответы на вопросы) инструменты НЕ ИСПОЛЬЗУЙ.
        """
        
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_input}
        ]

        def run_completion(use_tools=True):
            groq_tools = []
            if use_tools and tools:
                for tool in tools:
                    groq_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool["description"],
                            "parameters": tool["parameters"]
                        }
                    })

            params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0.1,
                "top_p": 0.8,
                "max_tokens": 512,
                "stream": True,
            }
            if groq_tools:
                params["tools"] = groq_tools
                params["tool_choice"] = "auto"

            return self.client.chat.completions.create(**params)

        try:
            # First attempt with tools
            try:
                stream = run_completion(use_tools=True)
                yield from self._process_stream(stream)
            except Exception as e:
                error_msg = str(e)
                if "Failed to call a function" in error_msg or "tool call" in error_msg.lower():
                    print(f"🔄 [Groq-Recovery]: Tool error detected, retrying without tools...")
                    # Silent retry without tools
                    stream = run_completion(use_tools=False)
                    yield from self._process_stream(stream)
                else:
                    raise e

        except Exception as e:
            print(f"❌ [Groq-Final-Error]: {e}")
            yield "Извини, произошла техническая ошибка. Попробуй еще раз."

    def _process_stream(self, stream):
        current_text = ""
        tool_calls = {}

        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if tc_delta.id and tc_delta.function:
                        tool_calls[idx] = {"id": tc_delta.id, "name": tc_delta.function.name, "arguments": ""}
                    if tc_delta.function and tc_delta.function.arguments:
                        tool_calls[idx]["arguments"] += tc_delta.function.arguments

            if delta.content:
                current_text += delta.content

        # Yield tool calls
        for idx in sorted(tool_calls.keys()):
            tc = tool_calls[idx]
            try:
                args = json.loads(tc["arguments"])
                yield MockFunctionCall(tc["name"], args)
            except: pass

        # Clean and yield text
        if current_text:
            import re
            current_text = re.sub(r'<function.*?>.*?</function>', '', current_text, flags=re.DOTALL)
            current_text = re.sub(r'\[🛠️.*?\]', '', current_text)
            if current_text.strip():
                for sentence in generate_sentences([current_text]):
                    yield sentence

    def memory_observer(self, user_input, current_memory, save_callback):
        sys_prompt = """
        Ты - аналитик данных. Найди новые факты о ПОЛЬЗОВАТЕЛЕ в его сообщении. 
        Верни ТОЛЬКО JSON: {"new_fact": "текст факта в 3-м лице или null"}
        """
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_input}
                ],
                response_format={"type": "json_object"}
            )
            
            response_text = completion.choices[0].message.content
            if response_text:
                data = json.loads(response_text)
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
                        print(f"🧠 [Groq-Memory]: Запомнил -> {new_fact_text}")
        except Exception as e:
            print(f"⚠️ Groq Memory Error: {e}")
