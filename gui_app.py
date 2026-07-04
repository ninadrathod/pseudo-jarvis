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
    "Subscribe each Cursor project once below — only added roots receive the voice rule."
)

# Light theme palette
BG = "#f4f6f9"
SURFACE = "#ffffff"
SURFACE_2 = "#eef1f6"
BORDER = "#c8d0dc"
TEXT = "#15202b"
MUTED = "#5a6573"
ACCENT = "#0077b6"
ACCENT_HOVER = "#0096c7"
ACCENT_FG = "#ffffff"
SECTION = "#0f4c6e"
GREEN = "#1b8a4a"
RED = "#c0392b"
RED_BG = "#fdecea"

FONT_UI = ("SF Pro Text", 14)
FONT_UI_BOLD = ("SF Pro Text", 14, "bold")
FONT_UI_SM = ("SF Pro Text", 13, "bold")
FONT_TITLE = ("SF Pro Display", 26, "bold")
FONT_SUB = ("SF Pro Text", 14)
FONT_STATUS = ("SF Pro Text", 14, "bold")
FONT_MONO = ("SF Mono", 13)
FONT_MONO_SM = ("SF Mono", 12)


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
        self.root.configure(bg=BG)
        self.root.minsize(680, 760)

        self._log_queue: queue.Queue[str] = queue.Queue()
        self._converter: Optional[VoiceToText] = None
        self._session_thread: Optional[threading.Thread] = None
        self._devices = VoiceToText.list_input_devices()
        self._projects_expanded = False
        self._listening = False

        self._setup_theme()
        self._build_ui()
        self._poll_log_queue()

    def _setup_theme(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=BG, foreground=TEXT, font=FONT_UI)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=SURFACE)
        style.configure(
            "Card.TLabelframe",
            background=SURFACE,
            foreground=SECTION,
            bordercolor=BORDER,
            relief="flat",
            borderwidth=1,
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=SURFACE,
            foreground=SECTION,
            font=("SF Pro Text", 13, "bold"),
        )
        style.configure("TLabel", background=BG, foreground=TEXT, font=FONT_UI)
        style.configure("Card.TLabel", background=SURFACE, foreground=TEXT, font=FONT_UI)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=FONT_UI_BOLD)
        style.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED, font=FONT_UI_SM)
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=FONT_TITLE)
        style.configure("Sub.TLabel", background=BG, foreground=MUTED, font=FONT_SUB)
        style.configure("Status.TLabel", background=BG, foreground=MUTED, font=FONT_STATUS)

        style.configure(
            "TEntry",
            fieldbackground=SURFACE,
            foreground=TEXT,
            insertcolor=ACCENT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            font=FONT_UI,
        )
        style.configure(
            "TCombobox",
            fieldbackground=SURFACE,
            foreground=TEXT,
            background=SURFACE,
            arrowcolor=ACCENT,
            bordercolor=BORDER,
            font=FONT_UI,
        )
        style.map("TCombobox", fieldbackground=[("readonly", SURFACE)])

        style.configure(
            "TButton",
            background=SURFACE_2,
            foreground=TEXT,
            bordercolor=BORDER,
            focusthickness=0,
            padding=(16, 10),
            font=FONT_UI_BOLD,
        )
        style.map(
            "TButton",
            background=[("active", BORDER), ("disabled", SURFACE_2)],
            foreground=[("disabled", MUTED)],
        )
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground=ACCENT_FG,
            font=("SF Pro Text", 15, "bold"),
            padding=(22, 12),
        )
        style.map(
            "Accent.TButton",
            background=[("active", ACCENT_HOVER), ("disabled", SURFACE_2)],
            foreground=[("disabled", MUTED)],
        )
        style.configure(
            "Danger.TButton",
            background=RED_BG,
            foreground=RED,
            font=("SF Pro Text", 15, "bold"),
            padding=(22, 12),
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#f9d6d2"), ("disabled", SURFACE_2)],
            foreground=[("disabled", MUTED)],
        )
        style.configure(
            "Ghost.TButton",
            background=SURFACE,
            foreground=ACCENT,
            font=FONT_UI_BOLD,
            padding=(12, 8),
        )
        style.map("Ghost.TButton", background=[("active", SURFACE_2)])

        style.configure("TSeparator", background=BORDER)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=(20, 16, 20, 16))
        outer.pack(fill="both", expand=True)

        # Header
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 16))

        title_block = ttk.Frame(header)
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(title_block, text="pseudo-jarvis", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_block,
            text="Voice → Cursor Agent · macOS",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        status_frame = ttk.Frame(header)
        status_frame.pack(side="right", anchor="ne")
        self._status_dot = tk.Label(
            status_frame,
            text="●",
            fg=MUTED,
            bg=BG,
            font=("SF Pro Text", 18, "bold"),
        )
        self._status_dot.pack(side="left")
        self._status_label = ttk.Label(status_frame, text="Idle", style="Status.TLabel")
        self._status_label.pack(side="left", padx=(4, 0))

        ttk.Label(outer, text=STARTUP_HINT, style="Muted.TLabel", wraplength=580).pack(
            anchor="w", pady=(0, 12)
        )

        # Projects
        projects_card = ttk.LabelFrame(outer, text="  Projects  ", style="Card.TLabelframe", padding=16)
        projects_card.pack(fill="x", pady=(0, 10))

        self._projects_toggle_btn = ttk.Button(
            projects_card,
            text="▸  Subscribed projects",
            style="Ghost.TButton",
            command=self._toggle_projects_list,
        )
        self._projects_toggle_btn.pack(anchor="w")

        self._projects_frame = ttk.Frame(projects_card, style="Card.TFrame")
        self._projects_list = tk.Listbox(
            self._projects_frame,
            height=4,
            font=FONT_MONO,
            bg=SURFACE,
            fg=TEXT,
            selectbackground=ACCENT,
            selectforeground=ACCENT_FG,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            borderwidth=0,
            activestyle="none",
        )
        self._projects_list.pack(fill="x", expand=True, pady=(8, 0))
        self._refresh_projects_list()

        folder_row = ttk.Frame(projects_card, style="Card.TFrame")
        folder_row.pack(fill="x", pady=(12, 0))

        ttk.Label(folder_row, text="Project root", style="CardMuted.TLabel").pack(anchor="w")
        entry_row = ttk.Frame(folder_row, style="Card.TFrame")
        entry_row.pack(fill="x", pady=(4, 0))

        self._folder_var = tk.StringVar()
        ttk.Entry(entry_row, textvariable=self._folder_var).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        ttk.Button(entry_row, text="Browse", command=self._browse_folder).pack(side="left", padx=(0, 6))
        ttk.Button(entry_row, text="Add project", command=self._on_add_project).pack(side="left")

        ttk.Separator(outer, orient="horizontal").pack(fill="x", pady=14)

        # Voice session
        session_card = ttk.LabelFrame(outer, text="  Voice session  ", style="Card.TLabelframe", padding=16)
        session_card.pack(fill="x", pady=(0, 10))

        mic_row = ttk.Frame(session_card, style="Card.TFrame")
        mic_row.pack(fill="x")

        ttk.Label(mic_row, text="Microphone", style="CardMuted.TLabel").pack(anchor="w")
        self._mic_var = tk.StringVar()
        self._mic_combo = ttk.Combobox(
            mic_row,
            textvariable=self._mic_var,
            state="readonly" if self._devices else "disabled",
        )
        self._mic_combo.pack(fill="x", pady=(4, 12))

        labels = [f"{name}  ·  device {idx}" for idx, name, _ in self._devices]
        self._mic_combo["values"] = labels
        if labels:
            self._mic_combo.current(0)

        btn_row = ttk.Frame(session_card, style="Card.TFrame")
        btn_row.pack(fill="x")

        self._start_btn = ttk.Button(
            btn_row,
            text="Start listening",
            style="Accent.TButton",
            command=self._on_start,
        )
        self._start_btn.pack(side="left")

        self._stop_btn = ttk.Button(
            btn_row,
            text="Stop",
            style="Danger.TButton",
            command=self._on_stop,
            state="disabled",
        )
        self._stop_btn.pack(side="left", padx=(10, 0))

        # Log
        log_header = ttk.Frame(outer)
        log_header.pack(fill="x", pady=(4, 6))
        ttk.Label(log_header, text="Session log", style="Muted.TLabel").pack(side="left")

        log_frame = tk.Frame(outer, bg=BORDER, padx=1, pady=1)
        log_frame.pack(fill="both", expand=True)

        self._log = scrolledtext.ScrolledText(
            log_frame,
            wrap="word",
            font=FONT_MONO,
            state="disabled",
            bg=SURFACE,
            fg=TEXT,
            insertbackground=ACCENT,
            selectbackground=ACCENT,
            selectforeground=ACCENT_FG,
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=10,
        )
        self._log.pack(fill="both", expand=True)

        if not self._devices:
            self._append_log("[error] No microphone input devices found.\n")
            self._start_btn.config(state="disabled")

    def _set_status(self, listening: bool) -> None:
        self._listening = listening
        if listening:
            self._status_dot.config(fg=GREEN)
            self._status_label.config(text="Listening")
        else:
            self._status_dot.config(fg=MUTED)
            self._status_label.config(text="Idle")

    def _toggle_projects_list(self) -> None:
        self._projects_expanded = not self._projects_expanded
        if self._projects_expanded:
            self._projects_toggle_btn.config(text="▾  Subscribed projects")
            self._refresh_projects_list()
            self._projects_frame.pack(fill="x", pady=(8, 0))
        else:
            self._projects_toggle_btn.config(text="▸  Subscribed projects")
            self._projects_frame.pack_forget()

    def _refresh_projects_list(self) -> None:
        self._projects_list.delete(0, tk.END)
        try:
            projects = list_subscribed_projects()
        except FileNotFoundError as exc:
            self._projects_list.insert(tk.END, f"(setup required: {exc})")
            return
        if not projects:
            self._projects_list.insert(tk.END, "(no projects yet — add one above)")
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

        self._set_status(True)
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
        self._set_status(False)
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
    # Retina-friendly default size
    root.geometry("700x780")
    PseudoJarvisGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
