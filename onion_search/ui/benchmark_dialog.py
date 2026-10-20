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
Performance Benchmark Test Runner & UI Dialog for comparing Sync vs Async network fetcher performance.
Provides automated throughput, latency, and speedup ratio metrics.
Developed by HES Projects by FePe.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Any, Callable, Dict, List, Optional, Tuple

from onion_search.config import TIMEOUT_GET
from onion_search.core.fetcher import OnionFetcher

logger = logging.getLogger("onion_search")


class PerformanceBenchmarkRunner:
    """Executes comparative benchmark tests between Sync (threads) and Async (httpx/asyncio)."""

    def __init__(self, fetcher: Optional[OnionFetcher] = None):
        self.fetcher = fetcher or OnionFetcher()

    def run_sync_benchmark(
        self,
        urls: List[str],
        proxy_url: str,
        workers: int = 6,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """Runs benchmark using synchronous requests + ThreadPoolExecutor."""
        start_t = time.time()
        results: List[Dict[str, Any]] = []
        completed = 0
        total = len(urls)

        def _worker(u: str) -> Dict[str, Any]:
            t0 = time.time()
            res = self.fetcher.fetch_page(u, proxy_url, is_running_cb=lambda: True)
            lat = (time.time() - t0) * 1000.0
            return {"url": u, "status": res.get("status", "unknown"), "latency_ms": lat}

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_worker, u): u for u in urls}
            for fut in as_completed(futures):
                completed += 1
                try:
                    res = fut.result()
                    results.append(res)
                except Exception as e:
                    results.append({"url": futures[fut], "status": "error", "latency_ms": 0.0, "error": str(e)})
                if progress_cb:
                    progress_cb(completed, total, f"Sync: {completed}/{total}")

        elapsed = time.time() - start_t
        success_cnt = sum(1 for r in results if r.get("status") not in ("dead", "error", "canceled"))
        fail_cnt = total - success_cnt
        avg_lat = (sum(r["latency_ms"] for r in results) / len(results)) if results else 0.0
        req_per_sec = (total / elapsed) if elapsed > 0 else 0.0

        return {
            "mode": "Sync",
            "elapsed_sec": round(elapsed, 2),
            "req_per_sec": round(req_per_sec, 2),
            "avg_latency_ms": round(avg_lat, 1),
            "total_requests": total,
            "success_count": success_cnt,
            "fail_count": fail_cnt,
            "workers": workers,
            "details": results,
        }

    def run_async_benchmark(
        self,
        urls: List[str],
        proxy_url: str,
        workers: int = 6,
        progress_cb: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """Runs benchmark using async httpx + asyncio task gather with Semaphore."""
        start_t = time.time()
        results: List[Dict[str, Any]] = []
        completed = 0
        total = len(urls)

        async def _async_runner():
            nonlocal completed
            import httpx

            sem = asyncio.Semaphore(workers)
            transport_kwargs = {}
            if proxy_url:
                transport_kwargs["proxy"] = proxy_url

            async with httpx.AsyncClient(timeout=TIMEOUT_GET, follow_redirects=True, **transport_kwargs) as client:
                async def _fetch_task(u: str):
                    nonlocal completed
                    async with sem:
                        t0 = time.time()
                        res = await self.fetcher.async_fetch_page_httpx(client, u, is_running_cb=lambda: True)
                        lat = (time.time() - t0) * 1000.0
                        completed += 1
                        if progress_cb:
                            progress_cb(completed, total, f"Async: {completed}/{total}")
                        return {"url": u, "status": res.get("status", "unknown"), "latency_ms": lat}

                tasks = [asyncio.create_task(_fetch_task(u)) for u in urls]
                return await asyncio.gather(*tasks, return_exceptions=True)

        loop_results = asyncio.run(_async_runner())
        for r in loop_results:
            if isinstance(r, Exception):
                results.append({"url": "", "status": "error", "latency_ms": 0.0, "error": str(r)})
            elif isinstance(r, dict):
                results.append(r)

        elapsed = time.time() - start_t
        success_cnt = sum(1 for r in results if r.get("status") not in ("dead", "error", "canceled"))
        fail_cnt = total - success_cnt
        avg_lat = (sum(r["latency_ms"] for r in results) / len(results)) if results else 0.0
        req_per_sec = (total / elapsed) if elapsed > 0 else 0.0

        return {
            "mode": "Async",
            "elapsed_sec": round(elapsed, 2),
            "req_per_sec": round(req_per_sec, 2),
            "avg_latency_ms": round(avg_lat, 1),
            "total_requests": total,
            "success_count": success_cnt,
            "fail_count": fail_cnt,
            "workers": workers,
            "details": results,
        }


class PerformanceTestDialog:
    """Tkinter Modal Dialog for running comparative Sync vs Async benchmarks."""

    DEFAULT_TEST_URLS = [
        "https://ahmia.fi",
        "https://duckduckgo.com",
        "https://torproject.org",
        "https://check.torproject.org",
        "http://jikan.moe",
    ]

    def __init__(self, parent: tk.Tk, fetcher: Optional[OnionFetcher] = None, proxy_url: str = "socks5h://127.0.0.1:9050"):
        self.parent = parent
        self.runner = PerformanceBenchmarkRunner(fetcher=fetcher)
        self.proxy_url = proxy_url

        self.win = tk.Toplevel(parent)
        self.win.title("⚡ Teljesítmény Benchmark Teszt (Sync vs Async)")
        self.win.geometry("680x620")
        self.win.resizable(False, False)

        self.sample_size_var = tk.IntVar(value=10)
        self.workers_var = tk.IntVar(value=6)
        self.running = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        # Title Header
        hdr = ttk.Frame(self.win, padding=12)
        hdr.pack(fill=tk.X)
        ttk.Label(hdr, text="⚡ Hálózati Teljesítmény Tesztelő", font=("TkDefaultFont", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(
            hdr,
            text="Hasonlítsa össze a hagyományos szinkron (requests + thread pool) és az új aszinkron (httpx + asyncio) hálózati modult.",
            font=("TkDefaultFont", 8),
            foreground="#7f8c8d",
            wraplength=640,
        ).pack(anchor=tk.W, pady=(2, 0))

        # Config Panel
        cfg_frame = ttk.LabelFrame(self.win, text="Teszt Beállítások", padding=10)
        cfg_frame.pack(fill=tk.X, padx=12, pady=4)

        f_grid = ttk.Frame(cfg_frame)
        f_grid.pack(fill=tk.X)

        ttk.Label(f_grid, text="Teszt minták / kérések száma:").grid(row=0, column=0, sticky=tk.W, pady=4)
        ttk.Spinbox(f_grid, from_=5, to=50, increment=5, textvariable=self.sample_size_var, width=8).grid(
            row=0, column=1, sticky=tk.W, pady=4, padx=8
        )

        ttk.Label(f_grid, text="Párhuzamos Worker / Szál szám:").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Spinbox(f_grid, from_=2, to=12, textvariable=self.workers_var, width=8).grid(
            row=1, column=1, sticky=tk.W, pady=4, padx=8
        )

        self.btn_run = ttk.Button(cfg_frame, text="▶ Teszt Indítása (Sync vs Async)", command=self.start_benchmark_thread)
        self.btn_run.pack(anchor=tk.W, pady=(8, 4))

        # Progress & Status Frame
        prog_frame = ttk.Frame(self.win, padding=12)
        prog_frame.pack(fill=tk.X)

        self.lbl_status = ttk.Label(prog_frame, text="Teszt futtatásra kész.", font=("TkDefaultFont", 9, "bold"))
        self.lbl_status.pack(anchor=tk.W, pady=2)

        self.progress_bar = ttk.Progressbar(prog_frame, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=4)

        # Comparative Summary Card Panel
        self.summary_frame = ttk.LabelFrame(self.win, text="Összehasonlító Eredmények", padding=10)
        self.summary_frame.pack(fill=tk.X, padx=12, pady=4)

        cards = ttk.Frame(self.summary_frame)
        cards.pack(fill=tk.X)

        # Sync Card
        c_sync = tk.Frame(cards, bg="#24273a", bd=1, relief=tk.RAISED, padding=8)
        c_sync.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        tk.Label(c_sync, text="SZINKRON (Sync)", bg="#24273a", fg="#8aadf4", font=("TkDefaultFont", 9, "bold")).pack()
        self.lbl_sync_res = tk.Label(
            c_sync, text="Összidő: -\nReq/s: -\nÁtl. latency: -\nSikeres/Halott: -", bg="#24273a", fg="#cad3f5", font=("Consolas", 8), justify=tk.LEFT
        )
        self.lbl_sync_res.pack(pady=4)

        # Async Card
        c_async = tk.Frame(cards, bg="#24273a", bd=1, relief=tk.RAISED, padding=8)
        c_async.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4)
        tk.Label(c_async, text="ASZINKRON (Async)", bg="#24273a", fg="#a6e3a1", font=("TkDefaultFont", 9, "bold")).pack()
        self.lbl_async_res = tk.Label(
            c_async, text="Összidő: -\nReq/s: -\nÁtl. latency: -\nSikeres/Halott: -", bg="#24273a", fg="#cad3f5", font=("Consolas", 8), justify=tk.LEFT
        )
        self.lbl_async_res.pack(pady=4)

        # Speedup Badge
        self.lbl_speedup = tk.Label(
            self.summary_frame, text="Gyorsulási tényező (Speedup): —", font=("TkDefaultFont", 10, "bold"), fg="#f1c40f"
        )
        self.lbl_speedup.pack(pady=(8, 2))

        # Log Output Frame
        log_frame = ttk.LabelFrame(self.win, text="Részletes Napló", padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        self.txt_log = scrolledtext.ScrolledText(log_frame, height=6, font=("Consolas", 8))
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        # Bottom Action Bar
        btn_bar = ttk.Frame(self.win, padding=12)
        btn_bar.pack(fill=tk.X)
        ttk.Button(btn_bar, text="📋 Eredmények Másolása", command=self.copy_results).pack(side=tk.LEFT)
        ttk.Button(btn_bar, text="Bezárás", command=self.win.destroy).pack(side=tk.RIGHT)

    def log(self, msg: str) -> None:
        self.txt_log.insert(tk.END, f"{msg}\n")
        self.txt_log.see(tk.END)

    def start_benchmark_thread(self) -> None:
        if self.running:
            return
        self.running = True
        self.btn_run.config(state=tk.DISABLED)
        self.txt_log.delete("1.0", tk.END)

        sample_size = self.sample_size_var.get()
        workers = self.workers_var.get()

        # Build url set
        base_urls = self.DEFAULT_TEST_URLS
        target_urls = (base_urls * (sample_size // len(base_urls) + 1))[:sample_size]

        import threading

        def _bg():
            def _update_prog(curr: int, tot: int, txt: str):
                self.win.after(0, lambda: (
                    self.lbl_status.config(text=f"Keresés fut... {txt}"),
                    self.progress_bar.config(maximum=tot * 2, value=curr if "Sync" in txt else tot + curr)
                ))

            self.log(f"⚡ Benchmark indítása {len(target_urls)} kéréssel, {workers} worker-rel...")
            self.log(f"Proxy: {self.proxy_url}")

            # 1. Sync run
            self.win.after(0, lambda: self.lbl_status.config(text="1/2: Szinkron mód tesztelése..."))
            self.log("\n--- 1. SZINKRON TESZT INDÍTÁSA ---")
            sync_res = self.runner.run_sync_benchmark(
                target_urls, self.proxy_url, workers=workers, progress_cb=_update_prog
            )
            self.log(
                f"Sync kész: {sync_res['elapsed_sec']}s | {sync_res['req_per_sec']} req/s | "
                f"átl. latency: {sync_res['avg_latency_ms']} ms"
            )

            # 2. Async run
            self.win.after(0, lambda: self.lbl_status.config(text="2/2: Aszinkron mód tesztelése..."))
            self.log("\n--- 2. ASZINKRON TESZT INDÍTÁSA ---")
            async_res = self.runner.run_async_benchmark(
                target_urls, self.proxy_url, workers=workers, progress_cb=_update_prog
            )
            self.log(
                f"Async kész: {async_res['elapsed_sec']}s | {async_res['req_per_sec']} req/s | "
                f"átl. latency: {async_res['avg_latency_ms']} ms"
            )

            # Compute Speedup
            sync_t = sync_res["elapsed_sec"] or 0.001
            async_t = async_res["elapsed_sec"] or 0.001
            speedup = sync_t / async_t if async_t > 0 else 1.0

            def _finish():
                self.running = False
                self.btn_run.config(state=tk.NORMAL)
                self.lbl_status.config(text="⚡ Benchmark Teszt Befejeződött!")

                self.lbl_sync_res.config(
                    text=f"Összidő: {sync_res['elapsed_sec']} s\n"
                         f"Req/s: {sync_res['req_per_sec']}\n"
                         f"Átl. latency: {sync_res['avg_latency_ms']} ms\n"
                         f"Sikeres/Halott: {sync_res['success_count']}/{sync_res['fail_count']}"
                )
                self.lbl_async_res.config(
                    text=f"Összidő: {async_res['elapsed_sec']} s\n"
                         f"Req/s: {async_res['req_per_sec']}\n"
                         f"Átl. latency: {async_res['avg_latency_ms']} ms\n"
                         f"Sikeres/Halott: {async_res['success_count']}/{async_res['fail_count']}"
                )

                if speedup > 1.0:
                    sp_str = f"⚡ Async {speedup:.2f}x GYORSABB, mint a Sync mód!"
                    col = "#a6e3a1"
                elif speedup < 1.0:
                    sp_str = f"Sync {1.0/speedup:.2f}x gyorsabb volt ebben a futásban."
                    col = "#e74c3c"
                else:
                    sp_str = "Mindkét mód azonos teljesítményt ért el."
                    col = "#f1c40f"

                self.lbl_speedup.config(text=sp_str, fg=col)
                self.log(f"\n⚡ {sp_str}")

            self.win.after(0, _finish)

        threading.Thread(target=_bg, daemon=True).start()

    def copy_results(self) -> None:
        text = self.txt_log.get("1.0", tk.END)
        self.win.clipboard_clear()
        self.win.clipboard_append(text)
        messagebox.showinfo("Másolva", "Benchmark eredmények másolva a vágólapra!")
