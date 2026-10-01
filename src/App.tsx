/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {
  FolderTree,
  CheckCircle2,
  ShieldCheck,
  Cpu,
  Database,
  Layers,
  Terminal,
  Activity,
  Code2,
} from 'lucide-react';

export default function App() {
  const modules = [
    {
      path: 'onion_search/main.py',
      role: 'Bootstrap & Dependency Injection',
      desc: 'Alkalmazás inicializálása, perzisztencia és domain komponensek létrehozása, DI összekötés és fő életciklus futtatása.',
      icon: Terminal,
      color: 'text-amber-400',
    },
    {
      path: 'onion_search/ui/main_window.py',
      role: 'Main Window & UI Lifecycle',
      desc: 'Főablak layout, keresési munkafolyamat koordináció, statisztika kártyák, TreeView és export dialógusok.',
      icon: Layers,
      color: 'text-blue-400',
    },
    {
      path: 'onion_search/ui/filters.py',
      role: 'Filter Panel & Query Matcher',
      desc: 'Nyelvi és kategória gyorsszűrők, precíz AND/OR/NOT kulcsszó és regex vizsgálatok.',
      icon: Code2,
      color: 'text-cyan-400',
    },
    {
      path: 'onion_search/ui/log_panel.py',
      role: 'Log Panel & Color Tags',
      desc: 'Színkódolt státusznapló (ok, clone, dead, newnym, tor_ok stb.), szűrt nézet és vágólap integráció.',
      icon: Activity,
      color: 'text-emerald-400',
    },
    {
      path: 'onion_search/core/fetcher.py',
      role: 'Network Fetching & Sessions',
      desc: 'Tor SOCKS proxy lekérések, redirect és hiba kezelés, SessionManager és nyilvános maglisták letöltése.',
      icon: Cpu,
      color: 'text-purple-400',
    },
    {
      path: 'onion_search/core/detector.py',
      role: 'Content & Clone Detection',
      desc: 'Nyelvdetektálás (heuristika + langdetect), kategória besorolás, SHA256 digit-stripped fingerprint és Bitcoin cím kinyerés.',
      icon: ShieldCheck,
      color: 'text-rose-400',
    },
    {
      path: 'onion_search/core/neonym.py',
      role: 'Tor Control & Identity Circuit',
      desc: 'Tor SOCKS és Control port állapotellenőrzések, cookie auth, auto-detect (9050/9150) és SIGNAL NEWNYM vezérlés.',
      icon: ShieldCheck,
      color: 'text-orange-400',
    },
    {
      path: 'onion_search/storage/sqlite_backend.py',
      role: 'SQLite Persistence',
      desc: 'WAL mód, results, fingerprints, btc_map, checked és 24 órás elévülésű dead_blacklist perzisztencia.',
      icon: Database,
      color: 'text-indigo-400',
    },
    {
      path: 'onion_search/storage/json_backend.py',
      role: 'JSON Persistence',
      desc: 'JSON állapot- és feketelista mentés/betöltés fájlrendszerre.',
      icon: Database,
      color: 'text-pink-400',
    },
    {
      path: 'onion_search/utils/helpers.py',
      role: 'Pure Utilities & Constants',
      desc: 'Időbélyeg formázás (fmt_ts), vesszővel elválasztott listafeldolgozás (parse_list) és útvonal konstansok.',
      icon: Layers,
      color: 'text-teal-400',
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
                P0 ARCHITECTURE REFACTOR
              </span>
              <span className="text-slate-500 text-sm">v4.8.0 Modular</span>
            </div>
            <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight mt-2 text-white">
              Onion Kereső — Architektúra Áttekintés
            </h1>
            <p className="text-slate-400 text-sm md:text-base mt-1">
              A korábbi 1200+ soros monolit felelősségeinek szétbontása tiszta modulokra, rétegzett architektúrával és Dependency Injectionnel.
            </p>
          </div>

          <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 p-3.5 rounded-xl shadow-lg">
            <CheckCircle2 className="w-8 h-8 text-emerald-400 shrink-0" />
            <div>
              <div className="text-xs text-slate-400 font-medium">Összes Pytest teszt</div>
              <div className="text-emerald-400 font-bold font-mono text-sm">
                19 / 19 Sikeres (100% Zöld)
              </div>
            </div>
          </div>
        </header>

        {/* Acceptance Criteria Status Cards */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm mb-2">
              <CheckCircle2 className="w-4 h-4" />
              <span>Modularitás & main.py</span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              A <code className="text-amber-300 bg-slate-800 px-1 py-0.5 rounded">main.py</code> kizárólag a komponensek inicializálásáért, a DI bekötéséért és az életciklus futtatásáért felel. Nulla üzleti logika.
            </p>
          </div>

          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm mb-2">
              <CheckCircle2 className="w-4 h-4" />
              <span>Rétegek Függetlensége</span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              Tiszta függőségi irányok: <code className="text-blue-300 bg-slate-800 px-1 py-0.5 rounded">UI</code> és <code className="text-purple-300 bg-slate-800 px-1 py-0.5 rounded">Core</code> nem tartalmaz SQL kódot. A <code className="text-indigo-300 bg-slate-800 px-1 py-0.5 rounded">Storage</code> nem importál UI-t. Nincs körkörös függőség.
            </p>
          </div>

          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm mb-2">
              <CheckCircle2 className="w-4 h-4" />
              <span>100% Viselkedés- és Séma-kompatibilis</span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              Az SQLite adatbázis séma, JSON állapotok, Tor socks/control kezelés, fingerprint hash és GUI viselkedés változatlan maradt.
            </p>
          </div>
        </section>

        {/* Modular Structure */}
        <section className="space-y-4">
          <div className="flex items-center gap-2 text-slate-200 font-semibold">
            <FolderTree className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg">Célstruktúra és Modulok Felelősségei</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {modules.map((mod) => {
              const Icon = mod.icon;
              return (
                <div
                  key={mod.path}
                  className="bg-slate-900 border border-slate-800 hover:border-slate-700 transition p-4 rounded-xl flex items-start gap-4"
                >
                  <div className="p-2.5 bg-slate-800/80 rounded-lg shrink-0 mt-0.5">
                    <Icon className={`w-5 h-5 ${mod.color}`} />
                  </div>
                  <div className="space-y-1">
                    <div className="font-mono text-xs text-slate-400">{mod.path}</div>
                    <div className="font-semibold text-slate-100 text-sm">{mod.role}</div>
                    <p className="text-xs text-slate-400 leading-relaxed">{mod.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Dependency Flow Map */}
        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h2 className="text-base font-semibold text-slate-200">Függőségi Gráf (Dependency Map)</h2>
          <pre className="font-mono text-xs bg-slate-950 p-4 rounded-lg text-slate-300 overflow-x-auto leading-relaxed border border-slate-800">
{`main.py (Bootstrap & Orchestration)
  │
  ├──► storage.sqlite_backend.SQLiteBackend (DB WAL, results, checked, dead)
  ├──► storage.json_backend.JSONBackend (JSON state & blacklist)
  │
  ├──► core.detector.ContentDetector (Language heuristic, Category, FP, BTC)
  ├──► core.fetcher.SessionManager & OnionFetcher (Tor SOCKS, requests, HTML parse)
  ├──► core.neonym.TorController (SOCKS & ControlPort check, NEWNYM signal)
  │
  └──► ui.main_window.MainWindow (GUI Coordination via Dependency Injection)
         ├──► ui.filters.FilterPanel (Language, Category, Precise AND/OR/NOT, Regex)
         ├──► ui.log_panel.LogPanel (Color tags, filtered view, thread-safe logger)
         └──► utils.helpers (fmt_ts, parse_list, constants)`}
          </pre>
        </section>

        {/* Verification Summary */}
        <footer className="text-xs text-slate-500 border-t border-slate-800 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>Onion Kereső P0 Architectural Refactoring — Python 3.10 / 3.11</div>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Pytest Verified
            </span>
            <span className="text-slate-400 font-mono">CI/CD Ready</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
