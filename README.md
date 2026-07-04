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

2. **Install and verify PortAudio** (system-level; required before PyAudio)

   ```bash
   brew install portaudio
   brew list portaudio
   ```

   `brew list portaudio` should print installed files (e.g. headers and `libportaudio.dylib`). If the command fails, run `brew install portaudio` again.

3. **Run the setup script** (creates `setup-variables/`, local path files, `.venv`, and installs dependencies)

   ```bash
   ./setup.sh
   ```

   Or set up manually — **create and activate the project virtual environment** (use for all steps below):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   Confirm the venv is active: your shell prompt may show `(.venv)`, or `which python` should point inside `.venv/`.

4. **Configure environment variables** (when needed)

   ```bash
   cp .env.example .env
   # Edit .env with API keys and model settings
   ```

5. **Run the application** (with venv activated)

   ```bash
   python main.py
   ```

   1. Choose your microphone from the list.
   2. Open **Cursor Agent** and **click** in the message typing box — app types `@voice-input-confirmation.mds ` and **starts listening** automatically.
   3. Speak in Cursor Agent — text appears at the cursor.
      - **Pause longer than 2 seconds** → `. ` then **Shift+Enter**
      - **Say "send" after a pause** → **Enter**, wait 0.5 s, then `@voice-input-confirmation.mds ` again
      - **Say "freeze" after a pause** → freezes dictation (mic still listens for **resume**)
      - **Say "resume"** (only after freeze) → click typing box → `@voice-input-confirmation.mds ` → then dictate
   4. Switch back to Terminal and press **`q`** to stop.

   Requires internet for Google Speech Recognition.

## Project files

| File / directory | Role |
|------------------|------|
| `main.py` | CLI entry point: device selection, start/stop prompts, runs `VoiceToText` |
| `app/voice_to_text.py` | `VoiceToText` — mic, cursor typing, pause `. `, say **send** → Enter, stop |
| `app/` | Application source code (modules, agents, pipelines) |
| `setup.sh` | One-shot setup: `setup-variables/` path files, `.venv`, `pip install -r requirements.txt` |
| `requirements.txt` | Python deps: `SpeechRecognition`, `PyAudio`, `pyautogui`, `pynput` (install inside `.venv`) |
| `.gitignore` | Excludes build artifacts, secrets, `.venv/`, `setup-variables/`, and local audio files |
| `setup-variables/` | Local setup (gitignored): `mds-path.txt`, `subscribed-projects.txt` (written by `setup.sh`) |
| `.venv/` | Local Python virtual environment (gitignored); use for all `pip` and `python` commands |
| `README.md` | Setup instructions and this file reference table |
| `index.html` | GitHub Pages site: project overview, architecture diagrams, command workflows (`styles.css` linked) |
| `styles.css` | Stylesheet for `index.html` (GitHub Pages) |
| `.cursor/rules/sync-root-docs.mds` | Agent rule: keeps root docs in sync when the codebase changes |
| `.cursor/rules/voice-input-confirmation.mds` | Agent rule: assume voice input, confirm intent; proceed on **confirm.** / **Confirm.** |
