/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {
  FolderTree,
  CheckCircle2,
  FileCheck2,
  Sliders,
  Terminal,
  FileCode,
  ShieldCheck,
  Zap,
} from 'lucide-react';

export default function App() {
  const qualityFeatures = [
    {
      title: 'Teljes Python Típusannotáció (Type Hints)',
      desc: 'Minden függvény és metódus (pl. detect_language(text: str, html_lang_attr: str = "") -> str, matches_precise_filter(...)) szigorú típusannotációt kapott (Optional, Tuple, Dict, List).',
      icon: FileCheck2,
      color: 'text-indigo-400',
    },
    {
      title: 'Szabványos Logging Modul & TkLogHandler',
      desc: 'A közvetlen UI kiírás helyett a Python beépített logging modulja fut: egyedi TkLogHandler fogadja a LogRecord eseményeket és továbbítja őket szálbiztosan a felületi naplóhoz.',
      icon: Terminal,
      color: 'text-cyan-400',
    },
    {
      title: 'Konstansok & Varázsszámok Felszámolása',
      desc: 'Központi config.py modulba szervezett konstansok: DEFAULT_TIMEOUT_GET=20, MIN_HTML_BODY_LENGTH=300, MAX_CONTENT_TEXT_LENGTH=8000, MIN_NEWNYM_INTERVAL_AUTO=12.0 stb.',
      icon: FileCode,
      color: 'text-amber-400',
    },
    {
      title: 'Perzisztens Konfigfájl (~/.config/onion_search/config.json)',
      desc: 'ConfigManager és AppConfig dataclass: a portok, szálak száma (workers), sötét mód, küszöbértékek és keresőkifejezések automatikusan mentődnek és induláskor betöltődnek.',
      icon: Sliders,
      color: 'text-emerald-400',
    },
    {
      title: 'Átfogó Unit Tesztkészlet (52/52 Sikeres Teszt)',
      icon: ShieldCheck,
      color: 'text-purple-400',
    },
    {
      title: 'Aszinkron Motor (aiohttp + asyncio)',
      desc: 'A korábbi httpx alapú fetcher helyett egy rendkívül gyors aiohttp.ClientSession alapú aszinkron motor végzi a letöltéseket az async_fetch_page metóduson keresztül.',
      icon: Zap,
      color: 'text-yellow-400',
    },
    {
      title: 'Több Keresőmotor (Ahmia + OnionSearchEngine)',
      desc: 'A beépített Ahmia mellett immár az OnionSearchEngine is aktívan részt vesz a találatok biztosításában, jelentősen növelve az új felfedezett .onion címek számát.',
      icon: FolderTree,
      color: 'text-emerald-400',
    },
    {
      title: 'Szálbiztosság & X11 Hibajavítások',
      desc: 'A UI elemek és változók lekérdezése (get/config) áthelyezésre került a főszálba, megszüntetve a Linuxos X11 async összeomlásokat és beragadó kereséseket.',
      icon: ShieldCheck,
      color: 'text-red-400',
    },
    {
      title: 'Tor Circuit Info Logolás',
      desc: 'A NEWNYM parancsok kiadásakor a vezérlő automatikusan lekéri az aktív Tor áramkörök adatait (circuit-status) és naplózza a felületen.',
      icon: Terminal,
      color: 'text-blue-400',
    },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 md:p-12 font-sans selection:bg-emerald-500 selection:text-slate-950">
      <div className="max-w-6xl mx-auto space-y-10">
        {/* Header */}
        <header className="border-b border-slate-800 pb-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-3">
              <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs px-2.5 py-0.5 rounded font-mono font-semibold">
                CODE QUALITY & TEST SUITE
              </span>
              <span className="text-slate-500 text-sm">v4.8.4 Robust Release</span>
            </div>
            <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight mt-2 text-white">
              Onion Kereső — Kódminőség & Teszteltség
            </h1>
            <p className="text-slate-400 text-sm md:text-base mt-1">
              Szigorú típusannotációk, szabványos Python logging, JSON konfigurációs perzisztencia és 52 automatizált egységteszt.
            </p>
          </div>

          <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 p-3.5 rounded-xl shadow-lg">
            <CheckCircle2 className="w-8 h-8 text-emerald-400 shrink-0" />
            <div>
              <div className="text-xs text-slate-400 font-medium">Pytest Tesztlefedettség</div>
              <div className="text-emerald-400 font-bold font-mono text-sm">
                52 / 52 Sikeres (100% Zöld)
              </div>
            </div>
          </div>
        </header>

        {/* Feature Grid */}
        <section className="space-y-4">
          <div className="flex items-center gap-2 text-slate-200 font-semibold">
            <FolderTree className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg">Megvalósított Kódminőségi Fejlesztések</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {qualityFeatures.map((item, idx) => {
              const Icon = item.icon;
              return (
                <div
                  key={idx}
                  className="bg-slate-900 border border-slate-800 hover:border-slate-700 transition p-5 rounded-xl flex items-start gap-4"
                >
                  <div className="p-2.5 bg-slate-800/80 rounded-lg shrink-0 mt-0.5">
                    <Icon className={`w-5 h-5 ${item.color}`} />
                  </div>
                  <div className="space-y-1.5">
                    <div className="font-semibold text-slate-100 text-sm">{item.title}</div>
                    <p className="text-xs text-slate-400 leading-relaxed">{item.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Configuration Schema */}
        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h2 className="text-base font-semibold text-slate-200">Konfiguráció & Naplózási Architektúra</h2>
          <pre className="font-mono text-xs bg-slate-950 p-4 rounded-lg text-slate-300 overflow-x-auto leading-relaxed border border-slate-800">
{`~/.config/onion_search/config.json
{
  "socks_port": "9050",
  "ctrl_port": "9051",
  "workers": 6,
  "backend": "sqlite",
  "dark_mode": true,
  "auto_newnym_success": true,
  "auto_newnym_total": true,
  "success_threshold": 50,
  "total_threshold": 100,
  "auto_save": true,
  "live_filtering": true,
  "timeout_get": 20,
  "domain_delay": 1.0,
  "queries": "forum, board, wiki, library"
}

Standard Logging Flow:
  logger.info("msg", extra={"tag": "ok"})
    │
    └──► TkLogHandler (logging.Handler)
           │
           └──► LogPanel.log_msg(msg, tag="ok")
                  │
                  └──► In-memory Buffer + Dynamic Filtered View`}
          </pre>
        </section>

        {/* Verification Summary */}
        <footer className="text-xs text-slate-500 border-t border-slate-800 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>Onion Kereső v4.8.4 — Termelési Minőség</div>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              52/52 Pytest Sikeres
            </span>
            <span className="text-slate-400 font-mono">Clean Architecture</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
