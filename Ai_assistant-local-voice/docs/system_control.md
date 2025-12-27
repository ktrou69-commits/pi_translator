# System Control Technical Documentation

This document describes the implementation of system-level execution (Tools/Function Calling) in the AI Assistant.

## Overview
The system allows the AI to perform actions on the local machine (opening URLs, folders, and applications) in a safe, cross-platform manner using native LLM Function Calling.

## 🛠 Functionality
| Feature | Capability | Platform Support |
| :--- | :--- | :--- |
| **Open URL** | Opens any link in the default browser. | Windows, macOS, Linux |
| **Open Path** | Opens directories or files in the native file manager (Finder/Explorer). | Windows, macOS, Linux |
| **Run App** | Launches installed applications by their logical name. | Windows, macOS, Linux |

---

## 🛠 Code Infrastructure

### 1. `app/core/executor.py` [NEW]
The core engine for OS interaction.
- **`SystemExecutor` Class**: Contains static methods using `webbrowser` and `subprocess`.
- **`TOOL_DEFINITIONS`**: JSON Schema list passed to LLM backends to define the interface.

### 2. `app/backends/base.py` [MODIFIED]
- Updated `chat_stream` signature to include an optional `tools` parameter.

### 3. `app/backends/gemini.py` [MODIFIED]
- **Tool Integration**: Passes `TOOL_DEFINITIONS` to the `google-genai` SDK.
- **Intent Detection**: Identifies when the model wants to call a function.
- **Output Handling**: Yields `FunctionCall` objects alongside text chunks.

### 4. `server.py` [MODIFIED]
- **Tool Dispatcher**: Intercepts `FunctionCall` objects from the backend.
- **Execution Loop**: Calls `executor.py` methods and notifies the user via WebSocket:
  ```python
  if func_name == "open_url":
      executor.open_url(**func_args)
  ```

---

## 🔒 Security Measures
1. **White-listing**: The AI can ONLY execute functions defined in `TOOL_DEFINITIONS`.
2. **Explicit Hooks**: No arbitrary `eval()` or `exec()` is used for system commands.
3. **User Visibility**: The server logs every tool invocation: `🛠️ Model requested tool: ...`.

## 🧠 AI System Prompt (Gemini Example)

Here is a simplified version of what Gemini sees in its system instructions to handle these tools:

```text
Ты - персональный ассистент Gemini. Твои ответы основаны на ПАМЯТИ О ПОЛЬЗОВАТЕЛЕ.
СЕГОДНЯШНЯЯ ДАТА: 2025-12-27

ПАМЯТЬ О ПОЛЬЗОВАТЕЛЕ:
- [2025-12-26] Пользователь любит музыку в стиле Lo-Fi.
- [2025-12-27] Пользователь работает над проектом AI Assistant.

ИНСТРУКЦИИ:
1. Используй память.
2. Отвечай кратко и по делу.
3. Если тебя просят что-то открыть или запустить, используй доступные ИНСТРУМЕНТЫ (Tools).
```

### How the Model "Thinks":
When you say: *"Open the project folder"*, the model analyzes the prompt and the available tools, then generates a hidden command:
`Call: open_path(path="~/Desktop/7777777/Ai_assistant-local-voice")`
instead of just writing text.
