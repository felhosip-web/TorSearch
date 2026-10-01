"""
Log panel UI component with search filtering, category tabs, and color-tagged message history.
Integrates standard Python logging module via TkLogHandler.
"""
import logging
import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import List, Optional, Tuple

logger = logging.getLogger("onion_search")


class TkLogHandler(logging.Handler):
    """Custom logging.Handler that directs standard Python log records into LogPanel."""

    def __init__(self, log_panel: "LogPanel") -> None:
        super().__init__()
        self.log_panel = log_panel

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            tag = getattr(record, "tag", None)
            if tag is None:
                if record.levelno >= logging.ERROR:
                    tag = "error"
                elif record.levelno >= logging.WARNING:
                    tag = "tor_err"
                elif "[OK]" in msg:
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
                elif "SAVE" in msg or "LOAD" in msg:
                    tag = "save"
                elif "START" in msg:
                    tag = "start"

            self.log_panel.log_msg(msg, force=True, tag=tag)
        except Exception:
            self.handleError(record)


class LogPanel(ttk.Frame):
    """Encapsulates the scrolled log area, text search, category buttons, and tag stylings."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.filtered_log_var = tk.BooleanVar(value=False)
        self.search_var = tk.StringVar(value="")
        self.category_var = tk.StringVar(value="all")  # all, ok, error, newnym, tor
        self.log_history: List[Tuple[str, Optional[str]]] = []  # List of tuples: (msg, tag)
        self._build_ui()
        self._setup_traces()
        self._setup_logging_handler()

    def _setup_logging_handler(self) -> None:
        """Attach TkLogHandler to 'onion_search' logger."""
        self.handler = TkLogHandler(self)
        formatter = logging.Formatter("%(message)s")
        self.handler.setFormatter(formatter)
        logger.addHandler(self.handler)
        logger.setLevel(logging.INFO)

    def _build_ui(self) -> None:
        # 1. Log Toolbar
        log_header = ttk.Frame(self)
        log_header.pack(fill=tk.X, pady=(4, 2))

        ttk.Label(log_header, text="Log:").pack(side=tk.LEFT)

        # Search field
        ttk.Label(log_header, text="Keresés:").pack(side=tk.LEFT, padx=(6, 2))
        self.search_entry = ttk.Entry(log_header, textvariable=self.search_var, width=14)
        self.search_entry.pack(side=tk.LEFT, padx=2)

        # Category buttons
        btn_box = ttk.Frame(log_header)
        btn_box.pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(btn_box, text="Mind", variable=self.category_var, value="all", command=self.refresh_view).pack(side=tk.LEFT, padx=1)
        ttk.Radiobutton(btn_box, text="Csak [OK]", variable=self.category_var, value="ok", command=self.refresh_view).pack(side=tk.LEFT, padx=1)
        ttk.Radiobutton(btn_box, text="Csak hibák", variable=self.category_var, value="error", command=self.refresh_view).pack(side=tk.LEFT, padx=1)
        ttk.Radiobutton(btn_box, text="NEWNYM", variable=self.category_var, value="newnym", command=self.refresh_view).pack(side=tk.LEFT, padx=1)
        ttk.Radiobutton(btn_box, text="Tor", variable=self.category_var, value="tor", command=self.refresh_view).pack(side=tk.LEFT, padx=1)

        ttk.Checkbutton(
            log_header, text="Szűrt", variable=self.filtered_log_var, command=self.refresh_view
        ).pack(side=tk.LEFT, padx=4)

        ttk.Button(
            log_header, text="Törlés", command=self.clear, width=6
        ).pack(side=tk.RIGHT)

        # 2. Text widget
        self.log_text = scrolledtext.ScrolledText(
            self, height=9, font=("Consolas", 8)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.apply_tag_styles()

    def apply_tag_styles(self, dark_mode: bool = False) -> None:
        """Configure color schemes for log tags in light or dark mode."""
        if dark_mode:
            self.log_text.tag_config("ok", foreground="#a6e3a1", background="#18342b")
            self.log_text.tag_config("clone", foreground="#f9e2af", background="#332a1c")
            self.log_text.tag_config("dead", foreground="#f38ba8", background="#3b1d24")
            self.log_text.tag_config(
                "newnym",
                foreground="#89b4fa",
                background="#1e293b",
                font=("Consolas", 8, "bold"),
            )
            self.log_text.tag_config("filter", foreground="#cba6f7", background="#2a1f3d")
            self.log_text.tag_config(
                "tor_ok",
                foreground="#94e2d5",
                background="#142c26",
                font=("Consolas", 8, "bold"),
            )
            self.log_text.tag_config(
                "tor_err",
                foreground="#f38ba8",
                background="#451a1a",
                font=("Consolas", 8, "bold"),
            )
            self.log_text.tag_config("save", foreground="#f9e2af", background="#2b2615")
            self.log_text.tag_config(
                "error",
                foreground="#f38ba8",
                background="#4c1d1d",
                font=("Consolas", 8, "bold"),
            )
            self.log_text.tag_config(
                "start",
                foreground="#89dceb",
                background="#172b36",
                font=("Consolas", 8, "bold"),
            )
        else:
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

    def _setup_traces(self) -> None:
        def _on_search(*args) -> None:
            self.refresh_view()

        try:
            self.search_var.trace_add("write", _on_search)
        except Exception:
            pass

    def clear(self) -> None:
        self.log_history.clear()
        self.log_text.delete("1.0", tk.END)

    def _matches_filters(self, msg: str, tag: Optional[str]) -> bool:
        # 1. Search filter
        query = self.search_var.get().strip().lower()
        if query and query not in msg.lower():
            return False

        # 2. Category button filter
        cat = self.category_var.get()
        if cat == "ok" and tag not in ("ok",):
            return False
        if cat == "error" and tag not in ("error", "dead", "tor_err"):
            return False
        if cat == "newnym" and tag != "newnym":
            return False
        if cat == "tor" and tag not in ("tor_ok", "tor_err"):
            return False

        # 3. Checkbox "Szűrt"
        if self.filtered_log_var.get():
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
                return False

        return True

    def refresh_view(self) -> None:
        """Re-render visible log messages from in-memory history matching active filters."""
        self.log_text.delete("1.0", tk.END)
        for msg, tag in self.log_history:
            if self._matches_filters(msg, tag):
                self.log_text.insert(tk.END, msg + "\n", tag if tag else "")
        self.log_text.see(tk.END)

    def log_msg(self, msg: str, force: bool = False, tag: Optional[str] = None) -> None:
        """Append log message thread-safely with tags and history buffer."""
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

        self.log_history.append((msg, tag))
        if len(self.log_history) > 5000:
            self.log_history.pop(0)

        if self._matches_filters(msg, tag):
            def _append():
                self.log_text.insert(tk.END, msg + "\n", tag if tag else "")
                self.log_text.see(tk.END)

            self.after(0, _append)
