"""
Main application window coordinating UI components, search lifecycle, and persistence.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import json
import random
import sqlite3
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from onion_search.core.detector import ContentDetector
from onion_search.core.fetcher import OnionFetcher
from onion_search.core.neonym import TorController
from onion_search.storage.json_backend import JSONBackend
from onion_search.storage.sqlite_backend import SQLiteBackend
from onion_search.ui.filters import FilterPanel
from onion_search.ui.log_panel import LogPanel
from onion_search.utils.helpers import DB_FILE, STATE_DIR, fmt_ts


class MainWindow:
    """Main window for Onion Kereso."""

    def __init__(
        self,
        root,
        fetcher=None,
        detector=None,
        tor_controller=None,
        sqlite_backend=None,
        json_backend=None,
    ):
        self.root = root
        self.root.title("Onion Kereso v4.8 - secure & stable")
        self.root.geometry("1350x920")

        # Injected dependencies with default fallback
        self.detector = detector or ContentDetector()
        self.sqlite_backend = sqlite_backend or SQLiteBackend()
        self.json_backend = json_backend or JSONBackend()
        self.fetcher = fetcher or OnionFetcher(detector=self.detector)
        self.tor_controller = tor_controller or TorController(
            on_sessions_reset=self.fetcher.session_manager.close_all
        )

        # In-memory application state
        self.seen_fp = {}
        self.seen_btc = {}
        self.checked_urls = set()
        self.dead_blacklist = {}
        self.results = []
        self.running = False
        self.lock = threading.Lock()
        self.stats = {"total": 0, "alive": 0, "clone": 0, "dead": 0, "filtered": 0}

        self.success_count = 0
        self.total_count = 0
        self.last_newnym = 0
        self.start_time = 0
        self.next_newnym_success = random.randint(40, 60)
        self.next_newnym_total = 100
        self.total_newnym = 0

        self.pending_results = []
        self.pending_fp = {}
        self.pending_btc = {}
        self.pending_checked = []
        self.pending_dead = {}

        # Tkinter variables
        self.backend_var = tk.StringVar(value="sqlite")
        self.auto_newnym_success_var = tk.BooleanVar(value=True)
        self.auto_newnym_total_var = tk.BooleanVar(value=True)
        self.success_threshold_var = tk.IntVar(value=50)
        self.total_threshold_var = tk.IntVar(value=100)
        self.auto_save_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Készen - v4.8 secure")

        # Build UI layout
        self.setup_styles()
        self.setup_ui()

        # Initialize state & Tor checks
        self.load_state(silent=True)
        self.load_deadlist()

        # Event bindings
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Control-s>", lambda e: self.save_state(silent=False))
        self.root.bind("<Control-n>", lambda e: self.manual_newnym_thread())
        self.root.bind("<Control-f>", lambda e: self.apply_filters())

        threading.Thread(target=self.check_tor_on_startup, daemon=True).start()

    def get_backend(self):
        return (
            self.sqlite_backend
            if self.backend_var.get() == "sqlite"
            else self.json_backend
        )

    def setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "green.Horizontal.TProgressbar",
            background="#2ecc71",
            troughcolor="#ecf0f1",
        )

    def setup_ui(self):
        # 1. Top toolbar
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Ahmia szavak:").pack(side=tk.LEFT)
        self.query_entry = ttk.Entry(top, width=20)
        self.query_entry.insert(0, "forum, board, wiki, library")
        self.query_entry.pack(side=tk.LEFT, padx=4)

        ttk.Label(top, text="Tor:").pack(side=tk.LEFT, padx=(5, 0))
        self.port_var = tk.StringVar(value="9050")
        ttk.Combobox(
            top, textvariable=self.port_var, values=["9050", "9150"], width=5
        ).pack(side=tk.LEFT)

        ttk.Label(top, text="Ctrl:").pack(side=tk.LEFT, padx=(5, 0))
        self.ctrl_port_var = tk.StringVar(value="9051")
        ttk.Combobox(
            top, textvariable=self.ctrl_port_var, values=["9051", "9151"], width=5
        ).pack(side=tk.LEFT)

        ttk.Label(top, text="Workers:").pack(side=tk.LEFT, padx=(5, 0))
        self.worker_var = tk.IntVar(value=6)
        ttk.Spinbox(
            top, from_=2, to=10, textvariable=self.worker_var, width=4
        ).pack(side=tk.LEFT)

        ttk.Label(top, text="Backend:").pack(side=tk.LEFT, padx=(8, 0))
        self.backend_combo = ttk.Combobox(
            top,
            textvariable=self.backend_var,
            values=["sqlite", "json"],
            width=7,
            state="readonly",
        )
        self.backend_combo.pack(side=tk.LEFT)
        self.backend_combo.bind(
            "<<ComboboxSelected>>", lambda e: self.on_backend_switch()
        )

        persist = ttk.Frame(top)
        persist.pack(side=tk.RIGHT)
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
        self.filters_panel.pack(fill=tk.X)

        # 4. Main body (left = controls, stats, logs; right = results treeview)
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

        # 5. Right side (Treeview and export toolbar)
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

        export_frame = ttk.LabelFrame(cf, text="Export")
        export_frame.pack(side=tk.LEFT, padx=8)
        ttk.Button(
            export_frame,
            text="TXT",
            command=lambda: self.export_file("txt"),
            width=4,
        ).pack(side=tk.LEFT, padx=1)
        ttk.Button(
            export_frame,
            text="CSV",
            command=lambda: self.export_file("csv"),
            width=4,
        ).pack(side=tk.LEFT, padx=1)
        ttk.Button(
            export_frame,
            text="JSON",
            command=lambda: self.export_file("json"),
            width=5,
        ).pack(side=tk.LEFT, padx=1)
        ttk.Button(cf, text="🔍 SQL", command=self.open_sql_query).pack(
            side=tk.LEFT, padx=4
        )

        cols = ("title", "url", "lang", "category", "last_check", "info")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=25)
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
        self.context_menu.add_command(label="🗑 Törlés", command=self.delete_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="🔄 NEWNYM most (Ctrl+N)", command=self.manual_newnym_thread
        )
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Double-1>", lambda e: self.copy_selected_url())

    def log_msg(self, msg, force=False, tag=None):
        """Proxy to LogPanel for backward compatibility and thread safety."""
        self.log_panel.log_msg(msg, force=force, tag=tag)

    def set_led(self, canvas, led_id, color):
        def _do():
            canvas.itemconfig(led_id, fill=color)

        self.root.after(0, _do)

    def set_statusbar_color(self, bg, fg="white", msg=None):
        def _do():
            self.status_bar.config(bg=bg)
            self.lbl_statusbar.config(bg=bg, fg=fg)
            if msg:
                self.status_var.set(msg)

        self.root.after(0, _do)

    def apply_filters(self):
        """Refresh TreeView based on current quick and precise filters."""
        self.tree.delete(*self.tree.get_children())
        shown = 0
        filtered_out = 0
        for r in self.results:
            visible, _ = self.filters_panel.is_item_visible(r)
            if not visible:
                filtered_out += 1
                continue
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
            force=True,
            tag="filter",
        )

    def reset_counters(self):
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

    def update_counts_label(self):
        self.root.after(
            0,
            lambda: self.lbl_counts.config(
                text=(
                    f"Sikeres: {self.success_count}/{self.next_newnym_success} | "
                    f"Összes: {self.total_count}/{self.next_newnym_total}"
                )
            ),
        )

    def auto_detect_tor(self):
        self.log_msg("[TOR AUTO-DETECT] Keresés 9050/9150...", force=True, tag="start")
        self.set_statusbar_color("#f39c12", msg="Tor auto-detect 9050/9150...")

        def _run():
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

            def _update():
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

    def check_tor_on_startup(self):
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
        if not socks_ok:
            self.log_msg(
                "[TOR TIPP] 1) Tor Browser legyen NYITVA! 2) pip install pysocks",
                force=True,
                tag="error",
            )

        def _update():
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

    def on_backend_switch(self):
        backend = self.backend_var.get()
        self.lbl_backend.config(text=f"Backend: {backend}")
        self.log_msg(f"[BACKEND] Váltás: {backend}", force=True, tag="save")
        self.load_state(silent=False)
        self.load_deadlist()

    def open_sql_query(self):
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

        def is_safe_select(q):
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
            import re

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

        def run_q():
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

    def do_newnym(self, reason="manual"):
        ctrl_port = int(self.ctrl_port_var.get() or 9051)
        now = time.time()
        if reason.startswith("auto") and now - self.last_newnym < 12:
            self.log_msg(
                f"[NEWNYM] Auto skip - {now-self.last_newnym:.1f}s < 12s",
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

    def manual_newnym_thread(self):
        threading.Thread(
            target=lambda: self.do_newnym(reason="manual"), daemon=True
        ).start()

    def check_auto_newnym(self, is_success=False):
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
        if self.auto_newnym_success_var.get() and sc >= n_s:
            should_trigger = True
            reason = f"auto sikeres {sc}/{n_s}"
        if (
            not should_trigger
            and self.auto_newnym_total_var.get()
            and tc >= n_t
        ):
            should_trigger = True
            reason = f"auto osszes {tc}/{n_t}"
        if should_trigger:
            if now - self.last_newnym >= 15:
                self.log_msg(
                    f"[NEWNYM] Auto trigger: {reason}", force=True, tag="newnym"
                )
                threading.Thread(
                    target=lambda r=reason: self.do_newnym(reason=r), daemon=True
                ).start()
            else:
                self.log_msg(
                    f"[NEWNYM] Auto var - {now-self.last_newnym:.1f}s < 15s",
                    tag="newnym",
                )

    def load_deadlist(self):
        self.dead_blacklist = self.get_backend().load_dead()

    def save_deadlist(self):
        self.get_backend().save_dead(self.dead_blacklist)

    def save_state(self, silent=False):
        try:
            backend = self.get_backend()
            if (
                silent
                and self.backend_var.get() == "sqlite"
                and (self.pending_results or self.pending_checked)
            ):
                pending = {
                    "results": self.pending_results,
                    "seen_fp": self.pending_fp,
                    "seen_btc": self.pending_btc,
                    "checked_urls": self.pending_checked,
                    "stats": self.stats,
                }
                backend.save_pending(pending)
                if pending.get("results"):
                    self.log_msg(
                        f"[SAVE sqlite incremental] {len(pending['results'])} uj találat",
                        force=True,
                        tag="save",
                    )
                if self.pending_dead:
                    backend.save_dead_pending(self.pending_dead)
                with self.lock:
                    self.pending_results = []
                    self.pending_fp = {}
                    self.pending_btc = {}
                    self.pending_checked = []
                    self.pending_dead = {}
                return

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
                    "dead_blacklist": dict(self.dead_blacklist),
                }
            backend.save(data)
            with self.lock:
                self.pending_results = []
                self.pending_fp = {}
                self.pending_btc = {}
                self.pending_checked = []
                self.pending_dead = {}
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

    def load_state(self, silent=False):
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
                self.seen_fp = data.get("seen_fp", {})
                self.seen_btc = data.get("seen_btc", {})
                self.checked_urls = set(data.get("checked_urls", []))
                self.results = data.get("results", [])
                self.stats = data.get(
                    "stats",
                    {"total": 0, "alive": 0, "clone": 0, "dead": 0, "filtered": 0},
                )
                self.success_count = data.get("success_count", 0)
                self.total_count = data.get("total_count", 0)
                self.total_newnym = data.get("total_newnym", 0)

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
                self.pending_results = []
                self.pending_fp = {}
                self.pending_btc = {}
                self.pending_checked = []
                self.pending_dead = {}
        except Exception as e:
            self.log_msg(
                f"[LOAD HIBA {self.backend_var.get()}] {e}",
                force=True,
                tag="error",
            )
            if not silent:
                messagebox.showerror("Betöltés hiba", str(e))

    def clear_state(self):
        if messagebox.askyesno(
            "Törlés", f"Minden mentés törlése? Backend: {self.backend_var.get()}"
        ):
            self.get_backend().clear()
            with self.lock:
                self.seen_fp.clear()
                self.seen_btc.clear()
                self.checked_urls.clear()
                self.results.clear()
                self.dead_blacklist.clear()
                self.pending_results = []
                self.pending_fp = {}
                self.pending_btc = {}
                self.pending_checked = []
                self.pending_dead = {}
                self.success_count = 0
                self.total_count = 0
                self.stats = {
                    "total": 0,
                    "alive": 0,
                    "clone": 0,
                    "dead": 0,
                    "filtered": 0,
                }
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

    def on_close(self):
        if self.auto_save_var.get():
            self.save_state(silent=False)
        self.root.destroy()

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def copy_selected_url(self):
        sel = self.tree.selection()
        if not sel:
            return
        self.copy_to_clipboard(self.tree.item(sel[0])["values"][1])
        self.set_statusbar_color("#27ae60", msg="Vágólapra másolva!")

    def copy_all_urls(self):
        urls = [self.tree.item(c)["values"][1] for c in self.tree.get_children()]
        if urls:
            self.copy_to_clipboard("\n".join(urls))
            self.set_statusbar_color("#27ae60", msg=f"{len(urls)} URL vágólapra!")

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        url = self.tree.item(sel[0])["values"][1]
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

    def export_file(self, fmt="txt"):
        if not self.results:
            messagebox.showinfo("Export", "Nincs mit exportálni")
            return
        base = STATE_DIR
        filtered = []
        for r in self.results:
            visible, _ = self.filters_panel.is_item_visible(r)
            if visible:
                filtered.append(r)

        if fmt == "txt":
            p = base / "export.txt"
            with open(p, "w", encoding="utf-8") as f:
                for r in filtered:
                    f.write(
                        f"{r['url']} # {r['title']} [{r.get('lang','')} {r.get('category','')}]\n"
                    )
        elif fmt == "csv":
            p = base / "export.csv"
            with open(p, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(
                    f,
                    fieldnames=[
                        "url",
                        "title",
                        "snippet",
                        "fp",
                        "ts",
                        "lang",
                        "category",
                    ],
                )
                w.writeheader()
                for r in filtered:
                    w.writerow(
                        {
                            "url": r["url"],
                            "title": r["title"],
                            "snippet": r.get("snippet", ""),
                            "fp": r.get("fp", ""),
                            "ts": fmt_ts(r.get("ts")),
                            "lang": r.get("lang", ""),
                            "category": r.get("category", ""),
                        }
                    )
        elif fmt == "json":
            p = base / "export.json"
            with open(p, "w", encoding="utf-8") as f:
                json.dump(filtered, f, ensure_ascii=False, indent=2)

        self.log_msg(
            f"[EXPORT {fmt.upper()}] {p} ({len(filtered)} sor)",
            force=True,
            tag="save",
        )
        messagebox.showinfo("Export", f"Export kész: {p}\n{len(filtered)} sor")
        self.set_statusbar_color(
            "#2980b9", msg=f"Export {fmt.upper()} kész: {len(filtered)} sor"
        )

    def fetch_github_thread(self):
        def _run():
            found = self.fetcher.fetch_github_seeds()
            self.root.after(
                0,
                lambda: self.extra_text.insert(
                    tk.END, "\n".join(list(found)[:400]) + "\n"
                ),
            )
            self.log_msg(f"[GITHUB] {len(found)} cím", force=True, tag="save")

        threading.Thread(target=_run, daemon=True).start()

    def fetch_one(self, url, proxy_url):
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

        page = self.fetcher.fetch_page(url, proxy_url)
        url_to_save = page.get("url", url)

        if page.get("status") == "dead":
            with self.lock:
                self.dead_blacklist[url] = now_ts
                self.pending_dead[url] = now_ts
                if url not in self.checked_urls:
                    self.checked_urls.add(url)
                    if url not in self.pending_checked:
                        self.pending_checked.append(url)
            return page

        if page.get("status") == "empty":
            with self.lock:
                if url not in self.checked_urls:
                    self.checked_urls.add(url)
                    if url not in self.pending_checked:
                        self.pending_checked.append(url)
            return page

        # Content filtering check
        fp = page.get("fp", "")
        btc = page.get("btc", [])
        lang = page.get("lang", "en")
        category = page.get("category", "other")
        title = page.get("title", "")
        text = page.get("text", "")
        snippet = page.get("snippet", "")

        if (
            self.filters_panel.enable_precise_var.get()
            and self.filters_panel.save_only_filtered_var.get()
        ):
            ok, reason = self.filters_panel.matches_precise(
                title, text, lang, category
            )
            if not ok:
                with self.lock:
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

        with self.lock:
            if fp in self.seen_fp:
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
                if b in self.seen_btc:
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
            self.seen_fp[fp] = url_to_save
            self.pending_fp[fp] = url_to_save
            for b in btc:
                self.seen_btc[b] = url_to_save
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

    def start_thread(self):
        if self.running:
            return
        self.start_time = time.time()
        self.set_statusbar_color("#2980b9", msg="Keresés indítása...")
        threading.Thread(target=self.run_search, daemon=True).start()

    def stop(self):
        self.running = False
        self.set_statusbar_color("#e67e22", msg="Leállítás kérve...")
        self.log_msg("[STOP] Leállítás kérve...", force=True, tag="tor_err")

    def run_search(self):
        import re

        self.running = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        proxy = f"socks5h://127.0.0.1:{self.port_var.get()}"

        raw_q = self.query_entry.get()
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

        extra_raw = self.extra_text.get("1.0", tk.END)
        extra = set(
            re.findall(r"https?://[a-z2-7]{16,56}\.onion[^\s]*", extra_raw)
        )
        extra.update(
            [f"http://{m}" for m in re.findall(r"[a-z2-7]{56}\.onion", extra_raw)]
        )
        all_onions = set(extra)

        ahmia_onions = self.fetcher.search_ahmia(
            queries, is_running_cb=lambda: self.running
        )
        all_onions.update(ahmia_onions)

        new_urls = [
            u
            for u in all_onions
            if u not in self.checked_urls and u not in self.dead_blacklist
        ]
        total = len(new_urls)
        self.log_msg(
            f"[START {self.backend_var.get()}] {len(all_onions)} összes, "
            f"{len(self.checked_urls)} ellenőrizve, {total} új, {self.worker_var.get()} worker",
            force=True,
            tag="start",
        )
        self.progress.config(maximum=total if total else 1)
        with self.lock:
            self.stats["total"] = len(all_onions)

        workers = self.worker_var.get()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.fetch_one, url, proxy): url
                for url in new_urls
            }
            completed = 0
            for fut in as_completed(futures):
                if not self.running:
                    for f in futures:
                        f.cancel()
                    break
                res = fut.result()
                completed += 1
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
                self.check_auto_newnym(is_success=is_success)

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
                    if comp % 10 == 0 and self.auto_save_var.get():
                        self.save_state(silent=True)

                self.root.after(0, _update)

        self.save_state(silent=False)
        self.save_deadlist()
        self.set_statusbar_color(
            "#27ae60",
            msg=f"Kész! {len(self.results)} egyedi | NEWNYM: {self.total_newnym}",
        )
        self.running = False
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)


# Alias for backward compatibility
OnionGUI = MainWindow
