# Changelog

## [5.0.2] - 2026-10-21

### Biztonság (2. fázis)
- **Pánikgomb billentyűkötés tisztítása**: A szövegmezős gépelést zavaró `Ctrl+Delete` és `Ctrl+KP_Delete` kötés törlése, megőrizve a `Ctrl+Shift+Delete`, `Ctrl+Shift+KP_Delete` és `Ctrl+Shift+BackSpace` parancsokat.
- **Szigorú kulcsfájl jogosultságkezelés**: Titkosítási kulcsfájl létrehozása atomi `O_CREAT | O_EXCL | O_WRONLY` móddal `0o600` jogosultsággal, a szülő mappa `0o700` védelmével és a létező fájlok automatikus felülvizsgálatával/szigorításával POSIX rendszereken.
- **Erős jelszó alapú kulcsszármaztatás**: PBKDF2HMAC(SHA256, length=32, iterations=600_000) alkalmazása 16 bájtos véletlen sóval (`.storage.salt`, `0o600`), visszafelé kompatibilis SHA-256 dekódolási ággal és figyelmeztetéssel.
- **Konfigurációs és adatbázisfájlok védelme**: Közös `secure_write_text` és `ensure_private_dir` segédfüggvények használata a `config.json`, SQLite (`onion.db`) és JSON állapotfájlok atomi `0o600` jogosultságú mentéséhez.
- **Tor cookie keresés optimalizálása**: A lassú, teljes home mappát bejáró rekurzív `rglob` eltávolítása, helyette fix útvonalak, célzott glob minták és a `TOR_CONTROL_COOKIE` környezeti változó támogatása.
- **Tor Browser User-Agent profil**: User-Agent rotáció kikapcsolása alapértelmezésben (`DEFAULT_USER_AGENT_ROTATE = False`), egységes Tor Browser ESR profil (`TOR_BROWSER_UA`) használata és szálbiztos dinamikus frissítés.
- **ReDoS elleni védelem és LIKE escape**: ReDoS-védelem a regex szűrőben (`regex` csomag 0.5s timeout / stdlib heurisztika) 200k karakteres korláttal, valamint az SQLite `LIKE` kifejezések speciális karaktereinek (`\`, `%`, `_`) biztonságos escape-elése.
- **Archaikus async kód és aiohttp eltávolítása**: A régi, 1. fázisból maradt `async_fetch_page` törlése a `fetcher.py`-ból és az aiohttp függőség teljes kivezetése a tesztek igazításával.

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
  - Dinamikus `allow_clearnet` szinkronizáció a felületről az `OnionFetcher`-be szálbiztos `set_allow_clearnet` metódussal és nyomon követéssel.
  - Szigorú `is_onion_host` domain ellenőrzés és URL feloldás (`urljoin`) a hamis `.onion` aldomainek (pl. `onion.example.com`) és relatív átirányítások biztonságos szűrésére.

### Javítva
- Exponenciális backoff várakozás és 5xx kódok újrapróbálásának visszaállítása az `async_fetch_page_httpx` ágban.
- `RobotsChecker.is_allowed` hívások áthelyezése `asyncio.to_thread`-re a nem blokkoló event loop működés érdekében.
- Duck-typing tartalék ág (`client.get`) törlése az `async_fetch_page_httpx`-ből a szigorú stream interfész javára.

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
