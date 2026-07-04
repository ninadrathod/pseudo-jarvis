# pseudo-jarvis

Voice-to-text for **Cursor Agent** on macOS. Speak in the chat panel; recognized text is typed at the cursor.

## Prerequisites

- macOS with [Homebrew](https://brew.sh/) installed
- **Microphone** — grant access to **pseudo-jarvis** (`.app`) or **Terminal** (when running `python gui_app.py` from source)
- **Accessibility** — same app as above; required for simulated keystrokes into Cursor
- Internet connection (Google Speech Recognition)

## Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd pseudo-jarvis
   ```

2. **Install and verify PortAudio** (system library; required before PyAudio)

   ```bash
   brew install portaudio
   brew list portaudio
   ```

   `brew list portaudio` should print installed files (e.g. headers and `libportaudio.dylib`). If it fails, run `brew install portaudio` again.

3. **Run the setup script** (recommended)

   ```bash
   ./setup.sh
   ```

   This creates local config, a virtual environment, and installs Python dependencies:

   | Output | Purpose |
   |--------|---------|
   | `setup-variables/mds-path.txt` | Absolute path to `.cursor/rules/voice-input-confirmation.mds` (source for **ADD project**) |
   | `setup-variables/subscribed-projects.txt` | One project root per line (starts with this repo); updated when you **ADD** Cursor projects |
   | `.venv/` | Local Python environment (gitignored) |

   Both files under `setup-variables/` are **gitignored** — they are machine-local.

   **Manual setup** (equivalent to `./setup.sh` without re-running venv steps you already did):

   ```bash
   mkdir -p setup-variables
   printf '%s\n' "$(pwd)/.cursor/rules/voice-input-confirmation.mds" > setup-variables/mds-path.txt
   printf '%s/\n' "$(pwd)" > setup-variables/subscribed-projects.txt

   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Run the application**

   ```bash
   source .venv/bin/activate
   python gui_app.py
   ```

   **macOS app bundle** (after `./setup.sh`):

   ```bash
   ./build_app.sh
   cp -R dist/pseudo-jarvis.app /Applications/
   ```

   The bundled app uses `~/Library/Application Support/pseudo-jarvis/setup-variables/` when no local `setup-variables/` folder exists next to the `.app`.

## Using the app

1. **Add a Cursor project** (first time per repo): enter the project root and click **ADD**. This copies `voice-input-confirmation.mds` into that project's `.cursor/rules/` and appends the path to `subscribed-projects.txt`.
2. Choose your **microphone**, then click **Start**.
3. Open **Cursor Agent** and **click** in the message typing box — the app types `@voice-input-confirmation.mds `, waits 0.3 s, presses **Enter**, and starts listening.
4. Speak in Cursor Agent — text appears at the cursor.
   - **Pause longer than 2 seconds** → `. ` then **Shift+Enter**
   - **Say "send" after a pause** → **Enter**, wait 0.5 s, then `@voice-input-confirmation.mds ` → wait 0.3 s → **Enter**
   - **Say "freeze" after a pause** → freezes dictation (mic still listens for **resume**)
   - **Say "resume"** (only after freeze) → click typing box → rule mention → then dictate
5. Click **Stop** in the pseudo-jarvis window to end the session.

Requires internet for Google Speech Recognition.

## Project files

| File / directory | Role |
|------------------|------|
| `gui_app.py` | tkinter GUI: Start / Stop, mic picker, project subscription, session log |
| `build_app.sh` | PyInstaller script → `dist/pseudo-jarvis.app` for Applications folder |
| `app/project_registry.py` | Reads `setup-variables/`; ADD copies voice rule, updates registry, gitignore |
| `app/session.py` | Session runner used by `gui_app.py` |
| `app/voice_to_text.py` | `VoiceToText` — mic, cursor typing, voice commands, stop |
| `setup.sh` | Creates `setup-variables/`, `.venv`, installs `requirements.txt` |
| `requirements.txt` | Python deps: `SpeechRecognition`, `PyAudio`, `pyautogui`, `pynput` |
| `index.html` | GitHub Pages site: architecture, App UI, workflows (`styles.css` linked) |
| `styles.css` | Stylesheet for `index.html` (GitHub Pages) |
| `.cursor/rules/voice-input-confirmation.mds` | Agent rule: assume voice input, confirm intent; proceed on **confirm.** / **Confirm.** |
| `.cursor/rules/sync-root-docs.mds` | Dev agent rule: keeps root docs in sync when the codebase changes |
| `setup-variables/` | Local config (gitignored): `mds-path.txt`, `subscribed-projects.txt` |
