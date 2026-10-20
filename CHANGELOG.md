# Changelog

## [5.0.1] - 2026-10-20

### Biztonság
- **Tor-only kikényszerítés és központi net_guard**
  - Új `onion_search/utils/net_guard.py` modul szigorú `socks5h://` ellenőrzéssel a DNS-szivárgások teljes megelőzésére.
  - Szigorú `TorOnlyViolation` kivétel dobása és `[SECURITY]` naplózás szanitizált (query paraméterek nélküli) URL-ekkel, amennyiben proxy hiányában clearnet kérés indulna.
  - Az összes HTTP hálózati kérés (`search_onionsearchengine`, `search_ahmia`, `fetch_github_seeds`, `RobotsChecker`, `fetch_page`, `fetch_url`, seed pluginok) átirányítása a központi guardon keresztül.
  - SOCKS5h séma kötelezővé tétele sima `socks5://` helyett.
  - Maximális válaszméret korlátozás (`MAX_RESPONSE_BYTES = 2MB`) streamelt és darabolt beolvasással (`too_large` hiba státusz).
  - Nem `.onion` átirányítások (redirect) blokkolása `allow_clearnet = False` mellett (`filtered` státusszal).
  - Új `tests/test_tor_guard.py` tesztkészlet és statikus AST forráskód ellenőrzés a kimenő kérések központi védelmének igazolására.

## [5.0.0] - 2026-10-20

### Hozzáadva
- **Tor kapcsolat diagnosztika és automatikus beállítás**
  - 9050 / 9150 SOCKS + ControlPort ellenőrzés
  - IsTor verifikáció, válaszidő mérés
  - Fast-path a legutóbb működő portra
  - Részletes, magyar nyelvű hibaüzenetek és megoldási javaslatok
  - Manuális újrafuttatás az Eszközök menüből
- **Átfogó tabbed Beállítások dialógus** (Ctrl+,)
  - Tor / Hálózat, Crawler, Szűrés, Adatbázis, Általános fülek
  - Validáció, alapértelmezések visszaállítása, tooltip-ek
- **Plugin-alapú seed rendszer**
  - `BaseSeedPlugin` absztrakt interfész
  - Automatikus plugin-felfedezés (`seeds/plugins/`)
  - `SeedOrchestrator` prioritásos kaszkád + health-check
  - Beépített pluginok: Tor66, Deep Search, Haystak, OnionLand, GitHub, OSE, Torch, not Evil, Ahmia
  - `CustomUrlRegexPlugin` (egyéni URL + regex/CSS)
  - Vizuális állapotjelzők (🟢/🟡/🔴) a GUI-ban
- **Cserélhető Storage absztrakció**
  - `BaseStorage` protokoll
  - `SQLiteStorage` (WAL mód, batch insert, indexek, busy timeout)
  - `StorageFactory` + regisztrálható backend-ek
  - JSON backend + PostgreSQL váz a jövőbeli skálázáshoz
- Konfigurálható Tor timeout-ok (`tor_tcp_timeout`, `tor_socks_timeout`)
- Port és beállítások tartós mentése

### Megváltoztatva
- Seed gyűjtés teljesen plugin-alapúvá alakítva (visszamenőleges kompatibilitás megmaradt)
- Storage réteg absztrakt interfész mögé rejtve
- Beállítások centralizálva a tabbed dialógusba

### Javítva
- Indítási race condition a Tor diagnosztikánál
- SQLite írási lock és teljesítmény (WAL + batch)
- Seed források törékenysége (health-check + automatikus kihagyás)

## [4.9.4] - 2026-10-18
### Hozzáadva
- URL normalizálás (`normalize_onion_url`)
- Erősebb tartalom-fingerprint SHA-256 alapú 20 hex karakteres azonosítóval
- `result_urls` O(1) deduplikáció
- `normalize_to_host_only` konfigurációs opció
- Klasszikus menüsáv (Fájl, Keresés, Beállítások, Nézet, Súgó) és letisztultabb főképernyő (UI/UX)

### Javítva
- Ismétlődő találatok szűrése kereséskor és állapot betöltésekor
- Lassú URL-duplikátum ellenőrzés
- Worker alapértelmezés 6, domain delay 0.7s
- Ahmia ≥30 találat esetén OnionSearchEngine kihagyása
- UI batch frissítés, ritkább incremental mentés

### Megváltoztatva
- Főképernyő: ritka beállítások menübe és párbeszédablakokba kerültek
