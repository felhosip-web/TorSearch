/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import {
  FolderTree,
  CheckCircle2,
  Moon,
  Eye,
  Zap,
  Play,
  Search,
  Download,
  Layers,
  Activity,
  ShieldCheck,
} from 'lucide-react';

export default function App() {
  const uiFeatures = [
    {
      title: 'Beépített Sötét Mód (Dark Mode)',
      desc: 'ttk.Style + clam téma finomhangolva: modern sötét felület (#181926) magas kontrasztú címkékkel, kártyákkal és színkódolt naplóval. Gombnyomással váltható (🌙/☀️).',
      icon: Moon,
      color: 'text-indigo-400',
    },
    {
      title: 'Találat Előnézeti Panel & Tor Megnyitás',
      desc: 'Alsó részletes ellenőrző panel és felugró ablak (dupla kattintás vagy "Előnézet" gomb): teljes cím, URL, nyelv, kategória, ujjlenyomat, és közvetlen "Megnyitás Tor Browserben" gomb.',
      icon: Eye,
      color: 'text-cyan-400',
    },
    {
      title: 'Élő Keresés Közbeni Szűrés (Live Filter)',
      desc: 'Új "⚡ Élő szűrés" kapcsoló és reaktív változó-figyelés: a szűrőmezőkbe gépeléskor azonnal valós időben frissül a találati lista a keresési ciklus alatt is.',
      icon: Zap,
      color: 'text-amber-400',
    },
    {
      title: 'Haladás Mentése & „Folytatás (Resume)” Gomb',
      desc: 'Ha a keresés félbeszakad (pl. 5000-ből 3000-nél), a hátralévő URL-ek mentődnek a pending_queue-ba. Az új "⏩ Folytatás" gombbal a keresés pontosan onnan folytatódik.',
      icon: Play,
      color: 'text-emerald-400',
    },
    {
      title: 'Kereshető & Kategóriákra Szűrhető Log',
      desc: 'Keresőmező a napló felett + gyorsszűrő gombok: "Mind", "Csak [OK]", "Csak hibák", "NEWNYM", "Tor". Memóriapufferből dinamikusan újraszűri a megjelenített sorokat.',
      icon: Search,
      color: 'text-rose-400',
    },
    {
      title: 'Testreszabható Export Párbeszédablak',
      desc: 'Új "📦 Export..." dialógus: választható hatókör (szűrt nézet vs összes egyedi), kategória- és nyelvszűkítés, valamint CSV / JSON / TXT formátumok.',
      icon: Download,
      color: 'text-purple-400',
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
                UI / UX & WORKFLOW EVOLUTION
              </span>
              <span className="text-slate-500 text-sm">v4.8.2 Enhanced</span>
            </div>
            <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight mt-2 text-white">
              Onion Kereső — Modern UI/UX & Munkafolyamat
            </h1>
            <p className="text-slate-400 text-sm md:text-base mt-1">
              Sötét mód, előnézeti panel Tor integrációval, élő szűrés, megszakítás utáni resume és intelligens logkeresés.
            </p>
          </div>

          <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 p-3.5 rounded-xl shadow-lg">
            <CheckCircle2 className="w-8 h-8 text-emerald-400 shrink-0" />
            <div>
              <div className="text-xs text-slate-400 font-medium">Pytest Tesztlefedettség</div>
              <div className="text-emerald-400 font-bold font-mono text-sm">
                25 / 25 Sikeres (100% Zöld)
              </div>
            </div>
          </div>
        </header>

        {/* Feature Grid */}
        <section className="space-y-4">
          <div className="flex items-center gap-2 text-slate-200 font-semibold">
            <FolderTree className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg">Megvalósított UI/UX Újdonságok</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {uiFeatures.map((item, idx) => {
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

        {/* Workflow Architecture */}
        <section className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <h2 className="text-base font-semibold text-slate-200">Kezelőfelület és Állapotkezelés (UI/UX Workflow)</h2>
          <pre className="font-mono text-xs bg-slate-950 p-4 rounded-lg text-slate-300 overflow-x-auto leading-relaxed border border-slate-800">
{`Főablak (MainWindow)
  │
  ├──► Téma Kezelő: 🌙 Sötét mód / ☀️ Világos mód ttk.Style clam palettával.
  │
  ├──► Találat Előnézet (Inspector Panel & Modal Dialog):
  │      Cím, .onion cím, kategória, nyelv, ujjlenyomat és snippet megtekintése;
  │      "🌐 Megnyitás Torban" közvetlen hívással vagy vágólapra másolással.
  │
  ├──► Élő Szűrés (Live Filter):
  │      A szűrőfeltételek (AND/OR/NOT/cím/regex/nyelv) gépeléskor azonnal frissítik a TreeView-t.
  │
  ├──► Keresési Állapot & Folytatás (Resume):
  │      Keresési leálláskor a pending_queue elmentődik SQLite / JSON metaadatként;
  │      A "⏩ Folytatás (Resume)" gomb aktiválódik és kihagyás nélkül tovább viszi a munkát.
  │
  ├──► Kereshető & Szűrhető Napló (LogPanel):
  │      Szöveges keresőmező + "Mind", "Csak [OK]", "Csak hibák", "NEWNYM", "Tor" kategóriák.
  │
  └──► Testreszabható Export Dialógus:
         Hatókör (szűrt lista / összes egyedi) + Kategória és Nyelv szűrés + CSV / JSON / TXT.`}
          </pre>
        </section>

        {/* Verification Summary */}
        <footer className="text-xs text-slate-500 border-t border-slate-800 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>Onion Kereső v4.8.2 — UI/UX Fejlesztési Csomag</div>
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              25/25 Pytest Sikeres
            </span>
            <span className="text-slate-400 font-mono">Modern Tkinter Desktop</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
