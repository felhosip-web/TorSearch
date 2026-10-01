"""
Filter panel UI and matching logic for language, category, and precise queries.
"""
import re
import tkinter as tk
from tkinter import ttk
from onion_search.utils.helpers import parse_list


def matches_precise_filter(
    title,
    text,
    enabled=False,
    must_all="",
    must_any="",
    must_not="",
    title_contains="",
    regex="",
    min_len=0,
    lang="",
    category="",
):
    """Pure filtering function for testing and standalone execution."""
    if not enabled:
        return True, "OK"
    t_lower = (title + " " + text).lower()
    title_lower = title.lower()

    must_all_list = parse_list(must_all)
    for kw in must_all_list:
        if kw not in t_lower:
            return False, f"hiányzik MUST ALL: {kw}"

    must_any_list = parse_list(must_any)
    if must_any_list:
        if not any(kw in t_lower for kw in must_any_list):
            return False, f"egyik ANY sem talalhato: {must_any_list}"

    must_not_list = parse_list(must_not)
    for kw in must_not_list:
        if kw in t_lower:
            return False, f"kizart NOT talalat: {kw}"

    title_c = title_contains.strip().lower()
    if title_c:
        tcs = [p.strip() for p in title_c.split(",") if p.strip()]
        if not any(tc in title_lower for tc in tcs):
            return False, f"cim nem tartalmazza: {title_c}"

    if min_len and len(text) < min_len:
        return False, f"tul rovid {len(text)} < {min_len}"

    regex_pat = regex.strip()
    if regex_pat:
        try:
            if not re.search(regex_pat, text, re.IGNORECASE):
                return False, f"regex nem illeszkedik: {regex_pat}"
        except re.error as e:
            return False, f"regex hiba: {e}"

    return True, "OK"


