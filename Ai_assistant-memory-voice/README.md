# 🎙️ Voice AI Assistant with Memory

Голосовой ассистент "Кент" на базе Gemini 2.5 Flash.
*   **Слушает** (Google STT)
*   **Думает и помнит** (Gemini + JSON Memory)
*   **Говорит** (Google TTS + BlueALSA)

## 🛠 Системные требования (Raspberry Pi)

```bash
sudo apt-get update
sudo apt-get install -y python3-pyaudio portaudio19-dev mpg123 alsa-utils flac sox libsox-fmt-all
```
```bash
sudo apt-get update
sudo apt-get install -y python3-pyaudio portaudio19-dev mpg123 alsa-utils flac
```
**Важно:** `alsa-utils` нужен для команды `aplay`. Без него звука не будет!

## 🛠 Системные требования (macOS)

```bash
brew install portaudio
```
*(Остальное уже есть в системе)*

## 🚀 Установка

1.  **Перейдите в папку:**
    ```bash
    cd Ai_assistant-memory-voice
    ```

2.  **Установите библиотеки:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Ключ API:**
    Уже настроен в `.env`.

## ▶️ Запуск

```bash
python voice_assistant.py
```

## 🧠 Память
Файл `memory.json` общий с текстовой версией (если вы скопировали его).
Ассистент помнит, что вы любите тюфтели! 🍝
