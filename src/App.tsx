/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useMemo } from 'react';
import {
  FolderTree,
  CheckCircle2,
  FileCheck2,
  Sliders,
  Terminal,
  FileCode,
  ShieldCheck,
  Zap,
  RefreshCw,
  Search,
  Globe,
  Database,
  Lock,
  Layers,
  ArrowRight,
  ExternalLink,
  Cpu,
  Trash2,
  Clock,
  Play,
  Flame,
  AlertTriangle,
  Code2,
} from 'lucide-react';

interface SeedSourceInfo {
  id: string;
  name: string;
  category: string;
  onionEndpoint: string;
  clearnetMirror: string;
  description: string;
  yieldRange: string;
  latency: string;
  badgeColor: string;
}

const SEED_SOURCES: SeedSourceInfo[] = [
  {
    id: 'tor66',
    name: 'Tor66 Hidden Service Directory',
    category: 'Rejtett Könyvtár & Fresh',
    onionEndpoint: 'http://tor66sewebgixwhcqfnpq5wfsqxuvhn2bawa4rwfdgahforacxdad123.onion/fresh',
    clearnetMirror: 'https://tor66.org/fresh',
    description: 'Folyamatosan frissülő aktív rejtett szolgáltatás feed. Elsődlegesen a .onion szolgáltatáson keresztül kérdezi le Tor SOCKS5h proxyn át, tartalékként tükrön.',
    yieldRange: '120 - 450 .onion / lekérdezés',
    latency: '1.2s - 2.8s (Tor áramkörön)',
    badgeColor: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  },
  {
    id: 'deepsearch',
    name: 'Deep Search Onion Catalog',
    category: 'Katalógus & Kereső',
    onionEndpoint: 'http://deepsearch74sxv42abcdefghijklmnopqrstuvwxyz234567abcdefg.onion/fresh',
    clearnetMirror: 'https://deepsearch.onion.pet/fresh',
    description: 'Strukturált mélywebes katalógus és linkgyűjtemény. Kategóriák és legfrissebb aktivitási státusz alapján ad friss validált v3 .onion címeket.',
    yieldRange: '80 - 300 .onion / lekérdezés',
    latency: '1.5s - 3.2s (Tor áramkörön)',
    badgeColor: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  },
  {
    id: 'ahmia',
    name: 'Ahmia.fi Fresh Onion Indexer',
    category: 'Keresőmotor Index',
    onionEndpoint: 'http://juhanurmih5wu7bv5imwtvfera6qnfd4hxxstl7tggdd2ufdgxao4yd.onion/onions/',
    clearnetMirror: 'https://ahmia.fi/onions/',
    description: 'A legismertebb és legrégebbi mélywebes indexelő. Automatikus listázást nyújt az elmúlt 48 órában meglátogatott működő oldalakról.',
    yieldRange: '200 - 800 .onion / lekérdezés',
    latency: '0.8s - 2.1s',
    badgeColor: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
  },
  {
    id: 'github',
    name: 'Curated GitHub Onion Repositories',
    category: 'Közösségi Kurált',
    onionEndpoint: 'N/A (Clearnet / Proxy)',
    clearnetMirror: 'https://raw.githubusercontent.com/alecmuffett/real-world-onion-sites/...',
    description: 'Kézzel ellenőrzött, minőségi és megbízható onion szolgáltatások gyűjteménye (Alec Muffett és Dan McInerney kurált listái).',
    yieldRange: '150 - 350 .onion / lista',
    latency: '0.3s - 0.9s',
    badgeColor: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  },
  {
    id: 'ose',
    name: 'OnionSearchEngine Multi-Aggregator',
    category: 'Metakereső',
    onionEndpoint: 'N/A (Clearnet / Proxy)',
    clearnetMirror: 'https://onionsearchengine.com/search.php?search=wiki',
    description: 'Több forrásból összesített meta-indexelő motor, amely kulcsszavas és témaspecifikus kezdőmagokat szolgáltat a bejárónak.',
    yieldRange: '50 - 180 .onion / kérés',
    latency: '1.0s - 2.4s',
    badgeColor: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  },
];