class FilterPanel(ttk.Frame):
    """Encapsulates filter UI controls (quick language/category and precise keywords) with live filtering."""

    def __init__(self, parent, on_filter_changed=None):
        super().__init__(parent)
        self.on_filter_changed = on_filter_changed

        # Filter state variables
        self.lang_filter_var = tk.StringVar(value="all")
        self.category_filter_var = tk.StringVar(value="all")
        self.enable_precise_var = tk.BooleanVar(value=False)
        self.must_all_var = tk.StringVar(value="")
        self.must_any_var = tk.StringVar(value="")
        self.must_not_var = tk.StringVar(value="")
        self.title_contains_var = tk.StringVar(value="")
        self.regex_var = tk.StringVar(value="")
        self.min_len_var = tk.IntVar(value=0)
        self.save_only_filtered_var = tk.BooleanVar(value=True)
        self.live_filter_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._setup_traces()

    def _build_ui(self):
        # 1. Precise filter frame
        precise_frame = ttk.LabelFrame(self, text="🔍 Precíz egyedi keresés", padding=4)
        precise_frame.pack(fill=tk.X, padx=8, pady=2)

        row1 = ttk.Frame(precise_frame)
        row1.pack(fill=tk.X, pady=1)
        ttk.Checkbutton(row1, text="Bekapcsolva:", variable=self.enable_precise_var).pack(
            side=tk.LEFT
        )
        ttk.Label(row1, text="MIND (AND):").pack(side=tk.LEFT, padx=(8, 2))
        ttk.Entry(row1, textvariable=self.must_all_var, width=22).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Label(row1, text="BÁRMELY (OR):").pack(side=tk.LEFT, padx=(6, 2))
        ttk.Entry(row1, textvariable=self.must_any_var, width=18).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Label(row1, text="KIZÁRVA (NOT):").pack(side=tk.LEFT, padx=(6, 2))
        ttk.Entry(row1, textvariable=self.must_not_var, width=16).pack(
            side=tk.LEFT, padx=2
        )

        row2 = ttk.Frame(precise_frame)
        row2.pack(fill=tk.X, pady=1)
        ttk.Label(row2, text="Címben:").pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.title_contains_var, width=16).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Label(row2, text="Regex:").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Entry(row2, textvariable=self.regex_var, width=18).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Label(row2, text="Min:").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Spinbox(
            row2, from_=0, to=10000, textvariable=self.min_len_var, width=5
        ).pack(side=tk.LEFT, padx=2)
        ttk.Checkbutton(
            row2, text="Csak szűrt mentése", variable=self.save_only_filtered_var
        ).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(
            row2, text="⚡ Élő szűrés", variable=self.live_filter_var
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(row2, text="Szűrés Ctrl+F", command=self._trigger_change).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(row2, text="Reset", command=self.reset_precise, width=6).pack(
            side=tk.LEFT, padx=2
        )
        self.lbl_precise_info = ttk.Label(
            row2, text="", font=("TkDefaultFont", 7), foreground="#8e44ad"
        )
        self.lbl_precise_info.pack(side=tk.LEFT, padx=6)

        # 2. Quick filter frame
        filter_frame = ttk.LabelFrame(
            self, text="Gyors szűrők - Nyelv & Kategória", padding=4
        )
        filter_frame.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(filter_frame, text="Nyelv:").pack(side=tk.LEFT)
        lang_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.lang_filter_var,
            values=["all", "hu", "en", "de", "fr", "ru", "es", "it", "other"],
            width=6,
            state="readonly",
        )
        lang_combo.pack(side=tk.LEFT, padx=2)
        lang_combo.bind("<<ComboboxSelected>>", lambda e: self._trigger_change())

        ttk.Label(filter_frame, text="Kategória:").pack(side=tk.LEFT, padx=(8, 0))
        cat_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.category_filter_var,
            values=["all", "forum", "wiki", "library", "news", "other", "market"],
            width=8,
            state="readonly",
        )
        cat_combo.pack(side=tk.LEFT, padx=2)
        cat_combo.bind("<<ComboboxSelected>>", lambda e: self._trigger_change())

        ttk.Button(
            filter_frame, text="Reset", command=self.reset_filters, width=6
        ).pack(side=tk.LEFT, padx=8)
        self.lbl_filter_info = ttk.Label(
            filter_frame,
            text="Szűrő: mind (0/0)",
            font=("TkDefaultFont", 8, "bold"),
        )
        self.lbl_filter_info.pack(side=tk.LEFT, padx=8)

    def _setup_traces(self):
        """Bind variable traces for instant live filtering."""
        def _on_var_change(*args):
            if self.live_filter_var.get():
                self._trigger_change()

        for var in [
            self.must_all_var,
            self.must_any_var,
            self.must_not_var,
            self.title_contains_var,
            self.regex_var,
            self.min_len_var,
            self.enable_precise_var,
        ]:
            try:
                var.trace_add("write", _on_var_change)
            except Exception:
                pass

    def _trigger_change(self):
        if self.on_filter_changed:
            self.on_filter_changed()

    def reset_precise(self):
        self.must_all_var.set("")
        self.must_any_var.set("")
        self.must_not_var.set("")
        self.title_contains_var.set("")
        self.regex_var.set("")
        self.min_len_var.set(0)
        self.enable_precise_var.set(False)
        self.lbl_precise_info.config(text="")
        self._trigger_change()

    def reset_filters(self):
        self.lang_filter_var.set("all")
        self.category_filter_var.set("all")
        self._trigger_change()

    def matches_precise(self, title, text, lang="", category=""):
        return matches_precise_filter(
            title=title,
            text=text,
            enabled=self.enable_precise_var.get(),
            must_all=self.must_all_var.get(),
            must_any=self.must_any_var.get(),
            must_not=self.must_not_var.get(),
            title_contains=self.title_contains_var.get(),
            regex=self.regex_var.get(),
            min_len=self.min_len_var.get(),
            lang=lang,
            category=category,
        )

    def is_item_visible(self, item):
        lang = self.lang_filter_var.get()
        cat = self.category_filter_var.get()
        if lang != "all" and item.get("lang", "en") != lang:
            return False, "language mismatch"
        if cat != "all" and item.get("category", "other") != cat:
            return False, "category mismatch"
        if self.enable_precise_var.get():
            full_text = item.get("snippet", "") + " " + item.get("title", "")
            ok, reason = self.matches_precise(
                item.get("title", ""), full_text, item.get("lang", ""), item.get("category", "")
            )
            if not ok:
                return False, reason
        return True, "OK"

    def set_counts(self, shown, total, filtered_out):
        lang = self.lang_filter_var.get()
        cat = self.category_filter_var.get()
        self.lbl_filter_info.config(text=f"Szűrő: {lang}/{cat} ({shown}/{total})")
        self.lbl_precise_info.config(text=f"Precíz: {shown} látszik, {filtered_out} kiszűrve")
