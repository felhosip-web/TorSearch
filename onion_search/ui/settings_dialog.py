# Copyright 2026 HES Projects by FePe
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Comprehensive tabbed Settings Dialog for Onion Search.
Provides user-friendly configuration for Tor network, crawler performance,
content filtering, database storage, and general UX settings.
Developed by HES Projects by FePe.
"""
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, Optional, Tuple

from onion_search.config import (
    DB_FILE,
    AppConfig,
    ConfigManager,
)


class SettingsDialog:
    """Tabbed Modal Settings Dialog integrating with AppConfig."""

    def __init__(
        self,
        parent: tk.Tk,
        config_manager: Optional[ConfigManager] = None,
        on_save_callback: Optional[Callable[[AppConfig], None]] = None,
        on_run_diagnostics_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self.parent = parent
        self.config_manager = config_manager or ConfigManager()
        self.cfg: AppConfig = self.config_manager.config
        self.on_save_callback = on_save_callback
        self.on_run_diagnostics_callback = on_run_diagnostics_callback

        self.win = tk.Toplevel(self.parent)
        self.win.title("⚙️ Beállítások — Onion Kereső")
        self.win.geometry("640x580")
        self.win.resizable(False, False)
        self.win.grab_set()

        # Tkinter Form Variables initialized from AppConfig
        self.init_variables()

        # UI Layout Construction
        self.setup_ui()

    def init_variables(self) -> None:
        cfg = self.cfg
        # Tab 1: Tor / Network
        self.socks_host_var = tk.StringVar(value=getattr(cfg, "socks_host", "127.0.0.1"))
        self.socks_port_var = tk.StringVar(value=str(getattr(cfg, "socks_port", "9050")))
        self.ctrl_port_var = tk.StringVar(value=str(getattr(cfg, "ctrl_port", "9051")))
        self.tor_tcp_timeout_var = tk.DoubleVar(value=float(getattr(cfg, "tor_tcp_timeout", 2.0)))
        self.tor_socks_timeout_var = tk.DoubleVar(value=float(getattr(cfg, "tor_socks_timeout", 4.0)))
        self.auto_newnym_success_var = tk.BooleanVar(value=bool(getattr(cfg, "auto_newnym_success", True)))
        self.auto_newnym_total_var = tk.BooleanVar(value=bool(getattr(cfg, "auto_newnym_total", True)))
        self.success_threshold_var = tk.IntVar(value=int(getattr(cfg, "success_threshold", 50)))
        self.total_threshold_var = tk.IntVar(value=int(getattr(cfg, "total_threshold", 100)))

        # Tab 2: Crawler / Performance
        self.workers_var = tk.IntVar(value=int(getattr(cfg, "workers", 6)))
        self.domain_delay_var = tk.DoubleVar(value=float(getattr(cfg, "domain_delay", 0.7)))
        self.timeout_get_var = tk.IntVar(value=int(getattr(cfg, "timeout_get", 20)))
        self.max_crawl_depth_var = tk.IntVar(value=int(getattr(cfg, "max_crawl_depth", 2)))
        self.max_links_per_page_var = tk.IntVar(value=int(getattr(cfg, "max_links_per_page", 100)))
        self.user_agent_rotate_var = tk.BooleanVar(value=bool(getattr(cfg, "user_agent_rotate", True)))

        # Tab 3: Filtering & Content
        self.default_language_var = tk.StringVar(value=str(getattr(cfg, "default_language", "all")))
        self.default_category_var = tk.StringVar(value=str(getattr(cfg, "default_category", "all")))
        self.fingerprint_sensitivity_var = tk.StringVar(value=str(getattr(cfg, "fingerprint_sensitivity", "medium")))
        self.dead_link_recheck_hours_var = tk.DoubleVar(value=float(getattr(cfg, "dead_link_recheck_hours", 24.0)))
        self.normalize_to_host_only_var = tk.BooleanVar(value=bool(getattr(cfg, "normalize_to_host_only", False)))

        # Tab 4: Database & Storage
        self.backend_var = tk.StringVar(value=str(getattr(cfg, "backend", "sqlite")))
        self.encrypt_storage_var = tk.BooleanVar(value=bool(getattr(cfg, "encrypt_storage", False)))
        self.auto_cleanup_dead_var = tk.BooleanVar(value=bool(getattr(cfg, "auto_cleanup_dead", False)))
        self.export_default_format_var = tk.StringVar(value=str(getattr(cfg, "export_default_format", "csv")))

        # Tab 5: General & UX
        self.auto_update_seeds_var = tk.BooleanVar(value=bool(getattr(cfg, "auto_update_seeds", True)))
        self.auto_tor_diagnostics_var = tk.BooleanVar(value=bool(getattr(cfg, "auto_tor_diagnostics_on_startup", True)))
        self.auto_save_var = tk.BooleanVar(value=bool(getattr(cfg, "auto_save", True)))
        self.dark_mode_var = tk.BooleanVar(value=bool(getattr(cfg, "dark_mode", True)))
        self.minimize_to_tray_var = tk.BooleanVar(value=bool(getattr(cfg, "minimize_to_tray", False)))
        self.health_check_cache_ttl_var = tk.DoubleVar(value=float(getattr(cfg, "health_check_cache_ttl", 600.0)))
        self.use_only_healthy_sources_var = tk.BooleanVar(value=bool(getattr(cfg, "use_only_healthy_sources", False)))

    def setup_ui(self) -> None:
        # Header title banner
        header = ttk.Frame(self.win, padding=12)
        header.pack(fill=tk.X)
        ttk.Label(
            header,
            text="⚙️ Rendszer Beállítások",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            header,
            text="A beállítások automatikusan mentődnek a ~/.config/onion_search/config.json fájlba.",
            font=("TkDefaultFont", 8),
            foreground="#7f8c8d",
        ).pack(anchor=tk.W)

        # Main Tabbed Notebook
        self.notebook = ttk.Notebook(self.win)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        # Tab 1: Tor / Network
        self.tab_network = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_network, text="🌐 Tor / Hálózat")
        self.setup_tab_network()

        # Tab 2: Crawler / Performance
        self.tab_crawler = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_crawler, text="⚡ Crawler / Teljesítmény")
        self.setup_tab_crawler()

        # Tab 3: Filtering & Content
        self.tab_filter = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_filter, text="🔍 Szűrés és Tartalom")
        self.setup_tab_filter()

        # Tab 4: Database & Storage
        self.tab_storage = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_storage, text="💾 Adatbázis & Tárolás")
        self.setup_tab_storage()

        # Tab 5: General / UX
        self.tab_general = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_general, text="⚙️ Általános / UX")
        self.setup_tab_general()

        # Status notification label
        self.lbl_status = ttk.Label(self.win, text="", font=("TkDefaultFont", 8))
        self.lbl_status.pack(padx=12, pady=2)

        # Bottom Action Button Row
        btn_bar = ttk.Frame(self.win, padding=12)
        btn_bar.pack(fill=tk.X)

        ttk.Button(
            btn_bar,
            text="↺ Alapértelmezések",
            command=self.reset_to_defaults,
        ).pack(side=tk.LEFT, padx=4)

        ttk.Button(
            btn_bar,
            text="Mégse",
            command=self.win.destroy,
        ).pack(side=tk.RIGHT, padx=4)

        ttk.Button(
            btn_bar,
            text="💾 Mentés",
            command=self.save_and_close,
        ).pack(side=tk.RIGHT, padx=4)

        ttk.Button(
            btn_bar,
            text="✔ Alkalmaz",
            command=self.apply_changes,
        ).pack(side=tk.RIGHT, padx=4)

    def setup_tab_network(self) -> None:
        f = self.tab_network

        # Proxy connection frame
        p_frame = ttk.LabelFrame(f, text="SOCKS5 & ControlPort Címek", padding=10)
        p_frame.pack(fill=tk.X, pady=4)

        ttk.Label(p_frame, text="SOCKS Host:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Entry(p_frame, textvariable=self.socks_host_var, width=16).grid(row=0, column=1, sticky=tk.W, pady=4, padx=6)

        ttk.Label(p_frame, text="SOCKS Port:").grid(row=0, column=2, sticky=tk.W, pady=4, padx=(12, 0))
        ttk.Combobox(p_frame, textvariable=self.socks_port_var, values=["9050", "9150"], width=8).grid(row=0, column=3, sticky=tk.W, pady=4, padx=6)

        ttk.Label(p_frame, text="Control Port:").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(p_frame, textvariable=self.ctrl_port_var, values=["9051", "9151"], width=8).grid(row=1, column=1, sticky=tk.W, pady=4, padx=6)

        # Active Proxy Status Info
        act_host = self.socks_host_var.get()
        act_port = self.socks_port_var.get()
        self.lbl_active_proxy = ttk.Label(
            p_frame,
            text=f"Aktív beállítás: {act_host}:{act_port}",
            font=("TkDefaultFont", 8, "bold"),
            foreground="#27ae60",
        )
        self.lbl_active_proxy.grid(row=1, column=2, columnspan=2, sticky=tk.W, padx=(12, 0))

        # Timeouts frame
        t_frame = ttk.LabelFrame(f, text="Tor Kapcsolódási Időkorlátok (Timeouts)", padding=10)
        t_frame.pack(fill=tk.X, pady=4)

        ttk.Label(t_frame, text="TCP Port Timeout (mp):").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Spinbox(t_frame, from_=0.5, to=10.0, increment=0.5, textvariable=self.tor_tcp_timeout_var, width=8).grid(row=0, column=1, sticky=tk.W, pady=4, padx=6)
        ttk.Label(t_frame, text="(TCP socket válaszidő korlát portonként)", font=("TkDefaultFont", 7), foreground="#7f8c8d").grid(row=0, column=2, sticky=tk.W, padx=6)

        ttk.Label(t_frame, text="Tor SOCKS Timeout (mp):").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Spinbox(t_frame, from_=1.0, to=30.0, increment=0.5, textvariable=self.tor_socks_timeout_var, width=8).grid(row=1, column=1, sticky=tk.W, pady=4, padx=6)
        ttk.Label(t_frame, text="(Valós SOCKS5 HTTP lekérdezés korlát)", font=("TkDefaultFont", 7), foreground="#7f8c8d").grid(row=1, column=2, sticky=tk.W, padx=6)

        # Diagnostic trigger button
        diag_btn_row = ttk.Frame(f)
        diag_btn_row.pack(fill=tk.X, pady=6)
        ttk.Button(
            diag_btn_row,
            text="🔍 Tor Kapcsolat Diagnosztika Futtatása Most",
            command=self.run_diagnostics,
        ).pack(side=tk.LEFT)

        # Auto NEWNYM thresholds frame
        n_frame = ttk.LabelFrame(f, text="Automatikus Identitás-váltás (NEWNYM)", padding=10)
        n_frame.pack(fill=tk.X, pady=4)

        ttk.Checkbutton(n_frame, text="Sikeres találatok után:", variable=self.auto_newnym_success_var).grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Spinbox(n_frame, from_=10, to=300, textvariable=self.success_threshold_var, width=6).grid(row=0, column=1, sticky=tk.W, pady=3, padx=6)

        ttk.Checkbutton(n_frame, text="Összes lekérdezés után:", variable=self.auto_newnym_total_var).grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Spinbox(n_frame, from_=20, to=1000, textvariable=self.total_threshold_var, width=6).grid(row=1, column=1, sticky=tk.W, pady=3, padx=6)

    def setup_tab_crawler(self) -> None:
        f = self.tab_crawler

        c_frame = ttk.LabelFrame(f, text="Párhuzamosság & Hálózati Sebesség", padding=10)
        c_frame.pack(fill=tk.X, pady=4)

        ttk.Label(c_frame, text="Párhuzamos szálak (Workers):").grid(row=0, column=0, sticky=tk.W, pady=6)
        ttk.Spinbox(c_frame, from_=1, to=20, textvariable=self.workers_var, width=6).grid(row=0, column=1, sticky=tk.W, pady=6, padx=6)
        ttk.Label(c_frame, text="(1-20 worker szál egyidejű lekérdezései)", font=("TkDefaultFont", 7), foreground="#7f8c8d").grid(row=0, column=2, sticky=tk.W)

        ttk.Label(c_frame, text="Domain-enkénti késleltetés (mp):").grid(row=1, column=0, sticky=tk.W, pady=6)
        ttk.Spinbox(c_frame, from_=0.0, to=10.0, increment=0.1, textvariable=self.domain_delay_var, width=6).grid(row=1, column=1, sticky=tk.W, pady=6, padx=6)
        ttk.Label(c_frame, text="(Rate limiting kímélő szünet azonos domain esetén)", font=("TkDefaultFont", 7), foreground="#7f8c8d").grid(row=1, column=2, sticky=tk.W)

        ttk.Label(c_frame, text="Oldalbetöltési timeout (mp):").grid(row=2, column=0, sticky=tk.W, pady=6)
        ttk.Spinbox(c_frame, from_=5, to=120, textvariable=self.timeout_get_var, width=6).grid(row=2, column=1, sticky=tk.W, pady=6, padx=6)
        ttk.Label(c_frame, text="(Maximum várakozás egy .onion oldal letöltésekor)", font=("TkDefaultFont", 7), foreground="#7f8c8d").grid(row=2, column=2, sticky=tk.W)

        d_frame = ttk.LabelFrame(f, text="Crawler Mélység & Linkgyűjtés", padding=10)
        d_frame.pack(fill=tk.X, pady=6)

        ttk.Label(d_frame, text="Max. crawl mélység:").grid(row=0, column=0, sticky=tk.W, pady=6)
        ttk.Spinbox(d_frame, from_=1, to=10, textvariable=self.max_crawl_depth_var, width=6).grid(row=0, column=1, sticky=tk.W, pady=6, padx=6)
        ttk.Label(d_frame, text="(Bejárási hivatkozási mélység szintjei)", font=("TkDefaultFont", 7), foreground="#7f8c8d").grid(row=0, column=2, sticky=tk.W)

        ttk.Label(d_frame, text="Max. linkek oldalanként:").grid(row=1, column=0, sticky=tk.W, pady=6)
        ttk.Spinbox(d_frame, from_=10, to=1000, increment=10, textvariable=self.max_links_per_page_var, width=6).grid(row=1, column=1, sticky=tk.W, pady=6, padx=6)
        ttk.Label(d_frame, text="(Maximum kinyerhető .onion link egy oldalból)", font=("TkDefaultFont", 7), foreground="#7f8c8d").grid(row=1, column=2, sticky=tk.W)

        ttk.Checkbutton(d_frame, text="User-Agent fejlécek rotálása", variable=self.user_agent_rotate_var).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=6)

    def setup_tab_filter(self) -> None:
        f = self.tab_filter

        s_frame = ttk.LabelFrame(f, text="Alapértelmezett Szűrők", padding=10)
        s_frame.pack(fill=tk.X, pady=4)

        ttk.Label(s_frame, text="Alapértelmezett nyelv:").grid(row=0, column=0, sticky=tk.W, pady=6)
        lang_combo = ttk.Combobox(
            s_frame,
            textvariable=self.default_language_var,
            values=["all", "hu", "en", "de", "fr", "ru", "es", "other"],
            state="readonly",
            width=10,
        )
        lang_combo.grid(row=0, column=1, sticky=tk.W, pady=6, padx=6)

        ttk.Label(s_frame, text="Alapértelmezett kategória:").grid(row=1, column=0, sticky=tk.W, pady=6)
        cat_combo = ttk.Combobox(
            s_frame,
            textvariable=self.default_category_var,
            values=["all", "forum", "wiki", "library", "news", "market", "other"],
            state="readonly",
            width=10,
        )
        cat_combo.grid(row=1, column=1, sticky=tk.W, pady=6, padx=6)

        d_frame = ttk.LabelFrame(f, text="Tartalom- és Duplikációkezelés", padding=10)
        d_frame.pack(fill=tk.X, pady=6)

        ttk.Label(d_frame, text="Ujjlenyomat / Fingerprint érzékenység:").grid(row=0, column=0, sticky=tk.W, pady=6)
        fp_combo = ttk.Combobox(
            d_frame,
            textvariable=self.fingerprint_sensitivity_var,
            values=["high", "medium", "low"],
            state="readonly",
            width=10,
        )
        fp_combo.grid(row=0, column=1, sticky=tk.W, pady=6, padx=6)
        ttk.Label(d_frame, text="(Klón- és tüköroldal érzékelés szigorúsága)", font=("TkDefaultFont", 7), foreground="#7f8c8d").grid(row=0, column=2, sticky=tk.W)

        ttk.Label(d_frame, text="Halott linkek újraellenőrzése (óra):").grid(row=1, column=0, sticky=tk.W, pady=6)
        ttk.Spinbox(d_frame, from_=1.0, to=720.0, increment=12.0, textvariable=self.dead_link_recheck_hours_var, width=8).grid(row=1, column=1, sticky=tk.W, pady=6, padx=6)
        ttk.Label(d_frame, text="(Feketelistázott halott címek elévülési ideje)", font=("TkDefaultFont", 7), foreground="#7f8c8d").grid(row=1, column=2, sticky=tk.W)

        ttk.Checkbutton(
            d_frame,
            text="Normalize to host only (URL-ek csonkolása a domainre)",
            variable=self.normalize_to_host_only_var,
        ).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=6)

    def setup_tab_storage(self) -> None:
        f = self.tab_storage

        b_frame = ttk.LabelFrame(f, text="Adatbázis Motor & Biztonság", padding=10)
        b_frame.pack(fill=tk.X, pady=4)

        ttk.Label(b_frame, text="Tároló Engine:").grid(row=0, column=0, sticky=tk.W, pady=6)
        b_combo = ttk.Combobox(
            b_frame,
            textvariable=self.backend_var,
            values=["sqlite", "json"],
            state="readonly",
            width=10,
        )
        b_combo.grid(row=0, column=1, sticky=tk.W, pady=6, padx=6)

        ttk.Label(b_frame, text=f"Adatbázis fájl: {DB_FILE}", font=("TkDefaultFont", 8), foreground="#7f8c8d").grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=2)

        ttk.Checkbutton(b_frame, text="Adatbázis mentések AES/Fernet titkosítása", variable=self.encrypt_storage_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=6)

        e_frame = ttk.LabelFrame(f, text="Export & Karbantartás", padding=10)
        e_frame.pack(fill=tk.X, pady=6)

        ttk.Label(e_frame, text="Alapértelmezett export formátum:").grid(row=0, column=0, sticky=tk.W, pady=6)
        exp_combo = ttk.Combobox(
            e_frame,
            textvariable=self.export_default_format_var,
            values=["csv", "json", "txt"],
            state="readonly",
            width=10,
        )
        exp_combo.grid(row=0, column=1, sticky=tk.W, pady=6, padx=6)

        ttk.Checkbutton(e_frame, text="Halott / régi bejegyzések automatikus tisztítása", variable=self.auto_cleanup_dead_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=6)

    def setup_tab_general(self) -> None:
        f = self.tab_general

        g_frame = ttk.LabelFrame(f, text="Indítási & Felhasználói Élmény (UX)", padding=10)
        g_frame.pack(fill=tk.X, pady=4)

        ttk.Checkbutton(g_frame, text="Indításkor automatikus seed frissítés (Tor66, Deep Search)", variable=self.auto_update_seeds_var).pack(anchor=tk.W, pady=6)
        ttk.Checkbutton(g_frame, text="Indításkor automatikus Tor diagnosztika & auto-beállítás", variable=self.auto_tor_diagnostics_var).pack(anchor=tk.W, pady=6)
        ttk.Checkbutton(g_frame, text="Eredmények és állapot automatikus mentése kilépéskor", variable=self.auto_save_var).pack(anchor=tk.W, pady=6)
        ttk.Checkbutton(g_frame, text="Sötét téma (Dark Mode) használata", variable=self.dark_mode_var).pack(anchor=tk.W, pady=6)
        ttk.Checkbutton(g_frame, text="Minimalizálás tálcára bezárás helyett", variable=self.minimize_to_tray_var).pack(anchor=tk.W, pady=6)

        s_frame = ttk.LabelFrame(f, text="Seed Plugin Beállítások", padding=10)
        s_frame.pack(fill=tk.X, pady=4)

        ttk.Checkbutton(s_frame, text="Csak az egészséges (🟢 OK) seed forrásokat használd", variable=self.use_only_healthy_sources_var).pack(anchor=tk.W, pady=4)

        ttl_row = ttk.Frame(s_frame)
        ttl_row.pack(fill=tk.X, pady=4)
        ttk.Label(ttl_row, text="Health-Check gyorsítótár TTL (mp):").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Spinbox(ttl_row, from_=60, to=3600, increment=60, textvariable=self.health_check_cache_ttl_var, width=8).pack(side=tk.LEFT)
        ttk.Label(ttl_row, text="(pl. 600 mp = 10 perc)", font=("TkDefaultFont", 7), foreground="#7f8c8d").pack(side=tk.LEFT, padx=6)

    def run_diagnostics(self) -> None:
        if self.on_run_diagnostics_callback:
            self.on_run_diagnostics_callback()
            self.lbl_status.config(text="Diagnosztika elindítva!", foreground="#27ae60")
        else:
            messagebox.showinfo("Diagnosztika", "A diagnosztika futtatása a főablakból érhető el.")

    def validate_inputs(self) -> Tuple[bool, str]:
        """Validate form fields to prevent invalid settings."""
        # 1. Port validation
        for port_name, port_val in [("SOCKS", self.socks_port_var.get()), ("Control", self.ctrl_port_var.get())]:
            try:
                p = int(port_val)
                if p < 1 or p > 65535:
                    return False, f"Érvénytelen {port_name} port szám ({port_val})! Érvényes tartomány: 1-65535."
            except ValueError:
                return False, f"A(z) {port_name} port számnak egész számnak kell lennie!"

        # 2. Timeouts validation
        if self.tor_tcp_timeout_var.get() <= 0 or self.tor_tcp_timeout_var.get() > 30.0:
            return False, "A TCP Port Timeout értékének 0.1 és 30.0 mp között kell lennie!"
        if self.tor_socks_timeout_var.get() <= 0 or self.tor_socks_timeout_var.get() > 60.0:
            return False, "A Tor SOCKS Timeout értékének 0.5 és 60.0 mp között kell lennie!"
        if self.timeout_get_var.get() < 1 or self.timeout_get_var.get() > 120:
            return False, "Az oldalbetöltési timeout értékének 1 és 120 mp között kell lennie!"

        # 3. Crawler validation
        if self.workers_var.get() < 1 or self.workers_var.get() > 20:
            return False, "A szálak száma (Workers) 1 és 20 között lehet!"
        if self.domain_delay_var.get() < 0.0 or self.domain_delay_var.get() > 10.0:
            return False, "A domain késleltetés 0.0 és 10.0 mp között lehet!"
        if self.max_crawl_depth_var.get() < 1 or self.max_crawl_depth_var.get() > 10:
            return False, "A crawl mélység 1 és 10 között lehet!"
        if self.max_links_per_page_var.get() < 5 or self.max_links_per_page_var.get() > 1000:
            return False, "Az oldalankénti max. linkek száma 5 és 1000 között lehet!"

        return True, "OK"

    def build_config_from_form(self) -> AppConfig:
        """Construct strongly typed AppConfig from current form variables."""
        return AppConfig(
            socks_host=self.socks_host_var.get().strip(),
            socks_port=self.socks_port_var.get().strip(),
            ctrl_port=self.ctrl_port_var.get().strip(),
            workers=self.workers_var.get(),
            backend=self.backend_var.get(),
            dark_mode=self.dark_mode_var.get(),
            auto_newnym_success=self.auto_newnym_success_var.get(),
            auto_newnym_total=self.auto_newnym_total_var.get(),
            success_threshold=self.success_threshold_var.get(),
            total_threshold=self.total_threshold_var.get(),
            auto_save=self.auto_save_var.get(),
            live_filtering=self.cfg.live_filtering,
            allow_clearnet=self.cfg.allow_clearnet,
            encrypt_storage=self.encrypt_storage_var.get(),
            auto_update_seeds=self.auto_update_seeds_var.get(),
            seed_sources=self.cfg.seed_sources,
            seed_update_interval_hours=self.cfg.seed_update_interval_hours,
            last_seed_update=self.cfg.last_seed_update,
            health_check_cache_ttl=self.health_check_cache_ttl_var.get(),
            disabled_plugins=self.cfg.disabled_plugins,
            use_only_healthy_sources=self.use_only_healthy_sources_var.get(),
            timeout_get=self.timeout_get_var.get(),
            domain_delay=self.domain_delay_var.get(),
            queries=self.cfg.queries,
            normalize_to_host_only=self.normalize_to_host_only_var.get(),
            tor_tcp_timeout=self.tor_tcp_timeout_var.get(),
            tor_socks_timeout=self.tor_socks_timeout_var.get(),
            max_crawl_depth=self.max_crawl_depth_var.get(),
            max_links_per_page=self.max_links_per_page_var.get(),
            user_agent_rotate=self.user_agent_rotate_var.get(),
            default_language=self.default_language_var.get(),
            default_category=self.default_category_var.get(),
            fingerprint_sensitivity=self.fingerprint_sensitivity_var.get(),
            dead_link_recheck_hours=self.dead_link_recheck_hours_var.get(),
            auto_cleanup_dead=self.auto_cleanup_dead_var.get(),
            export_default_format=self.export_default_format_var.get(),
            auto_tor_diagnostics_on_startup=self.auto_tor_diagnostics_var.get(),
            minimize_to_tray=self.minimize_to_tray_var.get(),
        )

    def apply_changes(self) -> bool:
        """Validate and apply config changes without closing the dialog."""
        valid, err = self.validate_inputs()
        if not valid:
            messagebox.showwarning("Érvénytelen beállítás", err, parent=self.win)
            self.lbl_status.config(text=f"HIBA: {err}", foreground="#c0392b")
            return False

        new_cfg = self.build_config_from_form()
        self.config_manager.save(new_cfg)

        if self.on_save_callback:
            self.on_save_callback(new_cfg)

        self.lbl_status.config(text="Beállítások sikeresen alkalmazva és mentve!", foreground="#27ae60")
        self.lbl_active_proxy.config(text=f"Aktív beállítás: {new_cfg.socks_host}:{new_cfg.socks_port}")
        return True

    def save_and_close(self) -> None:
        """Apply config changes and close the dialog."""
        if self.apply_changes():
            self.win.destroy()

    def reset_to_defaults(self) -> None:
        """Reset all form variables to default AppConfig values."""
        if not messagebox.askyesno(
            "Alapértelmezések",
            "Biztosan visszaállítasz minden beállítást az alapértelmezett gyári értékekre?",
            parent=self.win,
        ):
            return

        default_cfg = AppConfig()
        self.cfg = default_cfg

        # Re-initialize variables
        self.init_variables()
        self.lbl_status.config(text="Alapértelmezett értékek visszaállítva!", foreground="#2980b9")
        self.lbl_active_proxy.config(text=f"Aktív beállítás: {default_cfg.socks_host}:{default_cfg.socks_port}")
