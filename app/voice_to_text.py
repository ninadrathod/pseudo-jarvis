"""Voice capture and transcription for pseudo-jarvis."""

import subprocess
import sys
import threading
import time
from queue import Empty, PriorityQueue
from typing import Callable, Optional, Tuple

import pyautogui
import pyaudio
import speech_recognition as sr

# (priority, sequence, recognizer, audio) — lower priority value is processed first.
RecognitionJob = Tuple[int, int, sr.Recognizer, sr.AudioData]


class VoiceToText:
    """
    Captures microphone audio and transcribes speech to text in real time.

    Uses the selected microphone and Google's free speech recognition API
    (requires an internet connection). Recognized text is typed at the current
    cursor position in whichever app has focus.
    """

    # Single-character key that stops listening (case-insensitive).
    STOP_KEY = "q"

    # Pause threshold (seconds): type ". " once when silence exceeds this value.
    PAUSE_PERIOD_AFTER = 2.0

    # How long silence (seconds) ends a speech chunk for the recognizer.
    # Keep below PAUSE_PERIOD_AFTER so phrases split before ". " is typed.
    SPEECH_PAUSE_THRESHOLD = 1.0

    # Voice command: say this word after a pause to press Enter at the cursor.
    SEND_COMMAND = "send"

    # Voice commands: freeze stops dictation; resume continues (only after freeze).
    FREEZE_COMMAND = "freeze"
    RESUME_COMMAND = "resume"
    # Common Google Speech mis-hearings for "resume" (checked after freeze only).
    RESUME_ALIASES = frozenset({"presume"})

    # Typed after mic selection + click, and again after send or resume.
    VOICE_RULE_MENTION = "@voice-input-confirmation.mds"

    # Delay after Enter on send before typing VOICE_RULE_MENTION.
    SEND_RULE_DELAY = 0.5

    @staticmethod
    def select_input_device() -> int:
        """
        List available microphone input devices and prompt the user to choose one.

        Returns the PyAudio device index for the selected input device. That index
        is used for the entire VoiceToText session.
        """
        audio = pyaudio.PyAudio()
        input_devices: list[tuple[int, str, int]] = []

        try:
            for index in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(index)
                if info.get("maxInputChannels", 0) > 0:
                    name = info.get("name", "Unknown device")
                    channels = int(info["maxInputChannels"])
                    input_devices.append((index, name, channels))
        finally:
            audio.terminate()

        if not input_devices:
            print("[error] No microphone input devices found.", flush=True)
            sys.exit(1)

        print("\nAvailable input devices:\n")
        for menu_number, (device_index, name, channels) in enumerate(input_devices, start=1):
            print(f"  [{menu_number}] Device {device_index}: {name} ({channels} channel(s))")

        while True:
            print()
            choice = input(f"Select input device [1-{len(input_devices)}]: ").strip()
            if not choice.isdigit():
                print("Please enter a number from the list.")
                continue

            menu_index = int(choice)
            if 1 <= menu_index <= len(input_devices):
                device_index, name, _ = input_devices[menu_index - 1]
                print(f"\nUsing input device: {name} (index {device_index})\n", flush=True)
                return device_index

            print(f"Please enter a number between 1 and {len(input_devices)}.")

    def __init__(self, device_index: int) -> None:
        self._device_index = device_index
        self._recognizer = sr.Recognizer()
        self._recognizer.pause_threshold = self.SPEECH_PAUSE_THRESHOLD
        self._recognizer.phrase_threshold = 0.3
        self._recognizer.non_speaking_duration = 0.4

        # Bind to the user-selected input device for the whole session.
        self._microphone = sr.Microphone(device_index=device_index)
        self._listening = False
        self._stop_event = threading.Event()
        self._stop_listener_handle: Optional[Callable[[], None]] = None
        self._stop_key_thread: Optional[threading.Thread] = None
        # Serialize simulated keystrokes from the speech-recognition callback thread.
        self._typing_lock = threading.Lock()
        self._last_speech_time: Optional[float] = None
        self._pause_period_emitted = False
        self._suppress_period_after_send = False
        self._dictation_halted = False
        self._freeze_signaled = False
        self._last_freeze_hint_time = 0.0
        self._pause_monitor_thread: Optional[threading.Thread] = None
        self._recognition_queue: PriorityQueue[RecognitionJob] = PriorityQueue()
        self._recognition_worker_thread: Optional[threading.Thread] = None
        self._recognition_job_counter = 0

        # Avoid pyautogui aborting if the mouse moves to a screen corner mid-session.
        pyautogui.FAILSAFE = False

    def _session_active(self) -> bool:
        """False after stop() — no further keystrokes or pastes should be simulated."""
        return not self._stop_event.is_set()

    def _with_typing_if_active(self, action: Callable[[], None]) -> None:
        """Run a pyautogui/paste action only while the session is active (not after ``q``)."""
        if not self._session_active():
            return
        with self._typing_lock:
            if not self._session_active():
                return
            action()

    def _interruptible_sleep(self, seconds: float) -> bool:
        """
        Sleep in small steps so stop() can cancel before typing resumes.

        Returns False if the session was stopped during the wait.
        """
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if not self._session_active():
                return False
            time.sleep(min(0.05, deadline - time.monotonic()))
        return self._session_active()

    def _type_rule_mention_if_active(self) -> None:
        """Paste the rule mention only while the session is still active."""

        def paste() -> None:
            text = self.VOICE_RULE_MENTION + " "
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
            if not self._session_active():
                return
            pyautogui.hotkey("command", "v")

        self._with_typing_if_active(paste)

    @classmethod
    def type_voice_rule_mention_at_cursor(cls) -> None:
        """
        Type ``@voice-input-confirmation.mds `` at the cursor.

        Uses paste (pbcopy + Cmd+V) so ``@`` is not dropped by pyautogui.write().
        """
        text = cls.VOICE_RULE_MENTION + " "
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        pyautogui.hotkey("command", "v")

    @classmethod
    def _wait_for_typing_box_click(cls, heading: str, instructions: list[str]) -> None:
        """Block until the user clicks (e.g. to focus the Cursor Agent typing box)."""
        cls._wait_for_typing_box_click_until_event(
            heading,
            instructions,
            done=threading.Event(),
        )

    @classmethod
    def _wait_for_typing_box_click_until_event(
        cls,
        heading: str,
        instructions: list[str],
        done: threading.Event,
    ) -> bool:
        """
        Block until the user clicks or ``done`` is set.

        Returns True if the user clicked; False if cancelled via ``done``.
        """
        from pynput import mouse

        clicked = threading.Event()

        def on_click(x: int, y: int, button: mouse.Button, pressed: bool) -> bool | None:
            if pressed:
                clicked.set()
                return False
            return None

        print()
        print("=" * 52)
        print(f"  {heading}")
        print("=" * 52)
        for line in instructions:
            print(f"  {line}")
        print("=" * 52)
        print()
        with mouse.Listener(on_click=on_click) as listener:
            while not clicked.is_set() and not done.is_set():
                clicked.wait(timeout=0.1)
            listener.stop()

        if done.is_set() and not clicked.is_set():
            return False

        # Let the clicked field take focus before typing.
        time.sleep(0.1)
        return True

    @classmethod
    def wait_for_typing_window_click_and_type_rule_mention(cls) -> None:
        """
        Wait for the user to click a typing window, then type the rule mention.

        The click indicates the target field (e.g. Cursor chat) has focus.
        """
        cls._wait_for_typing_box_click(
            heading="Next step",
            instructions=[
                "1. Open Cursor Agent (chat panel in Cursor).",
                "2. Click inside the message / typing box.",
                "3. Waiting for your click…",
            ],
        )
        cls.type_voice_rule_mention_at_cursor()
        print(f'Typed "{cls.VOICE_RULE_MENTION} " at cursor.\n', flush=True)

    def wait_for_resume_click_and_type_rule_mention(self) -> None:
        """After ``resume``: wait for click, type rule mention, then start dictation."""
        self._complete_resume_setup()

    def _try_emit_period_for_pause(self) -> bool:
        """
        Type ". " then Shift+Enter once for the current pause.

        Caller must hold ``_typing_lock``. Returns True if a period was typed.
        """
        if not self._session_active():
            return False

        if self._last_speech_time is None or self._pause_period_emitted:
            return False

        if self._suppress_period_after_send:
            return False

        if self._dictation_halted:
            return False

        if time.monotonic() - self._last_speech_time > self.PAUSE_PERIOD_AFTER:
            if not self._session_active():
                return False
            pyautogui.write(". ", interval=0.02)
            if not self._session_active():
                return False
            pyautogui.hotkey("shift", "enter")
            self._pause_period_emitted = True
            return True

        return False

    def _pause_monitor_loop(self) -> None:
        """
        Watch for trailing pauses with no new speech.

        Types ". " then Shift+Enter once when silence exceeds PAUSE_PERIOD_AFTER.
        """
        while not self._stop_event.is_set():
            time.sleep(0.1)
            with self._typing_lock:
                self._try_emit_period_for_pause()

    def _type_recognized_text(self, text: str) -> None:
        """
        Type recognized text at the cursor via simulated keystrokes.

        Short pauses (<= PAUSE_PERIOD_AFTER) join phrases with a space.
        Longer pauses emit ". " and Shift+Enter first (once), then the next phrase with no leading space.

        Requires Accessibility permission for Terminal in System Settings.
        """
        chunk = text.strip()
        if not chunk or not self._session_active():
            return

        if self._dictation_halted:
            return

        with self._typing_lock:
            if not self._session_active():
                return
            period_emitted = self._try_emit_period_for_pause()

            # Word space only for short pauses — never before ". "
            if self._last_speech_time is not None and not period_emitted and not self._pause_period_emitted:
                if time.monotonic() - self._last_speech_time <= self.PAUSE_PERIOD_AFTER:
                    chunk = " " + chunk

            if not self._session_active():
                return

            pyautogui.write(chunk, interval=0.02)
            if not self._session_active():
                return
            self._last_speech_time = time.monotonic()
            self._pause_period_emitted = False
            self._suppress_period_after_send = False

    def _audio_duration_seconds(self, audio: sr.AudioData) -> float:
        """Length of an audio chunk in seconds."""
        return len(audio.get_raw_data()) / (audio.sample_rate * audio.sample_width)

    def _recognition_priority(self, audio: sr.AudioData) -> int:
        """
        Short clips (likely single-word commands like send) get priority 0.

        Processed before longer dictation chunks waiting in the queue.
        """
        return 0 if self._audio_duration_seconds(audio) < 2.0 else 1

    def _enqueue_audio(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
        """Queue audio for transcription; short clips jump ahead for faster send response."""
        if not self._session_active():
            return
        self._recognition_job_counter += 1
        job: RecognitionJob = (
            self._recognition_priority(audio),
            self._recognition_job_counter,
            recognizer,
            audio,
        )
        self._recognition_queue.put(job)

    def _recognition_worker_loop(self) -> None:
        """Process queued audio; priority 0 jobs (short / send-like) run before longer phrases."""
        while not self._stop_event.is_set():
            try:
                _, _, recognizer, audio = self._recognition_queue.get(timeout=0.05)
            except Empty:
                continue
            if self._stop_event.is_set():
                self._recognition_queue.task_done()
                continue
            self._process_audio(recognizer, audio)
            self._recognition_queue.task_done()

    def _normalized_phrase(self, text: str) -> str:
        """Lowercase phrase with trailing punctuation removed for command matching."""
        return text.strip().lower().rstrip(".,!?")

    def _google_transcripts(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> list[str]:
        """
        Return transcript strings from Google Speech, best guess first.

        Uses ``show_all=True`` so homophones (e.g. presume for resume) appear in alternatives.
        """
        result = recognizer.recognize_google(audio, show_all=True)
        if isinstance(result, dict):
            transcripts: list[str] = []
            for alt in result.get("alternative", []):
                text = alt.get("transcript", "").strip()
                if text:
                    transcripts.append(text)
            return transcripts
        if isinstance(result, str) and result.strip():
            return [result.strip()]
        return []

    def _resume_match_tokens(self) -> frozenset[str]:
        return frozenset({self.RESUME_COMMAND, *self.RESUME_ALIASES})

    def _is_resume_command(self, text: str) -> bool:
        """True when the phrase is ``resume`` or a common mis-hearing of it."""
        normalized = self._normalized_phrase(text)
        tokens = self._resume_match_tokens()
        if normalized in tokens:
            return True
        words = normalized.split()
        return bool(words and words[0] in tokens)

    def _is_freeze_command(self, text: str) -> bool:
        """True when the phrase is exactly ``freeze`` (spoken after a pause)."""
        return self._normalized_phrase(text) == self.FREEZE_COMMAND

    def _is_send_command(self, text: str) -> bool:
        """
        True when the phrase is the word "send" spoken after a pause.

        SpeechRecognition only delivers a new phrase after silence, so a lone
        "send" is always post-pause. Phrases like "oh send" are not matched.
        """
        return self._normalized_phrase(text) == self.SEND_COMMAND

    def _handle_send_command(self) -> None:
        """
        Press Enter, wait, then type the Cursor rule mention.

        Does not type the word send. Suppresses a trailing ". " after send.
        """
        if not self._session_active():
            return

        with self._typing_lock:
            if not self._session_active():
                return
            pyautogui.press("enter")
            self._last_speech_time = time.monotonic()
            self._pause_period_emitted = True
            self._suppress_period_after_send = True

        if not self._interruptible_sleep(self.SEND_RULE_DELAY):
            return

        self._type_rule_mention_if_active()

    def _handle_freeze_command(self) -> None:
        """
        Freeze dictation after a pause. Mic stays active to listen for ``resume``.

        Does not type the word freeze.
        """
        self._dictation_halted = True
        self._freeze_signaled = True
        self._pause_period_emitted = True
        print(
            f'[freeze] Dictation frozen. Say "{self.RESUME_COMMAND}" to resume.',
            flush=True,
        )

    def _complete_resume_setup(self) -> None:
        """Wait for click, type rule mention, then enable dictation."""
        clicked = self._wait_for_typing_box_click_until_event(
            heading="Resume dictation",
            instructions=[
                "Click in the typing box.",
                "Waiting for your click…",
            ],
            done=self._stop_event,
        )
        if not clicked or not self._session_active():
            return

        self._type_rule_mention_if_active()
        if not self._session_active():
            return

        print(f'Typed "{self.VOICE_RULE_MENTION} " at cursor.\n', flush=True)

        self._dictation_halted = False
        self._last_speech_time = None
        self._pause_period_emitted = False
        self._suppress_period_after_send = False
        print("[resume] Ready — speak to dictate.\n", flush=True)

    def _handle_resume_command(self) -> None:
        """
        Resume dictation after ``freeze``. Ignored unless freeze was signaled first.

        Waits for a click, types the rule mention, then starts dictation. Does not type resume.
        """
        if not self._session_active():
            return

        if not self._freeze_signaled:
            print(
                f'[resume] Ignored — say "{self.FREEZE_COMMAND}" first to freeze dictation.',
                flush=True,
            )
            return

        self._freeze_signaled = False
        self._dictation_halted = True
        self._pause_period_emitted = False
        self._last_speech_time = None

        print("[resume] Click the typing box.\n", flush=True)
        threading.Thread(
            target=self._complete_resume_setup,
            name="resume-setup",
            daemon=True,
        ).start()

    def _maybe_print_freeze_hint(self, message: str) -> None:
        """Rate-limit hints while waiting for resume after freeze."""
        now = time.monotonic()
        if now - self._last_freeze_hint_time < 3.0:
            return
        self._last_freeze_hint_time = now
        print(message, flush=True)

    def _process_audio(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
        """
        Transcribe one captured chunk on a worker thread.

        Runs separately from the microphone listener so brief pauses do not block
        the next recording while Google Speech Recognition is working.
        """
        if self._stop_event.is_set():
            return

        # Resume click pending — ignore speech until click + rule mention complete.
        if self._dictation_halted and not self._freeze_signaled:
            return

        try:
            transcripts = self._google_transcripts(recognizer, audio)
            if not transcripts or not self._session_active():
                return

            # After freeze, scan every Google alternative for resume / presume.
            resume_candidates = transcripts if self._freeze_signaled else transcripts[:1]
            for text in resume_candidates:
                if self._is_resume_command(text):
                    if self._session_active():
                        self._handle_resume_command()
                    return

            text = transcripts[0]

            if not self._session_active():
                return

            if self._is_freeze_command(text):
                self._handle_freeze_command()
                return

            if self._dictation_halted:
                if self._freeze_signaled:
                    self._maybe_print_freeze_hint(
                        f'[freeze] Heard "{text.strip()}" — say "{self.RESUME_COMMAND}" '
                        "(or pause, then say it clearly) to resume."
                    )
                return

            if self._is_send_command(text):
                if self._session_active():
                    self._handle_send_command()
                return

            if self._session_active():
                self._type_recognized_text(text)
        except sr.UnknownValueError:
            if self._freeze_signaled:
                self._maybe_print_freeze_hint(
                    f'[freeze] Did not catch that — pause, then say "{self.RESUME_COMMAND}" clearly.'
                )
        except sr.RequestError as exc:
            print(f"[error] Speech service unavailable: {exc}", flush=True)
        except Exception as exc:
            print(f"[error] Could not type text at cursor: {exc}", flush=True)

    def _on_audio(self, recognizer: sr.Recognizer, audio: sr.AudioData) -> None:
        """
        Callback invoked for each captured audio chunk while listening.

        Returns immediately so speech_recognition can keep recording; transcription
        is queued on a priority worker (short clips first for faster send).
        """
        if self._stop_event.is_set():
            return

        self._enqueue_audio(recognizer, audio)

    def _wait_for_stop_key(self) -> None:
        """
        Block until the user presses the stop key.

        On macOS/Linux, reads a single key without requiring Enter (cbreak mode).
        On Windows, falls back to typing the stop key followed by Enter.
        """
        if sys.platform == "win32":
            while not self._stop_event.is_set():
                line = input()
                if line.strip().lower() == self.STOP_KEY:
                    self.stop()
                    break
            return

        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while not self._stop_event.is_set():
                char = sys.stdin.read(1)
                if char and char.lower() == self.STOP_KEY:
                    self.stop()
                    break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def stop(self) -> None:
        """
        Stop microphone capture and transcription.

        Safe to call more than once; subsequent calls are no-ops.
        """
        if not self._listening and self._stop_event.is_set():
            return

        self._stop_event.set()
        self._dictation_halted = True
        self._listening = False

        if self._stop_listener_handle is not None:
            self._stop_listener_handle(wait_for_stop=False)
            self._stop_listener_handle = None

        while not self._recognition_queue.empty():
            try:
                self._recognition_queue.get_nowait()
                self._recognition_queue.task_done()
            except Empty:
                break

        if self._recognition_worker_thread is not None:
            self._recognition_worker_thread.join(timeout=3.0)

        print("\n[stopped] Voice conversion ended.", flush=True)

    def listen_and_transcribe(self) -> None:
        """
        Continuously listen on the selected microphone and type transcripts at the cursor.

        Blocks until stop() is called (typically via the stop-key listener thread).
        Calibrates the microphone for ambient noise before starting.
        """
        self._stop_event.clear()
        self._listening = True
        self._last_speech_time = None
        self._pause_period_emitted = False
        self._suppress_period_after_send = False
        self._dictation_halted = False
        self._freeze_signaled = False
        self._last_freeze_hint_time = 0.0
        self._recognition_job_counter = 0
        while not self._recognition_queue.empty():
            try:
                self._recognition_queue.get_nowait()
                self._recognition_queue.task_done()
            except Empty:
                break

        self._recognition_worker_thread = threading.Thread(
            target=self._recognition_worker_loop,
            name="speech-recognition-worker",
            daemon=True,
        )
        self._recognition_worker_thread.start()

        # Brief calibration reduces false triggers from room noise.
        with self._microphone as source:
            print("Calibrating microphone for ambient noise…", flush=True)
            self._recognizer.adjust_for_ambient_noise(source, duration=1)
            # Lock threshold after calibration — dynamic adjustment during pauses
            # can stop the mic from picking speech back up.
            self._recognizer.dynamic_energy_threshold = False
            self._recognizer.energy_threshold = max(200, self._recognizer.energy_threshold * 0.85)

        print(
            "Listening… place your cursor in the target app, then speak.\n"
            f'  Pause > {self.PAUSE_PERIOD_AFTER:.0f} s → ". " then Shift+Enter\n'
            f'  Say "{self.SEND_COMMAND}" after a pause → Enter, then {self.VOICE_RULE_MENTION}\n'
            f'  Say "{self.FREEZE_COMMAND}" after a pause → freeze; then "{self.RESUME_COMMAND}" → resume\n',
            flush=True,
        )

        self._pause_monitor_thread = threading.Thread(
            target=self._pause_monitor_loop,
            name="pause-punctuation-monitor",
            daemon=True,
        )
        self._pause_monitor_thread.start()

        # Background thread watches for the stop key while audio runs.
        self._stop_key_thread = threading.Thread(
            target=self._wait_for_stop_key,
            name="stop-key-listener",
            daemon=True,
        )
        self._stop_key_thread.start()

        # listen_in_background returns a callable that stops the worker thread.
        self._stop_listener_handle = self._recognizer.listen_in_background(
            self._microphone,
            self._on_audio,
            phrase_time_limit=10,
        )

        # Keep the main thread alive until the user stops conversion.
        self._stop_event.wait()

        if self._stop_key_thread is not None:
            self._stop_key_thread.join(timeout=1)

        if self._pause_monitor_thread is not None:
            self._pause_monitor_thread.join(timeout=1)

        if self._recognition_worker_thread is not None:
            self._recognition_worker_thread.join(timeout=2)