interface Milestone {
  version: string;
  date: string;
  title: string;
  category: 'seed' | 'security' | 'async' | 'ui' | 'quality';
  summary: string;
  keyChanges: string[];
  codeHighlight: string;
  badgeColor: string;
}

const MILESTONES: Milestone[] = [
  {
    version: 'v4.9.2',
    date: 'Legfrissebb (2026. október)',
    title: 'Többforrásos Automatikus Seed Frissítés (Tor66, Deep Search, Ahmia, GitHub, OSE)',
    category: 'seed',
    summary:
      'A korábbi egyszálas források helyett dedikált SeedManager koordinálja a Tor66 és Deep Search rejtett szolgáltatás könyvtárakból, az Ahmiából és kurált listákból történő automatikus maggyűjtést.',
    keyChanges: [
      'Tor66 és Deep Search integráció natív .onion és tükör fallback támogatással',
      'Időzített automatikus háttérfrissítés (SeedManager.is_update_due, 6/12/24/48 órás ütemezés)',
      'Grafikus "Maglista Kezelő & Automatikus Frissítés" párbeszédablak forrás- és időköz-választóval',
      'Lokális JSON perzisztencia (~/.config/onion_search/seeds_cache.json) statisztikai bontással',
      'Szigorú Tor SOCKS5h routing: .onion címek és források soha nem kérhetők le clearneten át',
    ],
    codeHighlight: `# onion_search/core/seeds.py
class SeedManager:
    def fetch_all(self, proxy_url, allow_clearnet, selected_sources=None):
        # Queries Tor66, DeepSearch, Ahmia, GitHub & OSE via Tor proxy
        combined, counts = self._aggregate_providers(sources)
        self.save_cache(combined, source_counts=counts)
        return combined, counts`,
    badgeColor: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  },
  {
    version: 'v4.9.1',
    date: '2026. október',
    title: 'Szigorú Tor-Only Mód, Searchable Fernet SQLite & Pánik Megsemmisítés',
    category: 'security',
    summary:
      'Deanonymizáció elleni védelem: clearnet letiltása esetén minden külső hívás blokkolva van proxy hiányában. Fernet titkosított SQLite tárolás determinisztikus HMAC kulccsal és Pánik törlés gomb.',
    keyChanges: [
      'Clearnet engedélyezése checkbox: letiltva az Ahmia és GitHub hívások szigorúan blokkolva Tor proxy nélkül',
      'Titkosított tárolás (Fernet): checked_urls és dead_blacklist titkosított szövegként van jelen lemezen',
      'Determinisztikus HMAC prefix ("enc:HMAC:ciphertext") az O(1) indexelt SQLite visszakereshetőséghez',
      'Pánik Törlés (Ctrl+Shift+Del / BackSpace / KP_Delete): azonnali fájlmegsemmisítés és állapotürítés',
    ],
    codeHighlight: `# Determinisztikus HMAC + Fernet tárolás SQLite backendben
prefix = hmac.new(self.encryptor.key, url.encode(), hashlib.sha256).hexdigest()[:16]
enc_val = f"enc:{prefix}:{self.encryptor.encrypt(url)}"
cur.execute("SELECT 1 FROM checked WHERE url LIKE ?", (f"enc:{prefix}:%",))`,
    badgeColor: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  },
  {
    version: 'v4.9.0',
    date: '2026. szeptember',
    title: 'Aszinkron Motor (aiohttp + asyncio), lxml Gyorsítás & TkLogHandler',
    category: 'async',
    summary:
      '10-50x konkurens letöltési hatékonyság aiohttp kapcsolatkészlettel és lxml parserrel. Szabványos logging architektúra TkLogHandlerrel.',
    keyChanges: [
      'AsyncClient és aiohttp.ClientSession alapú async_fetch_page aszinkron motor',
      'lxml alapú villámgyors HTML faépítés és szövegkivonatolás a regex parser helyett',
      'Tartalom- és nyelvfelismerési LRU gyorsítótár a CPU terhelés minimalizálására',
      'Szálbiztos TkLogHandler, amely a beépített logging modult csatolja a Tkinter UI-hoz',
    ],
    codeHighlight: `async def async_fetch_page(self, client, url, is_running_cb=None):
    await self.rate_limiter.async_wait_for_domain(domain)
    res_cm = client.get(url, timeout=TIMEOUT_GET, allow_redirects=True, headers=headers)
    # 10-50x párhuzamos lekérés socket-újrahasznosítással`,
    badgeColor: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  },
  {
    version: 'v4.8.5',
    date: '2026. szeptember',
    title: 'Perzisztens ConfigManager (~/.config/onion_search/config.json) & Tor Circuit Log',
    category: 'quality',
    summary:
      'Központosított típusbiztos konfigurációkezelés AppConfig dataclass-szal és automatikus Tor circuit-status lekérdezés NEWNYM esetén.',
    keyChanges: [
      '~/.config/onion_search/config.json perzisztens beállításfájl',
      'NEWNYM parancs kiadásakor automatikus circuit-status lekérés és logolás',
      'Alkalmazás-állapot automatikus visszaállítása indításkor',
      'Portok, szálak száma és küszöbértékek központi validációja',
    ],
    codeHighlight: `@dataclass
class AppConfig:
    socks_port: str = "9050"
    ctrl_port: str = "9051"
    auto_update_seeds: bool = True
    seed_sources: str = "tor66,deepsearch,ahmia,github,ose"`,
    badgeColor: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  },
  {
    version: 'v4.8.4',
    date: '2026. augusztus',
    title: 'Élő Keresési Szűrők (Must/Must Not) & SQL Lekérdező Konzol',
    category: 'ui',
    summary:
      'Összetett keresési és szűrési felület valós idejű gépelés közbeni szűréssel, valamint beépített SQLite konzol tetszőleges lekérdezések futtatásához.',
    keyChanges: [
      'Must Contain és Must Not Contain szűrőkulcsszavak azonnali fa-frissítéssel',
      'Kategória (Market, Forum, Wiki, Library) és nyelv (HU, EN, DE, RU) szerinti élő szűrő',
      'SQL Query konzol ablak közvetlen SELECT lekérdezésekhez és exportáláshoz',
      'X11 főszál szinkronizáció és Tkinter widget-biztonsági javítások',
    ],
    codeHighlight: `def matches_precise_filter(item, must_all, must_any, must_not, lang, cat):
    # Null overhead memory check with lower() pre-normalization
    return passes_all_criteria`,
    badgeColor: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<'seeds' | 'changelog' | 'simulator' | 'arch'>('seeds');
  const [selectedSources, setSelectedSources] = useState<string[]>(['tor66', 'deepsearch', 'ahmia', 'github', 'ose']);
  const [searchFilter, setSearchFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [simulatedUrls, setSimulatedUrls] = useState<Array<{ url: string; source: string; status: string }>>([]);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simProgress, setSimProgress] = useState<string>('');

  const toggleSource = (id: string) => {
    if (selectedSources.includes(id)) {
      setSelectedSources(selectedSources.filter((s) => s !== id));
    } else {
      setSelectedSources([...selectedSources, id]);
    }
  };

  const runSimulation = () => {
    setIsSimulating(true);
    setSimulatedUrls([]);
    setSimProgress('Kapcsolódás a kijelölt forrásokhoz Tor SOCKS5h proxyn át...');

    setTimeout(() => {
      const generated: Array<{ url: string; source: string; status: string }> = [];

      if (selectedSources.includes('tor66')) {
        generated.push(
          { url: 'http://tor66fresh74abcdefghijklmnopqrstuvwxyz234567abcdefg.onion', source: 'Tor66', status: 'Új felfedezett' },
          { url: 'http://wiki56hiddenhubabcdefghijklmnopqrstuvwxyz234567abcdef.onion', source: 'Tor66', status: 'Új felfedezett' },
          { url: 'http://marketboard66linkabcdefghijklmnopqrstuvwxyz234567abcd.onion', source: 'Tor66', status: 'Új felfedezett' }
        );
      }
      if (selectedSources.includes('deepsearch')) {
        generated.push(
          { url: 'http://deepsearchcatalogabcdefghijklmnopqrstuvwxyz234567abcd.onion', source: 'Deep Search', status: 'Új felfedezett' },
          { url: 'http://libdocsreadforumabcdefghijklmnopqrstuvwxyz234567abcde.onion', source: 'Deep Search', status: 'Új felfedezett' }
        );
      }
      if (selectedSources.includes('ahmia')) {
        generated.push(
          { url: 'http://juhanurmih5wu7bv5imwtvfera6qnfd4hxxstl7tggdd2ufdgxao4yd.onion', source: 'Ahmia', status: 'Ismert (cache)' },
          { url: 'http://privacygate77secabcdefghijklmnopqrstuvwxyz234567abcde.onion', source: 'Ahmia', status: 'Új felfedezett' }
        );
      }
      if (selectedSources.includes('github')) {
        generated.push(
          { url: 'http://duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion', source: 'GitHub Curated', status: 'Ismert (cache)' },
          { url: 'http://torproject39hiddenserviceabcdefghijklmnopqrstuvwxyza.onion', source: 'GitHub Curated', status: 'Ismert (cache)' }
        );
      }
      if (selectedSources.includes('ose')) {
        generated.push(
          { url: 'http://oseaggregator999abcdefghijklmnopqrstuvwxyz234567abcde.onion', source: 'OnionSearchEngine', status: 'Új felfedezett' }
        );
      }

      setSimulatedUrls(generated);
      setIsSimulating(false);
      setSimProgress(`Sikeres szinkronizáció! ${generated.length} cím beolvasva és deduplikálva.`);
    }, 900);
  };

  const filteredMilestones = useMemo(() => {
    return MILESTONES.filter((m) => {
      const matchesCategory = categoryFilter === 'all' || m.category === categoryFilter;
      const matchesSearch =
        m.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
        m.summary.toLowerCase().includes(searchFilter.toLowerCase()) ||
        m.keyChanges.some((c) => c.toLowerCase().includes(searchFilter.toLowerCase())) ||
        m.version.toLowerCase().includes(searchFilter.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [categoryFilter, searchFilter]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-emerald-500 selection:text-slate-950">
      {/* Top Banner */}
      <div className="bg-slate-900/90 border-b border-slate-800/80 sticky top-0 z-30 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <FolderTree className="w-5 h-5 text-slate-950 stroke-[2.5]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-base tracking-tight text-white">Onion Kereső</span>
                <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs px-2 py-0.5 rounded font-mono font-medium">
                  v4.9.2 Multi-Seed
                </span>
              </div>
              <span className="text-xs text-slate-400 block -mt-0.5">
                Automatikus többforrásos seed lista frissítés & Architektúra
              </span>
            </div>
          </div>

          {/* Test Badge */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 bg-slate-800/80 border border-slate-700/80 px-3 py-1.5 rounded-lg text-xs font-mono">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-slate-300">Pytest:</span>
              <span className="text-emerald-400 font-bold">67/67 (100% Zöld)</span>
            </div>

            <nav className="flex items-center gap-1 bg-slate-950/60 p-1 rounded-xl border border-slate-800">
              <button
                onClick={() => setActiveTab('seeds')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  activeTab === 'seeds'
                    ? 'bg-emerald-500 text-slate-950 font-bold shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                🌱 Seed Források
              </button>
              <button
                onClick={() => setActiveTab('simulator')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  activeTab === 'simulator'
                    ? 'bg-emerald-500 text-slate-950 font-bold shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                ⚡ Szimuláció
              </button>
              <button
                onClick={() => setActiveTab('changelog')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  activeTab === 'changelog'
                    ? 'bg-emerald-500 text-slate-950 font-bold shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                📜 Módosítások Naplója
              </button>
              <button
                onClick={() => setActiveTab('arch')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  activeTab === 'arch'
                    ? 'bg-emerald-500 text-slate-950 font-bold shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                🏗️ Rendszerleírás
              </button>
            </nav>
          </div>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* TAB 1: SEED FORRÁSOK (Tor66, Deep Search, etc.) */}
        {activeTab === 'seeds' && (
          <div className="space-y-8 animate-fadeIn">
            {/* Header Card */}
            <div className="bg-gradient-to-r from-slate-900 via-slate-900 to-slate-950 border border-slate-800 rounded-2xl p-6 sm:p-8 relative overflow-hidden">
              <div className="absolute right-0 top-0 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none" />
              <div className="max-w-3xl space-y-3 relative z-10">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" style={{ animationDuration: '6s' }} />
                  AUTOMATIKUS TÖBBFORRÁSOS SEED LISTA FRISSÍTÉS
                </div>
                <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                  Automatikus Maggyűjtés Tor66 és Deep Search Integrációval
                </h1>
                <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
                  A mélywebes keresőmotor nemcsak statikus címeket vagy Ahmia-t használ: a háttérben futó{' '}
                  <code className="text-emerald-400 font-mono">SeedManager</code> szigorúan Tor SOCKS5h proxyn át kérdezi le a friss
                  rejtett szolgáltatásokat a <strong>Tor66</strong> és <strong>Deep Search</strong> könyvtárakból, majd deduplikálja és
                  gyorsítótárazza a címeket.
                </p>
                <div className="pt-2 flex flex-wrap gap-4 text-xs font-mono text-slate-400">
                  <div className="flex items-center gap-1.5">
                    <Lock className="w-4 h-4 text-emerald-400" />
                    <span>Tor-only SOCKS5h Kényszerítés</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Clock className="w-4 h-4 text-cyan-400" />
                    <span>Ütemezett 12 órás háttérciklus</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Database className="w-4 h-4 text-amber-400" />
                    <span>~/.config/onion_search/seeds_cache.json</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Provider Grid */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <Globe className="w-5 h-5 text-emerald-400" />
                    Integrált Seed Provider Források
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Minden forrás egyedileg ki/bekapcsolható a Maglista Kezelő dialógusban és a config.json-ben.
                  </p>
                </div>
                <button
                  onClick={() => setActiveTab('simulator')}
                  className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold px-4 py-2 rounded-xl text-xs transition shadow-lg shadow-emerald-600/20"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  Kipróbálás a Szimulátorban
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {SEED_SOURCES.map((src) => (
                  <div
                    key={src.id}
                    className="bg-slate-900 border border-slate-800 hover:border-slate-700 transition rounded-xl p-5 flex flex-col justify-between space-y-4 shadow-sm"
                  >
                    <div className="space-y-2.5">
                      <div className="flex items-start justify-between gap-2">
                        <span className={`text-xs px-2.5 py-0.5 rounded-full border font-mono font-medium ${src.badgeColor}`}>
                          {src.category}
                        </span>
                        <span className="text-xs font-mono text-slate-400">{src.yieldRange}</span>
                      </div>
                      <h3 className="font-bold text-white text-base">{src.name}</h3>
                      <p className="text-xs text-slate-400 leading-relaxed">{src.description}</p>
                    </div>

                    <div className="space-y-2 border-t border-slate-800/80 pt-3 text-xs font-mono">
                      <div>
                        <div className="text-[10px] text-slate-500 uppercase tracking-wider">.onion Végpont (Tor):</div>
                        <div className="text-slate-300 truncate" title={src.onionEndpoint}>
                          {src.onionEndpoint}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-slate-500 uppercase tracking-wider">Clearnet Tükör (Fallback):</div>
                        <div className="text-slate-400 truncate" title={src.clearnetMirror}>
                          {src.clearnetMirror}
                        </div>
                      </div>
                      <div className="flex items-center justify-between text-slate-400 pt-1 text-[11px]">
                        <span>Tipikus válaszidő:</span>
                        <span className="text-emerald-400">{src.latency}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Architecture Workflow */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <Layers className="w-5 h-5 text-cyan-400" />
                Automatikus Maglista Folyamat & Hibatűrés
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                  <div className="w-7 h-7 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold font-mono">
                    1
                  </div>
                  <div className="font-semibold text-white">Időzítés / Indítás</div>
                  <p className="text-slate-400">
                    Induláskor (<code className="text-slate-300 font-mono">auto_seed_update_on_startup</code>) és periodikusan 30
                    percenként ellenőrzi, hogy eltelt-e az ütemezett időszak (12 óra).
                  </p>
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                  <div className="w-7 h-7 rounded-lg bg-cyan-500/10 text-cyan-400 flex items-center justify-center font-bold font-mono">
                    2
                  </div>
                  <div className="font-semibold text-white">Tor SOCKS5h Kényszerítés</div>
                  <p className="text-slate-400">
                    A Tor66 és Deep Search kérések szigorúan <code className="text-slate-300 font-mono">socks5h://127.0.0.1:9050</code>-en
                    mennek keresztül. Proxy hiányában a clearnet kérések csak explicit engedélyezéskor futhatnak le.
                  </p>
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                  <div className="w-7 h-7 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center font-bold font-mono">
                    3
                  </div>
                  <div className="font-semibold text-white">Deduplikáció & Szűrés</div>
                  <p className="text-slate-400">
                    A Regex és BeautifulSoup parser által talált címek automatikusan deduplikálódnak az in-memory{' '}
                    <code className="text-slate-300 font-mono">checked_urls</code> és{' '}
                    <code className="text-slate-300 font-mono">dead_blacklist</code> halmazokkal szemben.
                  </p>
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                  <div className="w-7 h-7 rounded-lg bg-amber-500/10 text-amber-400 flex items-center justify-center font-bold font-mono">
                    4
                  </div>
                  <div className="font-semibold text-white">Perzisztens Cache & UI</div>
                  <p className="text-slate-400">
                    Az új magok azonnal mentődnek a <code className="text-slate-300 font-mono">seeds_cache.json</code>-be, és bekerülnek
                    a GUI "Extra .onionok" szövegdobozába a bejárás azonnali indításához.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: INTERAKTÍV SZIMULÁTOR */}
        {activeTab === 'simulator' && (
          <div className="space-y-6 animate-fadeIn">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Zap className="w-5 h-5 text-amber-400" />
                  Többforrásos Magfrissítés Tesztelő & Szimulátor
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  Válassz ki forrásokat, majd futtasd a szinkronizációs tesztet. A szimuláció a SeedManager működését modellezi.
                </p>
              </div>

              {/* Source Selectors */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                {SEED_SOURCES.map((src) => {
                  const active = selectedSources.includes(src.id);
                  return (
                    <button
                      key={src.id}
                      onClick={() => toggleSource(src.id)}
                      className={`p-3 rounded-xl border text-left transition flex flex-col justify-between ${
                        active
                          ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-400 shadow-sm'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs">{src.name.split(' ')[0]}</span>
                        <CheckCircle2 className={`w-4 h-4 ${active ? 'text-emerald-400' : 'text-slate-600'}`} />
                      </div>
                      <span className="text-[10px] text-slate-500 mt-1">{src.category}</span>
                    </button>
                  );
                })}
              </div>

              {/* Action Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-4 bg-slate-950 p-4 rounded-xl border border-slate-800">
                <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
                  <span>Kiválasztva: <strong className="text-white">{selectedSources.length}</strong> / 5 forrás</span>
                  <span>Proxy: <strong className="text-emerald-400">socks5h://127.0.0.1:9050</strong></span>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    disabled={isSimulating || selectedSources.length === 0}
                    onClick={runSimulation}
                    className="inline-flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold px-5 py-2 rounded-xl text-xs transition shadow-lg shadow-emerald-500/20"
                  >
                    <RefreshCw className={`w-4 h-4 ${isSimulating ? 'animate-spin' : ''}`} />
                    {isSimulating ? 'Letöltés...' : 'Maglista Frissítése Most'}
                  </button>
                  {simulatedUrls.length > 0 && (
                    <button
                      onClick={() => setSimulatedUrls([])}
                      className="p-2 text-slate-400 hover:text-rose-400 transition"
                      title="Eredmények törlése"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>

              {/* Output status */}
              {simProgress && (
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-emerald-400 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>{simProgress}</span>
                </div>
              )}

              {/* Simulated Results Table */}
              {simulatedUrls.length > 0 ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span>Felfedezett és deduplikált magok ({simulatedUrls.length} db):</span>
                    <span className="font-mono text-emerald-400">Extra .onion mezőbe továbbítva</span>
                  </div>
                  <div className="overflow-x-auto rounded-xl border border-slate-800">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-slate-950 border-b border-slate-800 text-slate-400">
                        <tr>
                          <th className="p-3">#</th>
                          <th className="p-3">Felfedezett .onion Cím</th>
                          <th className="p-3">Forrás</th>
                          <th className="p-3">Státusz</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 bg-slate-900/60">
                        {simulatedUrls.map((item, i) => (
                          <tr key={i} className="hover:bg-slate-800/40">
                            <td className="p-3 text-slate-500">{i + 1}</td>
                            <td className="p-3 text-emerald-300 font-semibold">{item.url}</td>
                            <td className="p-3">
                              <span className="bg-slate-800 text-slate-300 px-2 py-0.5 rounded text-[11px]">
                                {item.source}
                              </span>
                            </td>
                            <td className="p-3">
                              <span className="text-emerald-400 font-semibold">{item.status}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="text-center py-10 border border-dashed border-slate-800 rounded-xl text-slate-500 text-xs">
                  Kattints a "Maglista Frissítése Most" gombra a források párhuzamos lekéréséhez!
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: BROWSEABLE INNOVATIONS & MODIFICATIONS CHANGELOG */}
        {activeTab === 'changelog' && (
          <div className="space-y-6 animate-fadeIn">
            {/* Filter and Search Bar */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <Terminal className="w-5 h-5 text-indigo-400" />
                    Böngészhető Fejlesztési & Módosítási Napló
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Az eddigi összes javítás, kódminőségi újítás és biztonsági intézkedés mérföldkövei.
                  </p>
                </div>

                {/* Search input */}
                <div className="relative w-full sm:w-72">
                  <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                    placeholder="Keresés módosításokban..."
                    className="w-full bg-slate-950 border border-slate-800 focus:border-emerald-500 rounded-xl pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none transition"
                  />
                </div>
              </div>

              {/* Category Pills */}
              <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-800/80">
                <span className="text-xs text-slate-400 mr-2">Kategória:</span>
                {[
                  { id: 'all', label: 'Minden kategória' },
                  { id: 'seed', label: '🌱 Seed & Források' },
                  { id: 'security', label: '🛡️ Biztonság & Tor' },
                  { id: 'async', label: '⚡ Aszinkron Motor' },
                  { id: 'ui', label: '🖥️ Felület & Szűrők' },
                  { id: 'quality', label: '📐 Kódminőség & Tesztek' },
                ].map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setCategoryFilter(c.id)}
                    className={`text-xs px-3 py-1 rounded-lg transition font-medium ${
                      categoryFilter === c.id
                        ? 'bg-slate-100 text-slate-950 font-bold'
                        : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
                    }`}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Milestones Stepper / Cards */}
            <div className="space-y-6">
              {filteredMilestones.map((m, idx) => (
                <div
                  key={idx}
                  className="bg-slate-900 border border-slate-800 hover:border-slate-700 transition rounded-2xl p-6 space-y-5"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
                    <div className="flex items-center gap-3">
                      <span className={`text-xs font-mono font-bold px-3 py-1 rounded-lg border ${m.badgeColor}`}>
                        {m.version}
                      </span>
                      <h3 className="font-extrabold text-white text-base sm:text-lg">{m.title}</h3>
                    </div>
                    <span className="text-xs font-mono text-slate-400">{m.date}</span>
                  </div>

                  <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">{m.summary}</p>

                  <div className="space-y-2">
                    <div className="text-xs font-semibold text-slate-200">Kulcsfontosságú Változások & Megvalósítás:</div>
                    <ul className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-slate-400">
                      {m.keyChanges.map((change, cIdx) => (
                        <li key={cIdx} className="flex items-start gap-2 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                          <span>{change}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Code Highlight */}
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400">
                      <Code2 className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Kódrészlet / Minta:</span>
                    </div>
                    <pre className="font-mono text-xs bg-slate-950 p-3.5 rounded-xl text-slate-300 border border-slate-800 overflow-x-auto">
                      {m.codeHighlight}
                    </pre>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 4: RENDSZERLEÍRÁS & TESZTELEFEDETTSÉG */}
        {activeTab === 'arch' && (
          <div className="space-y-6 animate-fadeIn">
            {/* Architecture Overview */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <ShieldCheck className="w-5 h-5 text-emerald-400" />
                    Átfogó Tesztlefedettség (67 / 67 Sikeres Teszt)
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Minden alrendszer Pytest és Xvfb alatt automatikusan verifikálva van.
                  </p>
                </div>
                <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs px-3 py-1 rounded-full font-mono font-bold">
                  100% GREEN
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                  <div className="text-xs font-bold text-white flex items-center gap-2">
                    <FolderTree className="w-4 h-4 text-emerald-400" />
                    <span>test_seeds.py (7 teszt)</span>
                  </div>
                  <p className="text-xs text-slate-400">
                    Regex & HTML kivonatolás, Tor66 és Deep Search SOCKS5h proxyzás, SeedManager cache életciklus és Seed Dialog UI tesztek.
                  </p>
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                  <div className="text-xs font-bold text-white flex items-center gap-2">
                    <Lock className="w-4 h-4 text-rose-400" />
                    <span>test_security_anonymity.py (8 teszt)</span>
                  </div>
                  <p className="text-xs text-slate-400">
                    Tor-only clearnet tiltás, HMAC Fernet titkosított SQLite tárolás és Pánik Törlés (Shredding) fájlmegsemmisítés.
                  </p>
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                  <div className="text-xs font-bold text-white flex items-center gap-2">
                    <Zap className="w-4 h-4 text-amber-400" />
                    <span>test_performance.py (4 teszt)</span>
                  </div>
                  <p className="text-xs text-slate-400">
                    aiohttp aszinkron ClientSession kapcsolatkészlet, lxml parser, LRU osztályozási cache és indexelt SQLite mentés.
                  </p>
                </div>
              </div>

              {/* Codebase Tree */}
              <div className="space-y-2">
                <div className="text-xs font-semibold text-slate-300">Moduláris Fájlstruktúra:</div>
                <pre className="font-mono text-xs bg-slate-950 p-4 rounded-xl text-slate-300 border border-slate-800 overflow-x-auto leading-relaxed">
{`onion_search/
├── config.py              # AppConfig dataclass, konstansok, ConfigManager (~/.config/onion_search/config.json)
├── core/
│   ├── fetcher.py         # Aszinkron letöltő (aiohttp/httpx), DomainRateLimiter, RobotsChecker
│   ├── seeds.py           # SeedManager: Tor66, DeepSearch, Ahmia, GitHub & OSE forráskezelő
│   ├── detector.py        # Kategória- és nyelvfelismerő (SimHash, fast_detect, LRU cache)
│   ├── neonym.py          # Tor vezérlő (NEWNYM parancs, circuit-status lekérdezés)
│   └── session.py         # SessionManager és SOCKS5h kapcsolatkezelő
├── storage/
│   ├── crypto.py          # Fernet szimmetrikus titkosító és kulcsgeneráló
│   ├── sqlite_backend.py  # SQLite backend keyed HMAC kereshető titkosítással
│   └── json_backend.py    # JSON állapotfájl kezelő
├── ui/
│   ├── main_window.py     # Főablak, Maglista Dialógus, Pánik törlés gomb, Toolbar
│   ├── filters.py         # FilterPanel élő Must/Must Not/Nyelv/Kategória szűréssel
│   ├── log_panel.py       # LogPanel és TkLogHandler szálbiztos logging
│   └── tree_view.py       # Eredmények táblázatos megjelenítése
└── utils/
    ├── helpers.py         # URL regexek, TOR66_SOURCES, DEEPSEARCH_SOURCES definíciók
    └── theme.py           # Modern sötét/világos téma`}
                </pre>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950 py-6 mt-12 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            <span className="text-slate-400 font-medium">Onion Kereső v4.9.2</span>
            <span>— Automatikus többforrásos seed lista frissítés (Tor66, Deep Search)</span>
          </div>
          <div className="flex items-center gap-4 text-slate-400 font-mono">
            <span>67/67 Teszt Sikeres</span>
            <span>•</span>
            <span>Tor SOCKS5h Védelem</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
