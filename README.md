# pseudo-jarvis

Voice-to-text converter powered with AI agents.

## Setup

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd pseudo-jarvis
   ```

2. **Create and activate a virtual environment**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # macOS / Linux
   # .venv\Scripts\activate    # Windows
   ```

3. **Install dependencies** (when `requirements.txt` is added)

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables** (when needed)

   ```bash
   cp .env.example .env
   # Edit .env with API keys and model settings
   ```

5. **Run the application** (entry point TBD as the project grows)

   ```bash
   python -m app.voice_to_text
   ```

## Project files

| File / directory | Role |
|------------------|------|
| `app/voice_to_text.py` | Core `VoiceToText` class: captures audio and produces transcript text |
| `app/` | Application source code (modules, agents, pipelines) |
| `.gitignore` | Excludes build artifacts, secrets, virtual envs, and local audio files |
| `README.md` | Setup instructions and this file reference table |
| `architecture.html` | Visual overview of how components connect |
| `.cursor/rules/sync-root-docs.mds` | Agent rule: keeps root docs in sync when the codebase changes |
