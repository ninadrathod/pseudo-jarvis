"""Voice session flow for the pseudo-jarvis GUI."""

from collections.abc import Callable
from typing import Optional

from app.voice_to_text import VoiceToText


def print_session_header() -> None:
    """Banner and command hints shown in the GUI session log."""
    rule_mention = VoiceToText.VOICE_RULE_MENTION

    print("=" * 52)
    print("  pseudo-jarvis — real-time voice to text")
    print("=" * 52)
    print()
    print("  Listening — speak in Cursor Agent.")
    print('  Pause > 2 s → ". " then Shift+Enter.')
    print(f'  Say "{VoiceToText.SEND_COMMAND}" after a pause → Enter, then {rule_mention} ')
    print(
        f'  Say "{VoiceToText.FREEZE_COMMAND}" after a pause → freeze; '
        f'"{VoiceToText.RESUME_COMMAND}" → resume'
    )
    print("  To stop, press the Stop button in this window.")
    print()


def run_session(
    device_index: int,
    *,
    on_converter_ready: Optional[Callable[[VoiceToText], None]] = None,
) -> None:
    """
    Run one voice session: click-to-focus → rule mention → listen until GUI Stop.

    Parameters
    ----------
    device_index:
        PyAudio input device index from :meth:`VoiceToText.list_input_devices`.
    on_converter_ready:
        Callback invoked with the ``VoiceToText`` instance before
        ``listen_and_transcribe`` blocks — used by the GUI to wire Stop.
    """
    device_name = next(
        (name for idx, name, _ in VoiceToText.list_input_devices() if idx == device_index),
        f"device {device_index}",
    )
    print(f"Using input device: {device_name} (index {device_index})\n", flush=True)

    VoiceToText.wait_for_typing_window_click_and_type_rule_mention()
    print_session_header()

    converter = VoiceToText(device_index=device_index)
    if on_converter_ready is not None:
        on_converter_ready(converter)

    converter.listen_and_transcribe()
