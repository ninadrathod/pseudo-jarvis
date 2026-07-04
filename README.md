# pseudo-jarvis

Voice-to-text converter powered with AI agents. **macOS only.**

## Prerequisites

- macOS with [Homebrew](https://brew.sh/) installed
- Microphone access enabled for Terminal (System Settings → Privacy & Security → Microphone)
- **Accessibility** enabled for Terminal (System Settings → Privacy & Security → Accessibility) — required to type at the cursor
- Internet connection (Google Speech Recognition)

## Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd pseudo-jarvis
   ```

2. **Create and activate the project virtual environment** (use this for all steps below)

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   Confirm the venv is active: your shell prompt may show `(.venv)`, or `which python` should point inside `.venv/`.

3. **Install and verify PortAudio** (system-level; required before PyAudio)

   ```bash
   brew install portaudio
   brew list portaudio
   ```

   `brew list portaudio` should print installed files (e.g. headers and `libportaudio.dylib`). If the command fails, run `brew install portaudio` again.

4. **Install Python dependencies** (with venv activated)

   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables** (when needed)

   ```bash
   cp .env.example .env
   # Edit .env with API keys and model settings
   ```

6. **Run the application** (with venv activated)

   ```bash
   python main.py
   ```

   1. Choose your microphone from the list.
   2. Open **Cursor Agent** and **click** in the message typing box — app types `@voice-input-confirmation.mds ` and **starts listening** automatically.
   3. Speak in Cursor Agent — text appears at the cursor.
      - **Pause longer than 2 seconds** → `. ` then **Shift+Enter**
      - **Say "snap" after a pause** → **Enter**, wait 0.5 s, then `@voice-input-confirmation.mds ` again
   4. Switch back to Terminal and press **`q`** to stop.

   Requires internet for Google Speech Recognition.

## Project files

| File / directory | Role |
|------------------|------|
| `main.py` | CLI entry point: device selection, start/stop prompts, runs `VoiceToText` |
| `app/voice_to_text.py` | `VoiceToText` — mic, cursor typing, pause `. `, say **snap** → Enter, stop |
| `app/` | Application source code (modules, agents, pipelines) |
| `requirements.txt` | Python deps: `SpeechRecognition`, `PyAudio`, `pyautogui`, `pynput` (install inside `.venv`) |
| `.gitignore` | Excludes build artifacts, secrets, `.venv/`, and local audio files |
| `.venv/` | Local Python virtual environment (gitignored); use for all `pip` and `python` commands |
| `README.md` | Setup instructions and this file reference table |
| `architecture.html` | Visual overview of how components connect |
| `.cursor/rules/sync-root-docs.mds` | Agent rule: keeps root docs in sync when the codebase changes |
| `.cursor/rules/voice-input-confirmation.mds` | Agent rule: assume voice input, confirm intent; proceed on **confirm.** / **Confirm.** |
