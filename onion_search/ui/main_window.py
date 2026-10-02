"""
Main application window coordinating UI components, search lifecycle, persistence, and UX features.
Integrates standard logging, ConfigManager persistence, and constants configuration.
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import json
import logging
import os
from pathlib import Path
import random
import re
import sqlite3
import subprocess
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from onion_search.config import (
    AppConfig,
    ConfigManager,
    DB_FILE,
    MAX_MEMORY_CACHE_SIZE,
    MIN_NEWNYM_INTERVAL_AUTO,
    MIN_NEWNYM_INTERVAL_TRIGGER,
    STATE_DIR,
    TIMEOUT_GET,
)
from onion_search.core.detector import ContentDetector
from onion_search.core.fetcher import OnionFetcher
from onion_search.core.neonym import TorController
from onion_search.storage.json_backend import JSONBackend
from onion_search.storage.sqlite_backend import SQLiteBackend
from onion_search.ui.filters import FilterPanel
from onion_search.ui.log_panel import LogPanel, logger
from onion_search.utils.helpers import fmt_ts


class MainWindow:
    """Main window for Onion Kereso with enhanced UI/UX capabilities."""

    def __init__(
        self,
        root: tk.Tk,
        fetcher: Optional[OnionFetcher] = None,
        detector: Optional[ContentDetector] = None,
        tor_controller: Optional[TorController] = None,
        sqlite_backend: Optional[SQLiteBackend] = None,
        json_backend: Optional[JSONBackend] = None,
        config_manager: Optional[ConfigManager] = None,
    ) -> None:
        self.root: tk.Tk = root
        self.root.title("Onion Kereso v4.8 - secure & stable")
        self.root.geometry("1400x940")

        # Configuration manager
        self.config_manager: ConfigManager = config_manager or ConfigManager()
        cfg: AppConfig = self.config_manager.config

        # Injected dependencies with default fallback
        self.detector: ContentDetector = detector or ContentDetector()
        self.sqlite_backend: SQLiteBackend = sqlite_backend or SQLiteBackend()
        self.json_backend: JSONBackend = json_backend or JSONBackend()
        self.fetcher: OnionFetcher = fetcher or OnionFetcher(detector=self.detector)
        self.tor_controller: TorController = tor_controller or TorController(
            on_sessions_reset=self.fetcher.session_manager.close_all
        )

        # In-memory application state
        self.seen_fp: OrderedDict[str, str] = OrderedDict()
        self.seen_btc: OrderedDict[str, str] = OrderedDict()
        self.checked_urls: Set[str] = set()
        self.in_progress_urls: Set[str] = set()
        self.pending_queue: List[str] = []  # Remaining unvisited URLs for clean resume
        self.dead_blacklist: Dict[str, float] = {}
        self.results: List[Dict[str, Any]] = []
        self.running: bool = False
        self.lock: threading.Lock = threading.Lock()
        self.stats: Dict[str, int] = {"total": 0, "alive": 0, "clone": 0, "dead": 0, "filtered": 0}

        self.success_count: int = 0
        self.total_count: int = 0
        self.last_newnym: float = 0
        self.start_time: float = 0
        self.next_newnym_success: int = random.randint(40, 60)
        self.next_newnym_total: int = 100
        self.total_newnym: int = 0

        self.pending_results: List[Dict[str, Any]] = []
        self.pending_fp: Dict[str, str] = {}
        self.pending_btc: Dict[str, str] = {}
        self.pending_checked: List[str] = []
        self.pending_dead: Dict[str, float] = {}

        # Tkinter variables loaded from AppConfig
        self.dark_mode_var = tk.BooleanVar(value=cfg.dark_mode)
        self.backend_var = tk.StringVar(value=cfg.backend)
        self.auto_newnym_success_var = tk.BooleanVar(value=cfg.auto_newnym_success)
        self.auto_newnym_total_var = tk.BooleanVar(value=cfg.auto_newnym_total)
        self.success_threshold_var = tk.IntVar(value=cfg.success_threshold)
        self.total_threshold_var = tk.IntVar(value=cfg.total_threshold)
        self.auto_save_var = tk.BooleanVar(value=cfg.auto_save)
        self.allow_clearnet_var = tk.BooleanVar(value=cfg.allow_clearnet)
        self.encrypt_storage_var = tk.BooleanVar(value=cfg.encrypt_storage)
        self.status_var = tk.StringVar(value="Készen - v4.8 secure")

        # Build UI layout
        self.setup_ui()
        self.apply_theme()

        # Initialize state & Tor checks
        self.load_state(silent=True)
        self.load_deadlist()

        # Event bindings
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Control-s>", lambda e: self.save_state(silent=False))
        self.root.bind("<Control-n>", lambda e: self.manual_newnym_thread())
        self.root.bind("<Control-f>", lambda e: self.apply_filters())
        self.root.bind("<Control-Shift-Delete>", lambda e: self.panic_wipe())
        self.root.bind("<Control-Shift-KP_Delete>", lambda e: self.panic_wipe())
        self.root.bind("<Control-Shift-BackSpace>", lambda e: self.panic_wipe())
        self.root.bind("<Control-Delete>", lambda e: self.panic_wipe())
        self.root.bind("<Control-KP_Delete>", lambda e: self.panic_wipe())

        threading.Thread(target=self.check_tor_on_startup, daemon=True).start()

    def get_backend(self) -> Any:
        backend = (
            self.sqlite_backend
            if self.backend_var.get() == "sqlite"
            else self.json_backend
        )
        if hasattr(backend, "encrypt_storage"):
            backend.encrypt_storage = self.encrypt_storage_var.get()
            if backend.encrypt_storage and getattr(backend, "encryptor", None) is None:
                from onion_search.storage.crypto import StorageEncryptor
                backend.encryptor = StorageEncryptor()
        return backend

    def _cache_fp(self, fp: str, url: str) -> None:
        self.seen_fp[fp] = url
        if len(self.seen_fp) > MAX_MEMORY_CACHE_SIZE:
            self.seen_fp.popitem(last=False)

    def _cache_btc(self, btc: str, url: str) -> None:
        self.seen_btc[btc] = url
        if len(self.seen_btc) > MAX_MEMORY_CACHE_SIZE:
            self.seen_btc.popitem(last=False)

    def is_fp_seen(self, fp: str) -> Tuple[bool, Optional[str]]:
        with self.lock:
            if fp in self.seen_fp:
                return True, self.seen_fp[fp]

        if self.backend_var.get() == "sqlite":
            db_url = self.sqlite_backend.get_fingerprint_url(fp)
            if db_url:
                with self.lock:
                    self._cache_fp(fp, db_url)
                return True, db_url
        return False, None

    def is_btc_seen(self, btc: str) -> Tuple[bool, Optional[str]]:
        with self.lock:
            if btc in self.seen_btc:
                return True, self.seen_btc[btc]

        if self.backend_var.get() == "sqlite":
            db_url = self.sqlite_backend.get_btc_url(btc)
            if db_url:
                with self.lock:
                    self._cache_btc(btc, db_url)
                return True, db_url
        return False, None

    def apply_theme(self) -> None:
        """Configure and toggle modern dark/light themes via ttk.Style."""
        dark = self.dark_mode_var.get()
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        if dark:
            bg_main = "#181926"
            bg_panel = "#24273a"
            bg_card = "#313244"
            fg_main = "#cad3f5"
            fg_muted = "#a5adcb"
            accent = "#8aadf4"

            self.root.configure(bg=bg_main)
            style.configure(".", background=bg_main, foreground=fg_main)
            style.configure("TFrame", background=bg_main)
            style.configure("TLabelframe", background=bg_main, foreground=accent)
            style.configure("TLabelframe.Label", background=bg_main, foreground=accent)
            style.configure("TLabel", background=bg_main, foreground=fg_main)
            style.configure("TButton", background=bg_panel, foreground=fg_main)
            style.configure("TCheckbutton", background=bg_main, foreground=fg_main)
            style.configure("TRadiobutton", background=bg_main, foreground=fg_main)
            style.configure("TEntry", fieldbackground=bg_panel, foreground=fg_main)
            style.configure("TCombobox", fieldbackground=bg_panel, foreground=fg_main)
            style.configure("TSpinbox", fieldbackground=bg_panel, foreground=fg_main)
            style.configure(
                "Treeview",
                background=bg_panel,
                foreground=fg_main,
                fieldbackground=bg_panel,
                rowheight=24,
            )
            style.configure(
                "Treeview.Heading",
                background=bg_card,
                foreground=fg_main,
                font=("TkDefaultFont", 8, "bold"),
            )
            style.map(
                "Treeview",
                background=[("selected", "#3e5879")],
                foreground=[("selected", "white")],
            )
            style.configure(
                "green.Horizontal.TProgressbar",
                background="#a6e3a1",
                troughcolor=bg_card,
            )

            # Update Canvas and ScrolledText colors
            self.canvas_socks.configure(bg=bg_main)
            self.canvas_ctrl.configure(bg=bg_main)
            self.extra_text.configure(
                bg=bg_panel, fg=fg_main, insertbackground=fg_main
            )
            self.log_panel.log_text.configure(
                bg=bg_panel, fg=fg_main, insertbackground=fg_main
            )
            self.log_panel.apply_tag_styles(dark_mode=True)
            self.status_bar.configure(bg="#11111b")
            self.lbl_statusbar.configure(bg="#11111b", fg=fg_main)

            # Update stats cards
            cards = [
                (self.card_total, self.lbl_total, "#24273a", fg_muted, fg_main),
                (self.card_checked, self.lbl_checked, "#18342b", "#94e2d5", "#a6e3a1"),
                (self.card_alive, self.lbl_alive, "#142c26", "#a6e3a1", "#a6e3a1"),
                (self.card_dead, self.lbl_dead, "#3b1d24", "#f38ba8", "#f38ba8"),
                (self.card_clone, self.lbl_clone, "#332a1c", "#f9e2af", "#f9e2af"),
                (self.card_unique, self.lbl_unique, "#1e293b", "#89b4fa", "#89b4fa"),
                (self.card_filtered, self.lbl_filtered, "#2a1f3d", "#cba6f7", "#cba6f7"),
            ]
            for c_frame, c_lbl, c_bg, c_head_fg, c_val_fg in cards:
                c_frame.configure(bg=c_bg)
                for child in c_frame.winfo_children():
                    if child == c_lbl:
                        child.configure(bg=c_bg, fg=c_val_fg)
                    else:
                        child.configure(bg=c_bg, fg=c_head_fg)

            self.btn_theme.config(text="☀️ Világos mód")
        else:
            bg_main = "#f4f5f7"
            bg_panel = "#ffffff"
            bg_card = "#ecf0f1"
            fg_main = "#2c3e50"
            fg_muted = "#7f8c8d"

            self.root.configure(bg=bg_main)
            style.configure(".", background=bg_main, foreground=fg_main)
            style.configure("TFrame", background=bg_main)
            style.configure("TLabelframe", background=bg_main, foreground="#2980b9")
            style.configure("TLabelframe.Label", background=bg_main, foreground="#2980b9")
            style.configure("TLabel", background=bg_main, foreground=fg_main)
            style.configure("TButton", background=bg_card, foreground=fg_main)
            style.configure("TCheckbutton", background=bg_main, foreground=fg_main)
            style.configure("TRadiobutton", background=bg_main, foreground=fg_main)
            style.configure("TEntry", fieldbackground=bg_panel, foreground=fg_main)
            style.configure("TCombobox", fieldbackground=bg_panel, foreground=fg_main)
            style.configure("TSpinbox", fieldbackground=bg_panel, foreground=fg_main)
            style.configure(
                "Treeview",
                background=bg_panel,
                foreground=fg_main,
                fieldbackground=bg_panel,
                rowheight=24,
            )
            style.configure(
                "Treeview.Heading",
                background="#dfe6e9",
                foreground=fg_main,
                font=("TkDefaultFont", 8, "bold"),
            )
            style.map(
                "Treeview",
                background=[("selected", "#3498db")],
                foreground=[("selected", "white")],
            )
            style.configure(
                "green.Horizontal.TProgressbar",
                background="#2ecc71",
                troughcolor=bg_card,
            )

            self.canvas_socks.configure(bg=bg_main)
            self.canvas_ctrl.configure(bg=bg_main)
            self.extra_text.configure(
                bg=bg_panel, fg=fg_main, insertbackground=fg_main
            )
            self.log_panel.log_text.configure(
                bg=bg_panel, fg=fg_main, insertbackground=fg_main
            )
            self.log_panel.apply_tag_styles(dark_mode=False)
            self.status_bar.configure(bg="#2c3e50")
            self.lbl_statusbar.configure(bg="#2c3e50", fg="white")

            cards = [
                (self.card_total, self.lbl_total, "#ecf0f1", "#7f8c8d", "#2c3e50"),
                (self.card_checked, self.lbl_checked, "#d5f5e3", "#27ae60", "#1e8449"),
                (self.card_alive, self.lbl_alive, "#d4efdf", "#229954", "#1a7a3a"),
                (self.card_dead, self.lbl_dead, "#fadbd8", "#c0392b", "#922b21"),
                (self.card_clone, self.lbl_clone, "#fdebd0", "#e67e22", "#b9770e"),
                (self.card_unique, self.lbl_unique, "#d6eaf8", "#2980b9", "#1a5276"),
                (self.card_filtered, self.lbl_filtered, "#e8daef", "#8e44ad", "#6c3483"),
            ]
            for c_frame, c_lbl, c_bg, c_head_fg, c_val_fg in cards:
                c_frame.configure(bg=c_bg)
                for child in c_frame.winfo_children():
                    if child == c_lbl:
                        child.configure(bg=c_bg, fg=c_val_fg)
                    else:
                        child.configure(bg=c_bg, fg=c_head_fg)

            self.btn_theme.config(text="🌙 Sötét mód")

    def toggle_theme(self) -> None:
        self.dark_mode_var.set(not self.dark_mode_var.get())
        self.apply_theme()
        self.save_current_config()

    def save_current_config(self) -> None:
        """Persist current UI options to ~/.config/onion_search/config.json."""
        try:
            cfg = AppConfig(
                socks_port=self.port_var.get(),
                ctrl_port=self.ctrl_port_var.get(),
                workers=self.worker_var.get(),
                backend=self.backend_var.get(),
                dark_mode=self.dark_mode_var.get(),
                auto_newnym_success=self.auto_newnym_success_var.get(),
                auto_newnym_total=self.auto_newnym_total_var.get(),
                success_threshold=self.success_threshold_var.get(),
                total_threshold=self.total_threshold_var.get(),
                auto_save=self.auto_save_var.get(),
                live_filtering=self.filters_panel.live_filter_var.get(),
                allow_clearnet=self.allow_clearnet_var.get(),
                encrypt_storage=self.encrypt_storage_var.get(),
                queries=self.query_entry.get(),
            )
            self.config_manager.save(cfg)
        except Exception:
            pass

    def setup_ui(self) -> None:
        cfg = self.config_manager.config

        # 1. Top toolbar
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Ahmia szavak:").pack(side=tk.LEFT)
        self.query_entry = ttk.Entry(top, width=18)
        self.query_entry.insert(0, cfg.queries)
        self.query_entry.pack(side=tk.LEFT, padx=3)

        ttk.Label(top, text="Tor:").pack(side=tk.LEFT, padx=(4, 0))
        self.port_var = tk.StringVar(value=cfg.socks_port)
        ttk.Combobox(
            top, textvariable=self.port_var, values=["9050", "9150"], width=5
        ).pack(side=tk.LEFT)

        ttk.Label(top, text="Ctrl:").pack(side=tk.LEFT, padx=(4, 0))
        self.ctrl_port_var = tk.StringVar(value=cfg.ctrl_port)
        ttk.Combobox(
            top, textvariable=self.ctrl_port_var, values=["9051", "9151"], width=5
        ).pack(side=tk.LEFT)

        ttk.Label(top, text="Workers:").pack(side=tk.LEFT, padx=(4, 0))
        self.worker_var = tk.IntVar(value=cfg.workers)
        ttk.Spinbox(
            top, from_=2, to=10, textvariable=self.worker_var, width=3
        ).pack(side=tk.LEFT)

        ttk.Label(top, text="Backend:").pack(side=tk.LEFT, padx=(6, 0))
        self.backend_combo = ttk.Combobox(
            top,
            textvariable=self.backend_var,
            values=["sqlite", "json"],
            width=6,
            state="readonly",
        )
        self.backend_combo.pack(side=tk.LEFT)
        self.backend_combo.bind(
            "<<ComboboxSelected>>", lambda e: self.on_backend_switch()
        )

        ttk.Checkbutton(top, text="Clearnet", variable=self.allow_clearnet_var).pack(
            side=tk.LEFT, padx=3
        )
        ttk.Checkbutton(top, text="Titkosítva", variable=self.encrypt_storage_var).pack(
            side=tk.LEFT, padx=3
        )

        persist = ttk.Frame(top)
        persist.pack(side=tk.RIGHT)
        self.btn_panic = ttk.Button(
            persist, text="🚨 PÁNIK (Ctrl+Shift+Del)", command=self.panic_wipe
        )
        self.btn_panic.pack(side=tk.LEFT, padx=3)
        self.btn_theme = ttk.Button(
            persist, text="🌙 Sötét mód", command=self.toggle_theme
        )
        self.btn_theme.pack(side=tk.LEFT, padx=2)

        ttk.Button(
            persist, text="💾", width=3, command=lambda: self.save_state(silent=False)
        ).pack(side=tk.LEFT, padx=1)
        ttk.Button(
            persist, text="📂", width=3, command=lambda: self.load_state()
        ).pack(side=tk.LEFT, padx=1)
        ttk.Button(persist, text="🗑", width=3, command=self.clear_state).pack(
            side=tk.LEFT, padx=1
        )

        # 2. Status & NEWNYM toolbar
        status_top = ttk.Frame(self.root, padding=(8, 2))
        status_top.pack(fill=tk.X)
        self.canvas_socks = tk.Canvas(
            status_top, width=16, height=16, highlightthickness=0
        )
        self.canvas_socks.pack(side=tk.LEFT)
        self.led_socks = self.canvas_socks.create_oval(
            2, 2, 14, 14, fill="gray", outline=""
        )
        ttk.Label(status_top, text="SOCKS").pack(side=tk.LEFT, padx=(2, 8))

        self.canvas_ctrl = tk.Canvas(
            status_top, width=16, height=16, highlightthickness=0
        )
        self.canvas_ctrl.pack(side=tk.LEFT)
        self.led_ctrl = self.canvas_ctrl.create_oval(
            2, 2, 14, 14, fill="gray", outline=""
        )
        ttk.Label(status_top, text="CTRL").pack(side=tk.LEFT, padx=(2, 12))

        self.lbl_tor_status = ttk.Label(
            status_top, text="Tor: ellenőrzés...", foreground="gray"
        )
        self.lbl_tor_status.pack(side=tk.LEFT)
        ttk.Button(
            status_top, text="🔍 Auto-detect Tor", command=self.auto_detect_tor
        ).pack(side=tk.LEFT, padx=10)
        ttk.Separator(status_top, orient="vertical").pack(
            side=tk.LEFT, fill=tk.Y, padx=12
        )

        newnym_frame = ttk.LabelFrame(status_top, text="NEWNYM", padding=2)
        newnym_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Checkbutton(
            newnym_frame, text="Sikeresenként:", variable=self.auto_newnym_success_var
        ).pack(side=tk.LEFT)
        ttk.Spinbox(
            newnym_frame,
            from_=10,
            to=200,
            textvariable=self.success_threshold_var,
            width=5,
        ).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(
            newnym_frame, text="Összes:", variable=self.auto_newnym_total_var
        ).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Spinbox(
            newnym_frame,
            from_=20,
            to=500,
            textvariable=self.total_threshold_var,
            width=5,
        ).pack(side=tk.LEFT, padx=2)
        self.lbl_counts = ttk.Label(
            newnym_frame,
            text="Sikeres: 0 / Összes: 0",
            font=("TkDefaultFont", 8, "bold"),
        )
        self.lbl_counts.pack(side=tk.LEFT, padx=8)
        self.lbl_newnym = ttk.Label(
            newnym_frame,
            text="NEWNYM: 0",
            font=("TkDefaultFont", 8, "bold"),
            foreground="#2980b9",
        )
        self.lbl_newnym.pack(side=tk.LEFT, padx=4)
        ttk.Button(
            newnym_frame, text="Reset", command=self.reset_counters, width=6
        ).pack(side=tk.RIGHT)

        # 3. Filters panel component
        self.filters_panel = FilterPanel(
            self.root, on_filter_changed=self.apply_filters
        )
        self.filters_panel.live_filter_var.set(cfg.live_filtering)
        self.filters_panel.pack(fill=tk.X)

        # 4. Main body
        mid = ttk.Frame(self.root, padding=8)
        mid.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(mid)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        btn = ttk.Frame(left)
        btn.pack(fill=tk.X, pady=3)
        self.btn_github = ttk.Button(
            btn, text="GitHub", command=self.fetch_github_thread
        )
        self.btn_github.pack(side=tk.LEFT, padx=2)
        self.btn_start = ttk.Button(
            btn, text="▶ Start", command=self.start_thread
        )
        self.btn_start.pack(side=tk.LEFT, padx=2)
        self.btn_resume = ttk.Button(
            btn, text="⏩ Folytatás (Resume)", command=self.resume_thread, state=tk.DISABLED
        )
        self.btn_resume.pack(side=tk.LEFT, padx=2)
        self.btn_stop = ttk.Button(
            btn, text="⏹ Stop", command=self.stop, state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=2)
        self.btn_newnym = ttk.Button(
            btn, text="🔄 NEWNYM (Ctrl+N)", command=self.manual_newnym_thread
        )
        self.btn_newnym.pack(side=tk.LEFT, padx=(8, 2))
        ttk.Checkbutton(
            btn, text="Auto-mentés", variable=self.auto_save_var
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(left, text="Extra .onionok:").pack(anchor=tk.W)
        self.extra_text = scrolledtext.ScrolledText(left, height=3)
        self.extra_text.pack(fill=tk.X, pady=2)

        # Stats cards
        self.stats_frame = ttk.Frame(left)
        self.stats_frame.pack(fill=tk.X, pady=4)

        self.card_total = tk.Frame(
            self.stats_frame, bg="#ecf0f1", bd=1, relief=tk.RAISED
        )
        self.card_total.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Label(
            self.card_total,
            text="ÖSSZES",
            bg="#ecf0f1",
            fg="#7f8c8d",
            font=("TkDefaultFont", 7, "bold"),
        ).pack()
        self.lbl_total = tk.Label(
            self.card_total,
            text="0",
            bg="#ecf0f1",
            fg="#2c3e50",
            font=("TkDefaultFont", 10, "bold"),
        )
        self.lbl_total.pack()

        self.card_checked = tk.Frame(
            self.stats_frame, bg="#d5f5e3", bd=1, relief=tk.RAISED
        )
        self.card_checked.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Label(
            self.card_checked,
            text="ELLENŐRIZVE",
            bg="#d5f5e3",
            fg="#27ae60",
            font=("TkDefaultFont", 7, "bold"),
        ).pack()
        self.lbl_checked = tk.Label(
            self.card_checked,
            text="0",
            bg="#d5f5e3",
            fg="#1e8449",
            font=("TkDefaultFont", 10, "bold"),
        )
        self.lbl_checked.pack()

        self.card_alive = tk.Frame(
            self.stats_frame, bg="#d4efdf", bd=1, relief=tk.RAISED
        )
        self.card_alive.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Label(
            self.card_alive,
            text="ÉLŐ",
            bg="#d4efdf",
            fg="#229954",
            font=("TkDefaultFont", 7, "bold"),
        ).pack()
        self.lbl_alive = tk.Label(
            self.card_alive,
            text="0",
            bg="#d4efdf",
            fg="#1a7a3a",
            font=("TkDefaultFont", 12, "bold"),
        )
        self.lbl_alive.pack()

        self.card_dead = tk.Frame(
            self.stats_frame, bg="#fadbd8", bd=1, relief=tk.RAISED
        )
        self.card_dead.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Label(
            self.card_dead,
            text="HALOTT",
            bg="#fadbd8",
            fg="#c0392b",
            font=("TkDefaultFont", 7, "bold"),
        ).pack()
        self.lbl_dead = tk.Label(
            self.card_dead,
            text="0",
            bg="#fadbd8",
            fg="#922b21",
            font=("TkDefaultFont", 10, "bold"),
        )
        self.lbl_dead.pack()

        self.card_clone = tk.Frame(
            self.stats_frame, bg="#fdebd0", bd=1, relief=tk.RAISED
        )
        self.card_clone.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Label(
            self.card_clone,
            text="KLÓN",
            bg="#fdebd0",
            fg="#e67e22",
            font=("TkDefaultFont", 7, "bold"),
        ).pack()
        self.lbl_clone = tk.Label(
            self.card_clone,
            text="0",
            bg="#fdebd0",
            fg="#b9770e",
            font=("TkDefaultFont", 10, "bold"),
        )
        self.lbl_clone.pack()

        self.card_unique = tk.Frame(
            self.stats_frame, bg="#d6eaf8", bd=1, relief=tk.RAISED
        )
        self.card_unique.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Label(
            self.card_unique,
            text="EGYEDI",
            bg="#d6eaf8",
            fg="#2980b9",
            font=("TkDefaultFont", 7, "bold"),
        ).pack()
        self.lbl_unique = tk.Label(
            self.card_unique,
            text="0",
            bg="#d6eaf8",
            fg="#1a5276",
            font=("TkDefaultFont", 12, "bold"),
        )
        self.lbl_unique.pack()

        self.card_filtered = tk.Frame(
            self.stats_frame, bg="#e8daef", bd=1, relief=tk.RAISED
        )
        self.card_filtered.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Label(
            self.card_filtered,
            text="SZŰRT KI",
            bg="#e8daef",
            fg="#8e44ad",
            font=("TkDefaultFont", 7, "bold"),
        ).pack()
        self.lbl_filtered = tk.Label(
            self.card_filtered,
            text="0",
            bg="#e8daef",
            fg="#6c3483",
            font=("TkDefaultFont", 10, "bold"),
        )
        self.lbl_filtered.pack()

        # Progress bar
        prog_frame = ttk.Frame(left)
        prog_frame.pack(fill=tk.X, pady=3)
        self.progress = ttk.Progressbar(
            prog_frame, mode="determinate", style="green.Horizontal.TProgressbar"
        )
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.lbl_percent = ttk.Label(
            prog_frame, text="0%", width=6, font=("TkDefaultFont", 8, "bold")
        )
        self.lbl_percent.pack(side=tk.LEFT, padx=4)
        self.lbl_speed = ttk.Label(prog_frame, text="", font=("TkDefaultFont", 7))
        self.lbl_speed.pack(side=tk.LEFT)

        # Status bar
        self.status_bar = tk.Frame(left, bg="#2c3e50", height=22)
        self.status_bar.pack(fill=tk.X, pady=2)
        self.lbl_statusbar = tk.Label(
            self.status_bar,
            textvariable=self.status_var,
            bg="#2c3e50",
            fg="white",
            font=("TkDefaultFont", 8),
            anchor=tk.W,
        )
        self.lbl_statusbar.pack(fill=tk.X, padx=6, pady=2)

        # Log component
        self.log_panel = LogPanel(left)
        self.log_panel.pack(fill=tk.BOTH, expand=True)

        # 5. Right side (Treeview, preview inspector, export toolbar)
        right = ttk.Frame(mid)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

        tr = ttk.Frame(right)
        tr.pack(fill=tk.X)
        ttk.Label(tr, text="Egyedi találatok:").pack(side=tk.LEFT)
        self.lbl_backend = ttk.Label(
            tr, text="Backend: sqlite", foreground="purple", font=("TkDefaultFont", 7)
        )
        self.lbl_backend.pack(side=tk.RIGHT)

        cf = ttk.Frame(right)
        cf.pack(fill=tk.X, pady=2)
        ttk.Button(cf, text="📋 URL", command=self.copy_selected_url).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(cf, text="📋 Összes", command=self.copy_all_urls).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(cf, text="👁 Előnézet", command=self.open_selected_preview).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(cf, text="📦 Export...", command=self.open_export_dialog).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(cf, text="🔍 SQL", command=self.open_sql_query).pack(
            side=tk.LEFT, padx=4
        )

        cols = ("title", "url", "lang", "category", "last_check", "info")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=18)
        self.tree.heading("title", text="Cím")
        self.tree.heading("url", text=".onion")
        self.tree.heading("lang", text="Nyelv")
        self.tree.heading("category", text="Kat.")
        self.tree.heading("last_check", text="Utolsó check")
        self.tree.heading("info", text="Snippet")

        self.tree.column("title", width=150)
        self.tree.column("url", width=210)
        self.tree.column("lang", width=40)
        self.tree.column("category", width=55)
        self.tree.column("last_check", width=100)
        self.tree.column("info", width=120)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.tag_configure(
            "lang_hu", background="#eafaf1", foreground="#1e8449"
        )
        self.tree.tag_configure(
            "lang_en", background="#ebf5fb", foreground="#1a5276"
        )
        self.tree.tag_configure(
            "lang_de", background="#fef9e7", foreground="#7d6608"
        )
        self.tree.tag_configure(
            "lang_ru", background="#fdedec", foreground="#922b21"
        )
        self.tree.tag_configure(
            "lang_fr", background="#f4ecf7", foreground="#6c3483"
        )
        self.tree.tag_configure("cat_forum", font=("TkDefaultFont", 8, "bold"))

        vsb = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)

        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(
            label="📋 URL másolás", command=self.copy_selected_url
        )
        self.context_menu.add_command(
            label="👁 Előnézet megnyitása", command=self.open_selected_preview
        )
        self.context_menu.add_command(
            label="🌐 Megnyitás Torban", command=self.open_in_tor_browser
        )
        self.context_menu.add_command(label="🗑 Törlés", command=self.delete_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="🔄 NEWNYM most (Ctrl+N)", command=self.manual_newnym_thread
        )
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Double-1>", lambda e: self.open_selected_preview())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_inline_preview())

        # 6. Bottom Inspector Preview Pane
        self.preview_frame = ttk.LabelFrame(
            right, text="👁 Találat Előnézet & Részletek", padding=6
        )
        self.preview_frame.pack(fill=tk.X, pady=(6, 0))

        p_top = ttk.Frame(self.preview_frame)
        p_top.pack(fill=tk.X)
        self.lbl_prev_title = ttk.Label(
            p_top, text="Válassz ki egy találatot...", font=("TkDefaultFont", 9, "bold")
        )
        self.lbl_prev_title.pack(side=tk.LEFT)
        self.lbl_prev_meta = ttk.Label(
            p_top, text="", font=("TkDefaultFont", 8), foreground="#8e44ad"
        )
        self.lbl_prev_meta.pack(side=tk.RIGHT)

        p_url_bar = ttk.Frame(self.preview_frame)
        p_url_bar.pack(fill=tk.X, pady=2)
        self.lbl_prev_url = ttk.Label(
            p_url_bar, text="", foreground="#2980b9", font=("Consolas", 8)
        )
        self.lbl_prev_url.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(p_url_bar, text="🌐 Tor Browser", command=self.open_in_tor_browser).pack(side=tk.RIGHT, padx=2)
        ttk.Button(p_url_bar, text="📋 Másolás", command=self.copy_selected_url).pack(side=tk.RIGHT, padx=2)

        self.prev_text = scrolledtext.ScrolledText(
            self.preview_frame, height=4, font=("Consolas", 8)
        )
        self.prev_text.pack(fill=tk.X, pady=2)

    def log_msg(self, msg: str, force: bool = False, tag: Optional[str] = None) -> None:
        """Route log message via standard Python logger."""
        extra = {"tag": tag} if tag else {}
        logger.info(msg, extra=extra)

    def set_led(self, canvas: tk.Canvas, led_id: int, color: str) -> None:
        def _do():
            canvas.itemconfig(led_id, fill=color)

        self.root.after(0, _do)

    def set_statusbar_color(self, bg: str, fg: str = "white", msg: Optional[str] = None) -> None:
        def _do():
            self.status_bar.config(bg=bg)
            self.lbl_statusbar.config(bg=bg, fg=fg)
            if msg:
                self.status_var.set(msg)

        self.root.after(0, _do)

    def apply_filters(self) -> None:
        """Refresh TreeView based on current quick and precise filters."""
        self.tree.delete(*self.tree.get_children())
        shown: int = 0
        filtered_out: int = 0
        for r in self.results:
            visible, _ = self.filters_panel.is_item_visible(r)
            if not visible:
                filtered_out += 1
                continue
            ts_str: str = fmt_ts(r.get("ts"))
            tags: List[str] = []
            l = r.get("lang", "en")
            if l in ("hu", "en", "de", "ru", "fr"):
                tags.append(f"lang_{l}")
            if r.get("category") == "forum":
                tags.append("cat_forum")
            self.tree.insert(
                "",
                tk.END,
                values=(
                    r.get("title", ""),
                    r.get("url", ""),
                    r.get("lang", ""),
                    r.get("category", ""),
                    ts_str,
                    r.get("snippet", "")[:80],
                ),
                tags=tuple(tags),
            )
            shown += 1

        self.filters_panel.set_counts(shown, len(self.results), filtered_out)
        self.log_msg(
            f"[FILTER] lang={self.filters_panel.lang_filter_var.get()} "
            f"cat={self.filters_panel.category_filter_var.get()} "
            f"precise={self.filters_panel.enable_precise_var.get()} -> {shown}/{len(self.results)}",
            force=False,
            tag="filter",
        )

    def reset_counters(self) -> None:
        with self.lock:
            self.success_count = 0
            self.total_count = 0
        self.next_newnym_success = random.randint(
            int(self.success_threshold_var.get() * 0.8),
            int(self.success_threshold_var.get() * 1.2),
        )
        self.next_newnym_total = self.total_threshold_var.get()
        self.update_counts_label()
        self.log_msg("[COUNTER] Számlálók reset", force=True, tag="save")

    def update_counts_label(self) -> None:
        self.root.after(
            0,
            lambda: self.lbl_counts.config(
                text=(
                    f"Sikeres: {self.success_count}/{self.next_newnym_success} | "
                    f"Összes: {self.total_count}/{self.next_newnym_total}"
                )
            ),
        )

    def auto_detect_tor(self) -> None:
        self.log_msg("[TOR AUTO-DETECT] Keresés 9050/9150...", force=True, tag="start")
        self.set_statusbar_color("#f39c12", msg="Tor auto-detect 9050/9150...")

        def _run() -> None:
            socks_port, ok, msg = self.tor_controller.detect_working_tor(
                preferred_port=self.port_var.get()
            )
            ctrl_map = {"9150": "9151", "9050": "9051"}
            ctrl_port = ctrl_map.get(
                socks_port, "9151" if socks_port == "9150" else "9051"
            )
            ctrl_ok, ctrl_msg = self.tor_controller.check_control(ctrl_port)
            if not ctrl_ok:
                other_ctrl = "9051" if ctrl_port == "9151" else "9151"
                other_ok, other_msg = self.tor_controller.check_control(other_ctrl)
                if other_ok:
                    ctrl_port = other_ctrl
                    ctrl_ok = True
                    ctrl_msg = other_msg

            self.root.after(0, lambda: self.port_var.set(socks_port))
            self.root.after(0, lambda: self.ctrl_port_var.set(ctrl_port))
            self.root.after(
                0,
                lambda: self.log_msg(
                    f"[TOR AUTO] SOCKS={socks_port} ({msg}) CTRL={ctrl_port} ({ctrl_msg})",
                    force=True,
                    tag="tor_ok" if ok else "tor_err",
                ),
            )

            def _update() -> None:
                if ok:
                    self.set_led(self.canvas_socks, self.led_socks, "#2ecc71")
                else:
                    self.set_led(self.canvas_socks, self.led_socks, "#e67e22")
                if ctrl_ok:
                    self.set_led(self.canvas_ctrl, self.led_ctrl, "#2ecc71")
                else:
                    self.set_led(self.canvas_ctrl, self.led_ctrl, "#e74c3c")
                if ok and ctrl_ok:
                    self.lbl_tor_status.config(
                        text=f"Tor OK: SOCKS {socks_port} + Ctrl {ctrl_port}",
                        foreground="#27ae60",
                    )
                    self.set_statusbar_color(
                        "#27ae60",
                        msg=f"AUTO OK: SOCKS {socks_port} + Ctrl {ctrl_port} - {msg}",
                    )
                elif ok:
                    self.lbl_tor_status.config(
                        text=f"Tor SOCKS OK ({socks_port}), Ctrl hiba ({ctrl_port})",
                        foreground="#e67e22",
                    )
                    self.set_statusbar_color(
                        "#e67e22", msg=f"SOCKS OK {socks_port}, de Ctrl {ctrl_port} hiba"
                    )
                else:
                    self.lbl_tor_status.config(
                        text="Tor NEM elérhető - Tor Browser fut?",
                        foreground="#c0392b",
                    )
                    self.set_statusbar_color("#c0392b", msg=f"Tor hiba: {msg}")

            self.root.after(0, _update)

        threading.Thread(target=_run, daemon=True).start()

    def check_tor_on_startup(self) -> None:
        try:
            time.sleep(0.8)
            socks_port, ok, msg = self.tor_controller.detect_working_tor(
                preferred_port=self.port_var.get()
            )
            if ok:
                self.root.after(0, lambda: self.port_var.set(socks_port))
                ctrl_map = {"9150": "9151", "9050": "9051"}
                ctrl_port = ctrl_map.get(socks_port, self.ctrl_port_var.get())
                self.root.after(0, lambda: self.ctrl_port_var.set(ctrl_port))
            else:
                socks_port = self.port_var.get()
                ctrl_port = self.ctrl_port_var.get()

            socks_ok, socks_msg = self.tor_controller.check_socks(socks_port)
            if not socks_ok:
                alt = "9150" if socks_port == "9050" else "9050"
                alt_ok, alt_msg = self.tor_controller.check_socks(alt)
                if alt_ok:
                    socks_port = alt
                    socks_ok = True
                    socks_msg = alt_msg
                    self.root.after(0, lambda: self.port_var.set(socks_port))

            ctrl_ok, ctrl_msg = self.tor_controller.check_control(ctrl_port)
            if not ctrl_ok:
                alt_ctrl = "9151" if str(ctrl_port) == "9051" else "9051"
                alt_ok, alt_msg = self.tor_controller.check_control(alt_ctrl)
                if alt_ok:
                    ctrl_port = alt_ctrl
                    ctrl_ok = True
                    ctrl_msg = alt_msg
                    self.root.after(0, lambda: self.ctrl_port_var.set(ctrl_port))

            self.log_msg(
                f"[TOR CHECK] SOCKS {socks_port}: {socks_msg}",
                force=True,
                tag="tor_ok" if socks_ok else "tor_err",
            )
            self.log_msg(
                f"[TOR CHECK] CTRL {ctrl_port}: {ctrl_msg}",
                force=True,
                tag="tor_ok" if ctrl_ok else "tor_err",
            )

            def _update() -> None:
                if socks_ok:
                    self.set_led(self.canvas_socks, self.led_socks, "#2ecc71")
                else:
                    self.set_led(self.canvas_socks, self.led_socks, "#e74c3c")
                if ctrl_ok:
                    self.set_led(self.canvas_ctrl, self.led_ctrl, "#2ecc71")
                else:
                    self.set_led(self.canvas_ctrl, self.led_ctrl, "#e74c3c")
                if socks_ok and ctrl_ok:
                    self.lbl_tor_status.config(
                        text=f"Tor OK: SOCKS {socks_port} + Ctrl {ctrl_port}",
                        foreground="#27ae60",
                    )
                    self.set_statusbar_color("#27ae60", msg=f"Tor OK - {socks_msg}")
                elif socks_ok:
                    self.lbl_tor_status.config(
                        text="Tor SOCKS OK, Ctrl hiba", foreground="#e67e22"
                    )
                    self.set_statusbar_color(
                        "#e67e22", msg=f"Tor SOCKS OK ({socks_port}), de {ctrl_msg}"
                    )
                else:
                    self.lbl_tor_status.config(
                        text="Tor NEM elérhető - Tor Browser fut?", foreground="#c0392b"
                    )
                    self.set_statusbar_color("#c0392b", msg=f"Tor hiba: {socks_msg}")

            self.root.after(0, _update)
        except Exception:
            return

    def on_backend_switch(self) -> None:
        backend: str = self.backend_var.get()
        self.lbl_backend.config(text=f"Backend: {backend}")
        self.log_msg(f"[BACKEND] Váltás: {backend}", force=True, tag="save")
        self.load_state(silent=False)
        self.load_deadlist()
        self.save_current_config()

    def update_inline_preview(self) -> None:
        """Update the bottom preview inspector pane with selected item details."""
        sel = self.tree.selection()
        if not sel:
            return
        item_vals = self.tree.item(sel[0])["values"]
        if not item_vals or len(item_vals) < 2:
            return
        url: str = item_vals[1]

        res = next((r for r in self.results if r.get("url") == url), None)
        if not res:
            res = {
                "title": item_vals[0],
                "url": url,
                "lang": item_vals[2] if len(item_vals) > 2 else "en",
                "category": item_vals[3] if len(item_vals) > 3 else "other",
                "ts": time.time(),
                "snippet": item_vals[5] if len(item_vals) > 5 else "",
            }

        self.lbl_prev_title.config(text=res.get("title", "Nincs cím"))
        self.lbl_prev_url.config(text=res.get("url", ""))
        self.lbl_prev_meta.config(
            text=f"Nyelv: {res.get('lang','en')} | Kategória: {res.get('category','other')} | Utolsó ellenőrzés: {fmt_ts(res.get('ts'))}"
        )
        self.prev_text.delete("1.0", tk.END)
        self.prev_text.insert(
            tk.END,
            f"Snippet: {res.get('snippet', '')}\n\nUjjlenyomat (Fingerprint): {res.get('fp', 'N/A')}",
        )

    def open_selected_preview(self) -> None:
        """Open detailed modal preview dialog for selected result."""
        sel = self.tree.selection()
        if not sel:
            return
        url = self.tree.item(sel[0])["values"][1]
        res = next((r for r in self.results if r.get("url") == url), None)
        if not res:
            return

        win = tk.Toplevel(self.root)
        win.title(f"Előnézet: {res.get('title', url)}")
        win.geometry("680x420")

        ttk.Label(win, text=res.get("title", ""), font=("TkDefaultFont", 11, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 2))
        ttk.Label(win, text=res.get("url", ""), foreground="#2980b9", font=("Consolas", 9)).pack(anchor=tk.W, padx=10, pady=2)
        ttk.Label(
            win,
            text=f"Nyelv: {res.get('lang', 'en')}  |  Kategória: {res.get('category', 'other')}  |  Ujjlenyomat: {res.get('fp', 'N/A')}",
            font=("TkDefaultFont", 8),
            foreground="#8e44ad",
        ).pack(anchor=tk.W, padx=10, pady=2)

        txt = scrolledtext.ScrolledText(win, height=12, font=("Consolas", 9))
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        txt.insert(tk.END, f"--- TARTALOM / SNIPPET ---\n\n{res.get('snippet', '')}\n\n")
        txt.insert(tk.END, f"Utolsó látogatás: {fmt_ts(res.get('ts'))}\n")

        btn_row = ttk.Frame(win)
        btn_row.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btn_row, text="🌐 Megnyitás Torban", command=self.open_in_tor_browser).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="📋 URL másolása", command=self.copy_selected_url).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="Bezárás", command=win.destroy).pack(side=tk.RIGHT, padx=3)

    def open_in_tor_browser(self) -> None:
        """Attempt to launch Tor Browser or copy socks-ready command to clipboard."""
        sel = self.tree.selection()
        if not sel:
            return
        url: str = self.tree.item(sel[0])["values"][1]
        self.copy_to_clipboard(url)

        candidates: List[str] = ["torbrowser-launcher", "tor-browser", "firefox"]
        launched: bool = False
        for c in candidates:
            try:
                subprocess.Popen([c, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                launched = True
                self.log_msg(f"[TOR LAUNCH] Megnyitva: {c} {url}", force=True, tag="tor_ok")
                self.set_statusbar_color("#27ae60", msg=f"Megnyitva Tor Browserben: {url[:50]}")
                break
            except Exception:
                pass

        if not launched:
            self.set_statusbar_color("#2980b9", msg="URL másolva vágólapra (nyisd meg a Tor Browserben)")
            messagebox.showinfo(
                "Tor Browser",
                f"Az URL másolva a vágólapra:\n{url}\n\nNyisd meg a Tor Browserben a megtekintéshez!",
            )

    def open_sql_query(self) -> None:
        if self.backend_var.get() != "sqlite":
            messagebox.showinfo("SQL", "Válts SQLite backend-re!")
            return
        win = tk.Toplevel(self.root)
        win.title("SQL Lekérdezés - CSAK SELECT (read-only)")
        win.geometry("720x480")
        ttk.Label(
            win,
            text=(
                "Biztonságos mód: csak SELECT / WITH engedett, "
                "DELETE/DROP/UPDATE blokkolva. query_only=ON, read-only connection."
            ),
            foreground="#c0392b",
        ).pack(anchor=tk.W, padx=5, pady=2)
        ttk.Label(
            win,
            text="Példa: SELECT url,title,lang FROM results WHERE lang='hu' LIMIT 20",
        ).pack(anchor=tk.W, padx=5, pady=2)
        query_entry = ttk.Entry(win, width=90)
        query_entry.insert(
            0,
            (
                "SELECT url,title,lang,category,datetime(ts,'unixepoch','localtime') as last_check "
                "FROM results ORDER BY ts DESC LIMIT 50"
            ),
        )
        query_entry.pack(fill=tk.X, padx=5)
        txt = scrolledtext.ScrolledText(win, height=20, font=("Consolas", 8))
        txt.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        def is_safe_select(q: str) -> Tuple[bool, str]:
            q_stripped = q.strip().lower()
            if not q_stripped:
                return False, "Üres lekérdezés"
            forbidden = [
                "delete",
                "drop",
                "insert",
                "update",
                "alter",
                "attach",
                "detach",
                "replace",
                "vacuum",
            ]
            first_word = re.split(r"\s+", q_stripped, 1)[0]
            if first_word not in ("select", "with", "explain"):
                return False, f"Csak SELECT/WITH engedélyezett, te: {first_word.upper()}"
            for kw in forbidden:
                if re.search(r"\b" + kw + r"\b", q_stripped):
                    return (
                        False,
                        f"Tiltott kulcsszó: {kw.upper()} - csak olvasás engedélyezett",
                    )
            if ";" in q_stripped[:-1]:
                if q_stripped.count(";") > 1 or not q_stripped.rstrip().endswith(";"):
                    return False, "Több utasítás (;) nem engedélyezett"
            return True, "OK"

        def run_q() -> None:
            q = query_entry.get()
            safe, reason = is_safe_select(q)
            if not safe:
                txt.delete("1.0", tk.END)
                txt.insert(
                    tk.END,
                    f"BLOKKOLVA: {reason}\n\nCsak SELECT engedélyezett!\n",
                )
                self.log_msg(f"[SQL BLOKK] {reason} - {q[:80]}", force=True, tag="error")
                return
            try:
                uri = f"file:{DB_FILE}?mode=ro"
                con = sqlite3.connect(uri, uri=True, timeout=5)
                con.execute("PRAGMA query_only=ON;")
                cur = con.cursor()
                cur.execute(q)
                rows = cur.fetchall()
                txt.delete("1.0", tk.END)
                txt.insert(tk.END, f"-- {len(rows)} sor, read-only, query_only=ON\n")
                for r in rows[:500]:
                    txt.insert(tk.END, str(r) + "\n")
                if len(rows) > 500:
                    txt.insert(tk.END, f"... és még {len(rows)-500} sor\n")
                con.close()
                self.log_msg(f"[SQL OK] {len(rows)} sor", force=True, tag="save")
            except Exception as e:
                txt.delete("1.0", tk.END)
                txt.insert(tk.END, f"HIBA: {e}")
                self.log_msg(f"[SQL HIBA] {e}", force=True, tag="error")

        ttk.Button(win, text="Futtatás (biztonságos)", command=run_q).pack(pady=5)
        run_q()

    def do_newnym(self, reason: str = "manual") -> bool:
        ctrl_port: int = int(self.ctrl_port_var.get() or 9051)
        now = time.time()
        if reason.startswith("auto") and now - self.last_newnym < MIN_NEWNYM_INTERVAL_AUTO:
            self.log_msg(
                f"[NEWNYM] Auto skip - {now-self.last_newnym:.1f}s < {MIN_NEWNYM_INTERVAL_AUTO}s",
                tag="newnym",
            )
            return False
        self.log_msg(
            f"[NEWNYM] Küldés ({reason}) -> {ctrl_port}", force=True, tag="newnym"
        )
        self.set_statusbar_color("#2980b9", msg=f"NEWNYM küldés {reason}...")

        ok, msg = self.tor_controller.trigger_newnym(
            control_port=ctrl_port, reason=reason
        )
        if ok:
            self.last_newnym = time.time()
            self.total_newnym += 1
            with self.lock:
                self.success_count = 0
                self.total_count = 0
            self.next_newnym_success = random.randint(
                int(self.success_threshold_var.get() * 0.8),
                int(self.success_threshold_var.get() * 1.2),
            )
            self.next_newnym_total = self.total_threshold_var.get()
            self.root.after(
                0, lambda: self.lbl_newnym.config(text=f"NEWNYM: {self.total_newnym}")
            )
            self.log_msg(
                f"[NEWNYM] OK - kov sikeres:{self.next_newnym_success} / "
                f"osszes:{self.next_newnym_total} | {msg}",
                force=True,
                tag="newnym",
            )
            self.set_statusbar_color("#27ae60", msg=f"NEWNYM OK ({reason})")
            self.update_counts_label()
            return True
        else:
            self.log_msg(f"[NEWNYM] HIBA: {msg}", force=True, tag="error")
            self.set_statusbar_color("#c0392b", msg=f"NEWNYM HIBA: {msg}")
            return False

    def manual_newnym_thread(self) -> None:
        threading.Thread(
            target=lambda: self.do_newnym(reason="manual"), daemon=True
        ).start()

    def check_auto_newnym(self, is_success: bool = False, auto_newnym_success: bool = False, auto_newnym_total: bool = False) -> None:
        with self.lock:
            self.total_count += 1
            if is_success:
                self.success_count += 1
            sc = self.success_count
            tc = self.total_count
            n_s = self.next_newnym_success
            n_t = self.next_newnym_total
        self.update_counts_label()
        if not self.running:
            return
        now = time.time()
        should_trigger = False
        reason = ""
        if auto_newnym_success and sc >= n_s:
            should_trigger = True
            reason = f"auto sikeres {sc}/{n_s}"
        if (
            not should_trigger
            and auto_newnym_total
            and tc >= n_t
        ):
            should_trigger = True
            reason = f"auto osszes {tc}/{n_t}"
        if should_trigger:
            if now - self.last_newnym >= MIN_NEWNYM_INTERVAL_TRIGGER:
                self.log_msg(
                    f"[NEWNYM] Auto trigger: {reason}", force=True, tag="newnym"
                )
                threading.Thread(
                    target=lambda r=reason: self.do_newnym(reason=r), daemon=True
                ).start()
            else:
                self.log_msg(
                    f"[NEWNYM] Auto var - {now-self.last_newnym:.1f}s < {MIN_NEWNYM_INTERVAL_TRIGGER}s",
                    tag="newnym",
                )

    def load_deadlist(self) -> None:
        self.dead_blacklist = self.get_backend().load_dead()

    def save_deadlist(self) -> None:
        self.get_backend().save_dead(self.dead_blacklist)

    def save_incremental_pending(self) -> None:
        """Save only newly discovered pending delta items without rewriting the entire database."""
        with self.lock:
            if not self.pending_results and not self.pending_checked and not self.pending_dead:
                return
            pending = {
                "results": list(self.pending_results),
                "seen_fp": dict(self.pending_fp),
                "seen_btc": dict(self.pending_btc),
                "checked_urls": list(self.pending_checked),
                "stats": dict(self.stats),
            }
            pending_dead = dict(self.pending_dead)
            self.pending_results.clear()
            self.pending_fp.clear()
            self.pending_btc.clear()
            self.pending_checked.clear()
            self.pending_dead.clear()

        try:
            backend = self.get_backend()
            backend.save_pending(pending)
            if pending_dead and hasattr(backend, "save_dead_pending"):
                backend.save_dead_pending(pending_dead)
        except Exception as e:
            self.log_msg(f"[SAVE INCREMENTAL HIBA] {e}", force=False, tag="error")

    def save_state(self, silent: bool = False) -> None:
        try:
            backend = self.get_backend()
            with self.lock:
                data = {
                    "seen_fp": dict(self.seen_fp),
                    "seen_btc": dict(self.seen_btc),
                    "checked_urls": list(self.checked_urls),
                    "results": list(self.results),
                    "stats": dict(self.stats),
                    "queries": self.query_entry.get(),
                    "extra": self.extra_text.get("1.0", tk.END),
                    "success_count": self.success_count,
                    "total_count": self.total_count,
                    "total_newnym": self.total_newnym,
                    "pending_queue": list(self.pending_queue),
                    "dead_blacklist": dict(self.dead_blacklist),
                }
            backend.save(data)
            with self.lock:
                self.pending_results.clear()
                self.pending_fp.clear()
                self.pending_btc.clear()
                self.pending_checked.clear()
                self.pending_dead.clear()
            if not silent:
                self.log_msg(
                    f"[SAVE {self.backend_var.get()} full] {len(self.results)} találat",
                    force=True,
                    tag="save",
                )
        except Exception as e:
            if not silent:
                messagebox.showerror("Mentés hiba", str(e))
            else:
                self.log_msg(f"[SAVE HIBA] {e}", force=True, tag="error")

    def load_state(self, silent: bool = False) -> None:
        try:
            data = self.get_backend().load()
            if not data:
                if not silent:
                    self.log_msg(
                        f"[LOAD {self.backend_var.get()}] Nincs adat",
                        force=True,
                        tag="save",
                    )
                return
            with self.lock:
                self.seen_fp.clear()
                for k, v in data.get("seen_fp", {}).items():
                    self._cache_fp(k, v)
                self.seen_btc.clear()
                for k, v in data.get("seen_btc", {}).items():
                    self._cache_btc(k, v)
                self.checked_urls = set(data.get("checked_urls", []))
                self.results = data.get("results", [])
                self.stats = data.get(
                    "stats",
                    {"total": 0, "alive": 0, "clone": 0, "dead": 0, "filtered": 0},
                )
                self.success_count = data.get("success_count", 0)
                self.total_count = data.get("total_count", 0)
                self.total_newnym = data.get("total_newnym", 0)
                self.pending_queue = data.get("pending_queue", [])

            self.next_newnym_success = random.randint(
                int(self.success_threshold_var.get() * 0.8),
                int(self.success_threshold_var.get() * 1.2),
            )
            self.next_newnym_total = self.total_threshold_var.get()
            self.tree.delete(*self.tree.get_children())
            for r in self.results:
                ts_str = fmt_ts(r.get("ts"))
                tags = []
                l = r.get("lang", "en")
                if l in ("hu", "en", "de", "ru", "fr"):
                    tags.append(f"lang_{l}")
                if r.get("category") == "forum":
                    tags.append("cat_forum")
                self.tree.insert(
                    "",
                    tk.END,
                    values=(
                        r.get("title", ""),
                        r.get("url", ""),
                        r.get("lang", "en"),
                        r.get("category", "other"),
                        ts_str,
                        r.get("snippet", "")[:80],
                    ),
                    tags=tuple(tags),
                )
            self.lbl_unique.config(text=f"{len(self.results)}")
            self.lbl_checked.config(text=f"{len(self.checked_urls)}")
            self.lbl_newnym.config(text=f"NEWNYM: {self.total_newnym}")
            self.lbl_backend.config(text=f"Backend: {self.backend_var.get()}")
            self.update_counts_label()
            self.filters_panel.set_counts(
                len(self.results), len(self.results), 0
            )
            if data.get("queries"):
                self.query_entry.delete(0, tk.END)
                self.query_entry.insert(0, data["queries"])
            if data.get("extra"):
                self.extra_text.delete("1.0", tk.END)
                self.extra_text.insert("1.0", data["extra"])

            if self.pending_queue:
                self.btn_resume.config(state=tk.NORMAL)
                self.log_msg(f"[RESUME READY] {len(self.pending_queue)} folyamatban lévő cím folytatásra kész!", force=True, tag="save")

            self.log_msg(
                f"[LOAD {self.backend_var.get()}] {len(self.results)} találat",
                force=True,
                tag="save",
            )
            self.set_statusbar_color(
                "#2c3e50",
                msg=f"Betöltve [{self.backend_var.get()}]: {len(self.results)} egyedi",
            )
            with self.lock:
                self.pending_results.clear()
                self.pending_fp.clear()
                self.pending_btc.clear()
                self.pending_checked.clear()
                self.pending_dead.clear()
        except Exception as e:
            self.log_msg(
                f"[LOAD HIBA {self.backend_var.get()}] {e}",
                force=True,
                tag="error",
            )
            if not silent:
                messagebox.showerror("Betöltés hiba", str(e))

    def clear_state(self) -> None:
        if messagebox.askyesno(
            "Törlés", f"Minden mentés törlése? Backend: {self.backend_var.get()}"
        ):
            self.get_backend().clear()
            with self.lock:
                self.seen_fp.clear()
                self.seen_btc.clear()
                self.checked_urls.clear()
                self.in_progress_urls.clear()
                self.pending_queue.clear()
                self.results.clear()
                self.dead_blacklist.clear()
                self.pending_results.clear()
                self.pending_fp.clear()
                self.pending_btc.clear()
                self.pending_checked.clear()
                self.pending_dead.clear()
                self.success_count = 0
                self.total_count = 0
                self.stats = {
                    "total": 0,
                    "alive": 0,
                    "clone": 0,
                    "dead": 0,
                    "filtered": 0,
                }
            self.btn_resume.config(state=tk.DISABLED)
            self.tree.delete(*self.tree.get_children())
            for lbl in [
                self.lbl_total,
                self.lbl_checked,
                self.lbl_alive,
                self.lbl_dead,
                self.lbl_clone,
                self.lbl_unique,
                self.lbl_filtered,
            ]:
                try:
                    lbl.config(text="0")
                except Exception:
                    pass
            self.log_msg(
                f"[CLEAR {self.backend_var.get()}] Törölve", force=True, tag="save"
            )
            self.update_counts_label()
            self.set_statusbar_color("#2c3e50", msg="Törölve - készen")

    def on_close(self) -> None:
        if self.auto_save_var.get():
            self.save_state(silent=False)
        self.save_current_config()
        self.root.destroy()

    def show_context_menu(self, event: tk.Event) -> None:
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.update_inline_preview()
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def copy_to_clipboard(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def copy_selected_url(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        self.copy_to_clipboard(self.tree.item(sel[0])["values"][1])
        self.set_statusbar_color("#27ae60", msg="Vágólapra másolva!")

    def copy_all_urls(self) -> None:
        urls: List[str] = [self.tree.item(c)["values"][1] for c in self.tree.get_children()]
        if urls:
            self.copy_to_clipboard("\n".join(urls))
            self.set_statusbar_color("#27ae60", msg=f"{len(urls)} URL vágólapra!")

    def delete_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        url: str = self.tree.item(sel[0])["values"][1]
        with self.lock:
            self.results = [r for r in self.results if r["url"] != url]
        self.tree.delete(sel[0])
        if self.backend_var.get() == "sqlite":
            try:
                con = sqlite3.connect(DB_FILE)
                cur = con.cursor()
                cur.execute("DELETE FROM results WHERE url=?", (url,))
                con.commit()
                con.close()
            except Exception:
                pass
        self.log_msg(f"[DELETE] {url[:60]}", force=True, tag="dead")

    def open_export_dialog(self) -> None:
        """Open advanced export options dialog (scope, category filter, format)."""
        if not self.results:
            messagebox.showinfo("Export", "Nincs mit exportálni!")
            return

        win = tk.Toplevel(self.root)
        win.title("📦 Exportálás Testreszabása")
        win.geometry("450x380")
        win.resizable(False, False)

        ttk.Label(win, text="Találatok Exportálása", font=("TkDefaultFont", 11, "bold")).pack(pady=(12, 6))

        # Scope
        scope_frame = ttk.LabelFrame(win, text="Export Hatóköre", padding=8)
        scope_frame.pack(fill=tk.X, padx=16, pady=6)
        scope_var = tk.StringVar(value="filtered")
        ttk.Radiobutton(scope_frame, text=f"Jelenlegi szűrt nézet ({len(self.tree.get_children())} db)", variable=scope_var, value="filtered").pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(scope_frame, text=f"Összes egyedi találat ({len(self.results)} db)", variable=scope_var, value="all_unique").pack(anchor=tk.W, pady=2)

        # Filters
        filter_box = ttk.LabelFrame(win, text="Kategória & Nyelv szűkítés", padding=8)
        filter_box.pack(fill=tk.X, padx=16, pady=6)

        row_cat = ttk.Frame(filter_box)
        row_cat.pack(fill=tk.X, pady=2)
        ttk.Label(row_cat, text="Kategória:").pack(side=tk.LEFT)
        cat_combo = ttk.Combobox(row_cat, values=["all", "forum", "wiki", "library", "news", "market", "other"], state="readonly", width=12)
        cat_combo.set("all")
        cat_combo.pack(side=tk.RIGHT)

        row_lang = ttk.Frame(filter_box)
        row_lang.pack(fill=tk.X, pady=2)
        ttk.Label(row_lang, text="Nyelv:").pack(side=tk.LEFT)
        lang_combo = ttk.Combobox(row_lang, values=["all", "hu", "en", "de", "fr", "ru", "es", "other"], state="readonly", width=12)
        lang_combo.set("all")
        lang_combo.pack(side=tk.RIGHT)

        # Format
        fmt_frame = ttk.LabelFrame(win, text="Formátum", padding=8)
        fmt_frame.pack(fill=tk.X, padx=16, pady=6)
        fmt_var = tk.StringVar(value="csv")
        ttk.Radiobutton(fmt_frame, text="CSV (táblázatkezelőkhöz)", variable=fmt_var, value="csv").pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(fmt_frame, text="JSON (fejlesztőknek)", variable=fmt_var, value="json").pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(fmt_frame, text="TXT (egyszerű lista)", variable=fmt_var, value="txt").pack(side=tk.LEFT, padx=6)

        def _do_export() -> None:
            scope = scope_var.get()
            selected_cat = cat_combo.get()
            selected_lang = lang_combo.get()
            fmt = fmt_var.get()

            if scope == "filtered":
                source_urls = set(self.tree.item(c)["values"][1] for c in self.tree.get_children())
                candidates = [r for r in self.results if r.get("url") in source_urls]
            else:
                candidates = list(self.results)

            export_list = []
            for r in candidates:
                if selected_cat != "all" and r.get("category", "other") != selected_cat:
                    continue
                if selected_lang != "all" and r.get("lang", "en") != selected_lang:
                    continue
                export_list.append(r)

            if not export_list:
                messagebox.showwarning("Export", "A megadott szűrőkkel nem található találat!")
                return

            base = STATE_DIR
            if fmt == "txt":
                p = base / f"export_{int(time.time())}.txt"
                with open(p, "w", encoding="utf-8") as f:
                    for r in export_list:
                        f.write(f"{r['url']} # {r['title']} [{r.get('lang','')} {r.get('category','')}]\n")
            elif fmt == "csv":
                p = base / f"export_{int(time.time())}.csv"
                with open(p, "w", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=["url", "title", "snippet", "fp", "ts", "lang", "category"])
                    w.writeheader()
                    for r in export_list:
                        w.writerow({
                            "url": r["url"],
                            "title": r["title"],
                            "snippet": r.get("snippet", ""),
                            "fp": r.get("fp", ""),
                            "ts": fmt_ts(r.get("ts")),
                            "lang": r.get("lang", ""),
                            "category": r.get("category", ""),
                        })
            elif fmt == "json":
                p = base / f"export_{int(time.time())}.json"
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(export_list, f, ensure_ascii=False, indent=2)

            win.destroy()
            self.log_msg(f"[EXPORT {fmt.upper()}] Mentve: {p} ({len(export_list)} sor)", force=True, tag="save")
            self.set_statusbar_color("#2980b9", msg=f"Export kész: {len(export_list)} sor ({p.name})")
            messagebox.showinfo("Export kész", f"Sikeres exportálás:\n{p}\n\nÖsszesen: {len(export_list)} sor")

        btn_row = ttk.Frame(win)
        btn_row.pack(fill=tk.X, padx=16, pady=10)
        ttk.Button(btn_row, text="💾 Exportálás", command=_do_export).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(btn_row, text="Mégse", command=win.destroy).pack(side=tk.RIGHT, padx=2)

    def panic_wipe(self) -> None:
        """Emergency panic wipe: immediately halts workers and shreds all databases, logs, and state."""
        if not messagebox.askyesno(
            "🚨 PÁNIK TÖRLÉS VÉSZHELYZET",
            "BIZTOSAN MEGSEMMISÍTESZ MINDEN ADATOT?\n\n"
            "- Az összes mentett .onion cím, találat és metaadat törlődik.\n"
            "- A helyi adatbázis (onion.db), a konfiguráció és a naplók azonnal megsemmisülnek.\n"
            "- Ez a művelet visszavonhatatlan!",
        ):
            return

        self.running = False
        self.set_statusbar_color("#c0392b", msg="🚨 PÁNIK TÖRLÉS FOLYAMATBAN...")

        # 1. Purge all in-memory state
        with self.lock:
            self.seen_fp.clear()
            self.seen_btc.clear()
            self.checked_urls.clear()
            self.in_progress_urls.clear()
            self.pending_queue.clear()
            self.results.clear()
            self.dead_blacklist.clear()
            self.pending_results.clear()
            self.pending_fp.clear()
            self.pending_btc.clear()
            self.pending_checked.clear()
            self.pending_dead.clear()
            self.stats = {"total": 0, "alive": 0, "clone": 0, "dead": 0, "filtered": 0}
            self.success_count = 0
            self.total_count = 0

        # 2. Reset UI elements
        self.tree.delete(*self.tree.get_children())
        self.log_panel.clear()
        self.extra_text.delete("1.0", tk.END)
        self.prev_text.delete("1.0", tk.END)
        self.lbl_prev_title.config(text="Minden adat törölve.")
        self.lbl_prev_url.config(text="")
        self.lbl_prev_meta.config(text="")
        for lbl in [
            self.lbl_total,
            self.lbl_checked,
            self.lbl_alive,
            self.lbl_dead,
            self.lbl_clone,
            self.lbl_unique,
            self.lbl_filtered,
        ]:
            try:
                lbl.config(text="0")
            except Exception:
                pass
        self.btn_resume.config(state=tk.DISABLED)

        # 3. Secure file shredding (zeroing bytes then unlinking)
        def _shred_file(p: Path) -> None:
            if p.exists() and p.is_file():
                try:
                    size = p.stat().st_size
                    with open(p, "wb") as f:
                        f.write(b"\x00" * max(size, 1024))
                        f.flush()
                        os.fsync(f.fileno())
                    p.unlink()
                except Exception:
                    try:
                        p.unlink()
                    except Exception:
                        pass

        # Target all sensitive state files
        files_to_shred = [
            DB_FILE,
            Path(str(DB_FILE) + "-wal"),
            Path(str(DB_FILE) + "-shm"),
            STATE_DIR / "state_v3.json",
            STATE_DIR / "dead_blacklist.json",
            STATE_DIR / "config.json",
            STATE_DIR / ".storage.key",
        ]
        if hasattr(self, "sqlite_backend") and getattr(self.sqlite_backend, "db_file", None):
            db = Path(self.sqlite_backend.db_file)
            files_to_shred.extend([db, Path(str(db) + "-wal"), Path(str(db) + "-shm")])
        if hasattr(self, "json_backend"):
            if getattr(self.json_backend, "state_file", None):
                files_to_shred.append(Path(self.json_backend.state_file))
            if getattr(self.json_backend, "dead_file", None):
                files_to_shred.append(Path(self.json_backend.dead_file))
        if STATE_DIR.exists():
            for extra_f in STATE_DIR.glob("*"):
                if extra_f.is_file():
                    files_to_shred.append(extra_f)

        for f_path in files_to_shred:
            _shred_file(f_path)

        try:
            self.sqlite_backend.init_db()
        except Exception:
            pass

        self.log_msg("[PANIC] 🚨 Pánik törlés lefutott: minden adatbázis és állapotfájl megsemmisítve!", force=True, tag="dead")
        self.set_statusbar_color("#c0392b", msg="🚨 PÁNIK: MINDEN ADAT MEGSEMMISÍTVE")
        messagebox.showinfo(
            "Pánik Törlés Befejezve",
            "Minden adatbázis, napló, ujjlenyomat és beállítás véglegesen és biztonságosan megsemmisítve.",
        )

    def fetch_github_thread(self) -> None:
        def _run() -> None:
            proxy = f"socks5h://127.0.0.1:{self.port_var.get()}"
            allow_clearnet = self.allow_clearnet_var.get()
            found = self.fetcher.fetch_github_seeds(proxy_url=proxy, allow_clearnet=allow_clearnet)
            if not found and not allow_clearnet:
                self.log_msg(
                    "[SECURITY] GitHub seed letöltés blokkolva: Tor proxy nem elérhető és Clearnet tiltva!",
                    force=True,
                    tag="tor_err",
                )
                self.set_statusbar_color("#e67e22", msg="GitHub letöltés tiltva (Tor-only aktív)")
                return

            self.root.after(
                0,
                lambda: self.extra_text.insert(
                    tk.END, "\n".join(list(found)[:400]) + "\n"
                ),
            )
            self.log_msg(f"[GITHUB] {len(found)} cím letöltve (proxy: {proxy if proxy else 'clearnet'})", force=True, tag="save")

        threading.Thread(target=_run, daemon=True).start()

    def fetch_one(self, url: str, proxy_url: str) -> Dict[str, Any]:
        now_ts = time.time()
        with self.lock:
            if url in self.dead_blacklist:
                return {
                    "url": url,
                    "status": "dead_blacklisted",
                    "ts": now_ts,
                    "lang": "en",
                    "category": "other",
                }
            self.in_progress_urls.add(url)

        page = self.fetcher.fetch_page(
            url, proxy_url, is_running_cb=lambda: self.running
        )
        url_to_save: str = page.get("url", url)

        if page.get("status") == "canceled" or not self.running:
            with self.lock:
                self.in_progress_urls.discard(url)
            return {"url": url, "status": "canceled", "ts": now_ts}

        if page.get("status") == "dead":
            with self.lock:
                self.in_progress_urls.discard(url)
                self.dead_blacklist[url] = now_ts
                self.pending_dead[url] = now_ts
                if url not in self.checked_urls:
                    self.checked_urls.add(url)
                    if url not in self.pending_checked:
                        self.pending_checked.append(url)
            return page

        if page.get("status") == "empty":
            with self.lock:
                self.in_progress_urls.discard(url)
                if url not in self.checked_urls:
                    self.checked_urls.add(url)
                    if url not in self.pending_checked:
                        self.pending_checked.append(url)
            return page

        fp: str = page.get("fp", "")
        btc: List[str] = page.get("btc", [])
        lang: str = page.get("lang", "en")
        category: str = page.get("category", "other")
        title: str = page.get("title", "")
        text: str = page.get("text", "")
        snippet: str = page.get("snippet", "")

        if (
            self.filters_panel.enable_precise_var.get()
            and self.filters_panel.save_only_filtered_var.get()
        ):
            ok, reason = self.filters_panel.matches_precise(
                title, text, lang, category
            )
            if not ok:
                with self.lock:
                    self.in_progress_urls.discard(url)
                    if url not in self.checked_urls:
                        self.checked_urls.add(url)
                        if url not in self.pending_checked:
                            self.pending_checked.append(url)
                    self.stats["filtered"] = self.stats.get("filtered", 0) + 1
                return {
                    "url": url_to_save,
                    "status": "filtered",
                    "reason": reason,
                    "ts": now_ts,
                    "lang": lang,
                    "category": category,
                }

        is_fp_duplicate, fp_orig = self.is_fp_seen(fp)
        if is_fp_duplicate:
            with self.lock:
                self.in_progress_urls.discard(url)
                if url not in self.checked_urls:
                    self.checked_urls.add(url)
                    if url not in self.pending_checked:
                        self.pending_checked.append(url)
            return {
                "url": url_to_save,
                "status": "clone",
                "fp": fp,
                "ts": now_ts,
                "lang": lang,
                "category": category,
            }

        for b in btc:
            is_btc_duplicate, _ = self.is_btc_seen(b)
            if is_btc_duplicate:
                with self.lock:
                    self.in_progress_urls.discard(url)
                    if url not in self.checked_urls:
                        self.checked_urls.add(url)
                        if url not in self.pending_checked:
                            self.pending_checked.append(url)
                return {
                    "url": url_to_save,
                    "status": "clone_btc",
                    "ts": now_ts,
                    "lang": lang,
                    "category": category,
                }

        with self.lock:
            self.in_progress_urls.discard(url)
            self._cache_fp(fp, url_to_save)
            self.pending_fp[fp] = url_to_save
            for b in btc:
                self._cache_btc(b, url_to_save)
                self.pending_btc[b] = url_to_save

            result = {
                "title": title,
                "url": url_to_save,
                "snippet": snippet,
                "fp": fp,
                "ts": now_ts,
                "lang": lang,
                "category": category,
            }
            self.results.append(result)
            self.pending_results.append(result)
            if url not in self.checked_urls:
                self.checked_urls.add(url)
            if url not in self.pending_checked:
                self.pending_checked.append(url)

        return {
            "url": url_to_save,
            "status": "unique",
            "title": title,
            "snippet": snippet,
            "fp": fp,
            "ts": now_ts,
            "lang": lang,
            "category": category,
        }

    def start_thread(self) -> None:
        """Start fresh search from Ahmia queries + extra onions."""
        if self.running:
            return
        self.start_time = time.time()
        self.set_statusbar_color("#2980b9", msg="Keresés indítása...")
        
        raw_q = self.query_entry.get()
        extra_raw = self.extra_text.get("1.0", tk.END)
        workers = self.worker_var.get()
        backend = self.backend_var.get()
        auto_save = self.auto_save_var.get()
        port = self.port_var.get()
        auto_newnym_success = self.auto_newnym_success_var.get()
        auto_newnym_total = self.auto_newnym_total_var.get()
        
        self.btn_start.config(state=tk.DISABLED)
        self.btn_resume.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        
        threading.Thread(target=lambda: self.run_search(
            resume_queue=False, raw_q=raw_q, extra_raw=extra_raw, 
            workers=workers, backend=backend, auto_save=auto_save, port=port,
            auto_newnym_success=auto_newnym_success, auto_newnym_total=auto_newnym_total
        ), daemon=True).start()

    def resume_thread(self) -> None:
        """Resume search directly from existing pending_queue."""
        if self.running or not self.pending_queue:
            return
        self.start_time = time.time()
        self.set_statusbar_color("#2980b9", msg=f"Keresés folytatása ({len(self.pending_queue)} URL)...")
        
        raw_q = self.query_entry.get()
        extra_raw = self.extra_text.get("1.0", tk.END)
        workers = self.worker_var.get()
        backend = self.backend_var.get()
        auto_save = self.auto_save_var.get()
        port = self.port_var.get()
        auto_newnym_success = self.auto_newnym_success_var.get()
        auto_newnym_total = self.auto_newnym_total_var.get()
        
        self.btn_start.config(state=tk.DISABLED)
        self.btn_resume.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        
        threading.Thread(target=lambda: self.run_search(
            resume_queue=True, raw_q=raw_q, extra_raw=extra_raw, 
            workers=workers, backend=backend, auto_save=auto_save, port=port,
            auto_newnym_success=auto_newnym_success, auto_newnym_total=auto_newnym_total
        ), daemon=True).start()

    def stop(self) -> None:
        """Immediately flag stop and update UI without getting stuck."""
        self.running = False
        self.set_statusbar_color("#e67e22", msg="Leállítás folyamatban...")
        self.log_msg("[STOP] Leállítás kérve...", force=True, tag="tor_err")

    def run_search(self, resume_queue: bool = False, raw_q: str = "", extra_raw: str = "", workers: int = 10, backend: str = "JSON", auto_save: bool = True, port: str = "9050", auto_newnym_success: bool = False, auto_newnym_total: bool = False) -> None:
        self.running = True
        proxy = f"socks5h://127.0.0.1:{port}"

        if resume_queue and self.pending_queue:
            new_urls = [u for u in self.pending_queue if u not in self.checked_urls and u not in self.dead_blacklist]
            all_onions_count = len(new_urls) + len(self.checked_urls)
            self.log_msg(f"[RESUME] Folytatás {len(new_urls)} hátralévő URL-lel", force=True, tag="start")
        else:
            queries = []
            current = ""
            in_quote = False
            for ch in raw_q:
                if ch == '"':
                    in_quote = not in_quote
                    current += ch
                elif ch == "," and not in_quote:
                    if current.strip():
                        queries.append(current.strip())
                    current = ""
                else:
                    current += ch
            if current.strip():
                queries.append(current.strip())

            extra = set(
                re.findall(r"https?://[a-z2-7]{16,56}\.onion[^\s]*", extra_raw)
            )
            extra.update(
                [f"http://{m}" for m in re.findall(r"[a-z2-7]{56}\.onion", extra_raw)]
            )
            all_onions = set(extra)

            ahmia_onions = self.fetcher.search_ahmia(
                queries,
                proxy_url=proxy,
                allow_clearnet=self.allow_clearnet_var.get(),
                is_running_cb=lambda: self.running,
            )
            ose_onions = self.fetcher.search_onionsearchengine(
                queries, is_running_cb=lambda: self.running
            )
            all_onions.update(ahmia_onions)
            all_onions.update(ose_onions)

            new_urls = [
                u
                for u in all_onions
                if u not in self.checked_urls and u not in self.dead_blacklist
            ]
            all_onions_count = len(all_onions)
            self.log_msg(
                f"[START {backend}] {len(all_onions)} összes, "
                f"{len(self.checked_urls)} ellenőrizve, {len(new_urls)} új, {workers} worker",
                force=True,
                tag="start",
            )

        total = len(new_urls)
        with self.lock:
            self.stats["total"] = all_onions_count
            self.pending_queue = list(new_urls)

        def _setup_ui():
            self.progress.config(maximum=total if total else 1, value=0)
            self.lbl_total.config(text=f"{all_onions_count}")
        self.root.after(0, _setup_ui)

        completed = 0

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.fetch_one, url, proxy): url
                for url in new_urls
            }
            for fut in as_completed(futures):
                url_finished = futures.get(fut)
                if not self.running:
                    for f in futures:
                        f.cancel()
                    break

                res = fut.result()
                if res.get("status") == "canceled":
                    continue

                completed += 1
                with self.lock:
                    if url_finished in self.pending_queue:
                        self.pending_queue.remove(url_finished)

                is_success = res["status"] in ("unique", "clone", "clone_btc")
                with self.lock:
                    if res["status"] == "unique":
                        self.stats["alive"] = self.stats.get("alive", 0) + 1
                    elif res["status"] in ("dead", "dead_blacklisted", "empty"):
                        self.stats["dead"] = self.stats.get("dead", 0) + 1
                    elif "clone" in res["status"]:
                        self.stats["clone"] = self.stats.get("clone", 0) + 1
                        self.stats["alive"] = self.stats.get("alive", 0) + 1
                    elif res["status"] == "filtered":
                        self.stats["filtered"] = (
                            self.stats.get("filtered", 0) + 1
                        )

                self.check_auto_newnym(is_success=is_success, auto_newnym_success=auto_newnym_success, auto_newnym_total=auto_newnym_total)

                def _update(res=res, comp=completed):
                    pct = int(comp / total * 100) if total else 0
                    elapsed = (
                        time.time() - self.start_time if self.start_time else 1
                    )
                    speed = comp / elapsed if elapsed > 0 else 0
                    self.progress.config(value=comp)
                    self.lbl_percent.config(text=f"{pct}%")
                    self.lbl_speed.config(
                        text=f"{speed:.1f} req/s | {comp}/{total}"
                    )
                    with self.lock:
                        total_s = self.stats.get("total", 0)
                        alive_s = self.stats.get("alive", 0)
                        dead_s = self.stats.get("dead", 0)
                        clone_s = self.stats.get("clone", 0)
                        filt_s = self.stats.get("filtered", 0)
                        checked_len = len(self.checked_urls)
                        results_len = len(self.results)
                    self.lbl_total.config(text=f"{total_s}")
                    self.lbl_checked.config(text=f"{checked_len}")
                    self.lbl_alive.config(text=f"{alive_s}")
                    self.lbl_dead.config(text=f"{dead_s}")
                    self.lbl_clone.config(text=f"{clone_s}")
                    self.lbl_unique.config(text=f"{results_len}")
                    self.lbl_filtered.config(text=f"{filt_s}")

                    if res["status"] == "unique":
                        ts_str = fmt_ts(res.get("ts"))
                        visible, _ = self.filters_panel.is_item_visible(res)
                        if visible:
                            tags = []
                            l = res.get("lang", "en")
                            if l in ("hu", "en", "de", "ru", "fr"):
                                tags.append(f"lang_{l}")
                            if res.get("category") == "forum":
                                tags.append("cat_forum")
                            self.tree.insert(
                                "",
                                tk.END,
                                values=(
                                    res["title"],
                                    res["url"],
                                    res.get("lang", ""),
                                    res.get("category", ""),
                                    ts_str,
                                    res["snippet"],
                                ),
                                tags=tuple(tags),
                            )
                        self.log_msg(
                            f"[OK] {res['title']} [{res.get('lang','')}/{res.get('category','')}] - {res['url'][:50]}",
                            tag="ok",
                        )
                    elif res["status"] == "filtered":
                        self.log_msg(
                            f"[PRECISE FILTER] {res['url'][:60]} -> {res.get('reason','')}",
                            tag="filter",
                        )
                    elif "clone" in res["status"]:
                        self.log_msg(f"[CLONE] {res['url'][:60]}", tag="clone")
                    else:
                        if res["status"] == "dead":
                            self.log_msg(
                                f"[-] HALOTT: {res['url'][:60]} ({res.get('code','')})",
                                tag="dead",
                            )
                    if comp % 10 == 0 and auto_save:
                        self.save_incremental_pending()

                self.root.after(0, _update)

        with self.lock:
            self.in_progress_urls.clear()
            self.stats["total"] = all_onions_count

        self.save_state(silent=False)
        self.save_deadlist()

        def _finish_ui() -> None:
            self.lbl_total.config(text=f"{all_onions_count}")
            self.lbl_checked.config(text=f"{len(self.checked_urls)}")
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            if self.pending_queue:
                self.btn_resume.config(state=tk.NORMAL)
            else:
                self.btn_resume.config(state=tk.DISABLED)

            if not self.running:
                self.set_statusbar_color(
                    "#e67e22",
                    msg=f"Leállítva — {completed}/{total} feldolgozva | {len(self.pending_queue)} vár folytatásra",
                )
                self.lbl_speed.config(text=f"Leállítva: {completed}/{total}")
            else:
                self.set_statusbar_color(
                    "#27ae60",
                    msg=f"Kész! {len(self.results)} egyedi | NEWNYM: {self.total_newnym}",
                )

        self.root.after(0, _finish_ui)
        self.running = False


# Backward compatibility
OnionGUI = MainWindow
