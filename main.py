"""Entry point for pseudo-jarvis voice-to-text conversion."""

from app.voice_to_text import VoiceToText


def main() -> None:
    stop_key = VoiceToText.STOP_KEY
    rule_mention = VoiceToText.VOICE_RULE_MENTION

    print("=" * 52)
    print("  pseudo-jarvis — real-time voice to text")
    print("=" * 52)
    print()

    device_index = VoiceToText.select_input_device()
    VoiceToText.wait_for_typing_window_click_and_type_rule_mention()

    print("  Listening — speak in Cursor Agent.")
    print('  Pause > 2 s → ". " then Shift+Enter.')
    print(f'  Say "{VoiceToText.SEND_COMMAND}" after a pause → Enter, then {rule_mention} ')
    print(f'  Say "{VoiceToText.FREEZE_COMMAND}" after a pause → freeze; "{VoiceToText.RESUME_COMMAND}" → resume')
    print(f'  To stop, switch to Terminal and press "{stop_key}".')
    print()

    converter = VoiceToText(device_index=device_index)
    converter.listen_and_transcribe()


if __name__ == "__main__":
    main()
