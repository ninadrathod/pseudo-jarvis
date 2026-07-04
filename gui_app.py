#!/usr/bin/env python3
"""
Minimal macOS GUI for pseudo-jarvis.

Start → mic → click typing box → rule mention → listen.
Stop  → :meth:`VoiceToText.stop` via the Stop button.
Output → mirrors session ``print()`` in the log pane.
"""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import IO, Optional

from app.project_registry import (
    VOICE_RULE_FILENAME,
    add_subscribed_project,
    list_subscribed_projects,
)
from app.session import run_session
from app.voice_to_text import VoiceToText

STARTUP_HINT = (
    "To use pseudo-jarvis with a Cursor project, add that project's root folder "
    "below. Only subscribed projects receive the voice rule and appear in your list."
)


class QueueLogWriter:
    """Redirect ``print()`` to a thread-safe queue for the GUI log pane."""

    def __init__(self, log_queue: queue.Queue[str], fallback: IO[str]) -> None:
        self._queue = log_queue
        self._fallback = fallback

    def write(self, text: str) -> int:
        if text:
            self._queue.put(text)
        return len(text)

    def flush(self) -> None:
        pass


class PseudoJarvisGui:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("pseudo-jarvis")
        self.root.minsize(560, 560)

        self._log_queue: queue.Queue[str] = queue.Queue()
        self._converter: Optional[VoiceToText] = None
        self._session_thread: Optional[threading.Thread] = None
        self._devices = VoiceToText.list_input_devices()
        self._projects_expanded = False

        self._build_ui()
        self._poll_log_queue()
        self._show_startup_hint()

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        self._projects_toggle_btn = ttk.Button(
            self.root,
            text="▶ Subscribed projects",
            command=self._toggle_projects_list,
        )
        self._projects_toggle_btn.pack(anchor="w", **pad)

        self._projects_frame = ttk.Frame(self.root)
        self._projects_list = tk.Listbox(
            self._projects_frame,
            height=4,
            font=("Menlo", 10),
            activestyle="none",
        )
        self._projects_list.pack(fill="x", expand=True)
        self._refresh_projects_list()

        hint = ttk.Label(
            self.root,
            text=STARTUP_HINT,
            wraplength=520,
            foreground="#555555",
        )
        hint.pack(anchor="w", **pad)

        add_frame = ttk.LabelFrame(self.root, text="Add project to pseudo-jarvis", padding=10)
        add_frame.pack(fill="x", padx=12, pady=(0, 6))

        folder_row = ttk.Frame(add_frame)
        folder_row.pack(fill="x")

        ttk.Label(folder_row, text="Project root:").pack(side="left")
        self._folder_var = tk.StringVar()
        ttk.Entry(folder_row, textvariable=self._folder_var).pack(
            side="left", fill="x", expand=True, padx=(8, 8)
        )
        ttk.Button(folder_row, text="Browse…", command=self._browse_folder).pack(side="left")
        ttk.Button(add_frame, text="ADD", command=self._on_add_project).pack(anchor="e", pady=(8, 0))

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=12, pady=8)

        header = ttk.Label(
            self.root,
            text="Voice session · Cursor Agent",
            font=("Segoe UI", 13, "bold"),
        )
        header.pack(anchor="w", **pad)

        mic_row = ttk.Frame(self.root)
        mic_row.pack(fill="x", **pad)

        ttk.Label(mic_row, text="Microphone:").pack(side="left")
        self._mic_var = tk.StringVar()
        self._mic_combo = ttk.Combobox(
            mic_row,
            textvariable=self._mic_var,
            state="readonly" if self._devices else "disabled",
            width=48,
        )
        self._mic_combo.pack(side="left", padx=(8, 0), fill="x", expand=True)

        labels = [f"{name} (device {idx})" for idx, name, _ in self._devices]
        self._mic_combo["values"] = labels
        if labels:
            self._mic_combo.current(0)

        btn_row = ttk.Frame(self.root)
        btn_row.pack(fill="x", **pad)

        self._start_btn = ttk.Button(btn_row, text="Start", command=self._on_start)
        self._start_btn.pack(side="left")

        self._stop_btn = ttk.Button(
            btn_row,
            text="Stop",
            command=self._on_stop,
            state="disabled",
        )
        self._stop_btn.pack(side="left", padx=(8, 0))

        ttk.Label(self.root, text="Session log:").pack(anchor="w", padx=12)

        self._log = scrolledtext.ScrolledText(
            self.root,
            wrap="word",
            font=("Menlo", 11),
            state="disabled",
            height=14,
        )
        self._log.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        if not self._devices:
            self._append_log("[error] No microphone input devices found.\n")
            self._start_btn.config(state="disabled")

    def _show_startup_hint(self) -> None:
        messagebox.showinfo("pseudo-jarvis", STARTUP_HINT)

    def _toggle_projects_list(self) -> None:
        self._projects_expanded = not self._projects_expanded
        if self._projects_expanded:
            self._projects_toggle_btn.config(text="▼ Subscribed projects")
            self._refresh_projects_list()
            self._projects_frame.pack(fill="x", padx=12, pady=(0, 6), after=self._projects_toggle_btn)
        else:
            self._projects_toggle_btn.config(text="▶ Subscribed projects")
            self._projects_frame.pack_forget()

    def _refresh_projects_list(self) -> None:
        self._projects_list.delete(0, tk.END)
        try:
            projects = list_subscribed_projects()
        except FileNotFoundError as exc:
            self._projects_list.insert(tk.END, f"(setup required: {exc})")
            return
        if not projects:
            self._projects_list.insert(tk.END, "(no projects yet — use ADD below)")
            return
        for path in projects:
            self._projects_list.insert(tk.END, path)

    def _browse_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select project root folder")
        if folder:
            self._folder_var.set(folder)

    def _on_add_project(self) -> None:
        folder = self._folder_var.get().strip()
        if not folder:
            messagebox.showwarning("Add project", "Select a project root folder first.")
            return

        try:
            normalized, already = add_subscribed_project(Path(folder))
        except FileNotFoundError as exc:
            messagebox.showerror("Add project", str(exc))
            return
        except OSError as exc:
            messagebox.showerror("Add project", f"Could not add project:\n{exc}")
            return

        self._refresh_projects_list()
        if not self._projects_expanded:
            self._toggle_projects_list()

        if already:
            messagebox.showinfo(
                "Add project",
                f"Project already subscribed; {VOICE_RULE_FILENAME} refreshed.\n\n{normalized}",
            )
        else:
            messagebox.showinfo(
                "Add project",
                f"Added project and installed {VOICE_RULE_FILENAME}.\n\n{normalized}",
            )
        self._append_log(f"[project] Subscribed: {normalized}\n")

    def _append_log(self, text: str) -> None:
        self._log.config(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.config(state="disabled")

    def _poll_log_queue(self) -> None:
        while True:
            try:
                chunk = self._log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(chunk)
        self.root.after(80, self._poll_log_queue)

    def _selected_device_index(self) -> int:
        idx = self._mic_combo.current()
        if idx < 0:
            idx = 0
        return self._devices[idx][0]

    def _on_start(self) -> None:
        if self._session_thread and self._session_thread.is_alive():
            return

        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._mic_combo.config(state="disabled")

        device_index = self._selected_device_index()
        self._session_thread = threading.Thread(
            target=self._run_session,
            args=(device_index,),
            name="voice-session",
            daemon=True,
        )
        self._session_thread.start()

    def _run_session(self, device_index: int) -> None:
        writer = QueueLogWriter(self._log_queue, sys.__stdout__)
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = writer  # type: ignore[assignment]

        try:
            run_session(
                device_index,
                on_converter_ready=self._bind_converter,
            )
        except Exception as exc:
            print(f"[error] Session failed: {exc}", flush=True)
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
            self.root.after(0, self._on_session_ended)

    def _bind_converter(self, converter: VoiceToText) -> None:
        self._converter = converter

    def _on_stop(self) -> None:
        if self._converter is not None:
            self._converter.stop()

    def _on_session_ended(self) -> None:
        self._converter = None
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._mic_combo.config(state="readonly" if self._devices else "disabled")


def main() -> None:
    if sys.platform != "darwin":
        messagebox.showerror(
            "pseudo-jarvis",
            "This GUI targets macOS only (same as the voice engine).",
        )
        sys.exit(1)

    root = tk.Tk()
    PseudoJarvisGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
