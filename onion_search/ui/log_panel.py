"""
Log panel UI component with color-tagged message history and keyword filtering.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext


class LogPanel(ttk.Frame):
    """Encapsulates the scrolled log area, tag color stylings, and filter toggles."""

    def __init__(self, parent):
        super().__init__(parent)
        self.filtered_log_var = tk.BooleanVar(value=False)
        self._build_ui()

    def _build_ui(self):
        log_header = ttk.Frame(self)
        log_header.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(log_header, text="Log:").pack(side=tk.LEFT)
        ttk.Checkbutton(
            log_header, text="Szűrt", variable=self.filtered_log_var
        ).pack(side=tk.LEFT, padx=8)
        ttk.Button(
            log_header, text="Törlés", command=self.clear, width=6
        ).pack(side=tk.RIGHT)

        self.log_text = scrolledtext.ScrolledText(
            self, height=9, font=("Consolas", 8)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.log_text.tag_config("ok", foreground="#1e8449", background="#eafaf1")
        self.log_text.tag_config("clone", foreground="#b9770e", background="#fef5e7")
        self.log_text.tag_config("dead", foreground="#922b21", background="#fdedec")
        self.log_text.tag_config(
            "newnym",
            foreground="#1a5276",
            background="#d6eaf8",
            font=("Consolas", 8, "bold"),
        )
        self.log_text.tag_config("filter", foreground="#6c3483", background="#f4ecf7")
        self.log_text.tag_config(
            "tor_ok",
            foreground="#0e6655",
            background="#d5f5e3",
            font=("Consolas", 8, "bold"),
        )
        self.log_text.tag_config(
            "tor_err",
            foreground="white",
            background="#e74c3c",
            font=("Consolas", 8, "bold"),
        )
        self.log_text.tag_config("save", foreground="#7d6608", background="#fef9e7")
        self.log_text.tag_config(
            "error",
            foreground="white",
            background="#c0392b",
            font=("Consolas", 8, "bold"),
        )
        self.log_text.tag_config(
            "start",
            foreground="#1a5276",
            background="#d6eaf8",
            font=("Consolas", 8, "bold"),
        )

    def clear(self):
        self.log_text.delete("1.0", tk.END)

    def log_msg(self, msg, force=False, tag=None):
        """Append log message thread-safely with tags and optional filtering."""
        if not force and self.filtered_log_var.get():
            keep_keywords = (
                "[OK]",
                "[CLONE]",
                "[NEWNYM]",
                "[SAVE",
                "[LOAD",
                "[TOR",
                "HIBA",
                "MIGRATE",
                "COUNTER",
                "[FILTER",
                "[PRECISE",
            )
            if not any(k in msg for k in keep_keywords):
                return
        if tag is None:
            if "[OK]" in msg:
                tag = "ok"
            elif "[CLONE]" in msg:
                tag = "clone"
            elif "HALOTT" in msg or "[DEAD]" in msg:
                tag = "dead"
            elif "[NEWNYM]" in msg:
                tag = "newnym"
            elif "FILTER" in msg or "PRECISE" in msg:
                tag = "filter"
            elif "TOR" in msg and "OK" in msg:
                tag = "tor_ok"
            elif "TOR" in msg or "HIBA" in msg:
                tag = "tor_err"
            elif "SAVE" in msg or "LOAD" in msg:
                tag = "save"
            elif "START" in msg:
                tag = "start"

        def _append():
            self.log_text.insert(tk.END, msg + "\n", tag if tag else "")
            self.log_text.see(tk.END)

        self.after(0, _append)
