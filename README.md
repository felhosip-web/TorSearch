# Onion Kereső

> Tor hálózaton működő, magas anonimitású `.onion` keresőmotor és webes feltáró (crawler) alkalmazás.

[![Licenc](https://img.shields.io/badge/Licenc-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-brightgreen.svg)](https://www.python.org/)
[![Tor](https://img.shields.io/badge/H%C3%A1l%C3%B3zat-Tor%20SOCKS5h-purple.svg)](https://www.torproject.org/)
[![Szerző](https://img.shields.io/badge/Szerz%C5%91-HES%20Projects%20by%20FePe-orange.svg)](#szerzői-információ)

Az **Onion Kereső** egy professzionális, asztali és webes felülettel is rendelkező szoftver, amely a Tor rejtett szolgáltatásainak (`.onion` v3 címek) biztonságos, anonim feltárására, indexelésére, kategorizálására és visszakeresésére szolgál. Különös hangsúlyt fektet a szigorú deanonymizáció elleni védelemre, az automatizált többforrásos maggyűjtésre és a helyi titkosított adattárolásra.

---

## Tartalomjegyzék

1. [Főbb funkciók](#-főbb-funkciók)
2. [Rendszerkövetelmények](#-rendszerkövetelmények)
3. [Telepítés lépésről lépésre](#-telepítés-lépésről-lépésre)
4. [Használat és indítás](#-használat-és-indítás)
5. [Seed források és prioritásos fallback rendszer](#-seed-források-és-prioritásos-fallback-rendszer)
6. [Biztonsági architektúra és adatvédelem](#-biztonsági-architektúra-és-adatvédelem)
7. [Licenc](#-licenc)
8. [Felelősségkizárás (Disclaimer)](#-felelősségkizárás-disclaimer)
9. [Szerzői információ](#-szerzői-információ)

---

## 🚀 Főbb funkciók

- **Szigorú Tor-only védelem**: Valamennyi külső hálózati kérés kizárólag a helyi Tor SOCKS5h proxyn (`socks5h://127.0.0.1:9050`) halad keresztül. Ha a clearnet mód le van tiltva, véletlenül sem szivároghat ki adat a nyílt internetre.
- **Intelligens 8-szintű Seed Kaszkád**: Automatikus kezdőcím (seed) gyűjtés több független forrásból (Tor66, Deep Search, Haystak, OnionLand stb.), automatikus továbblépéssel alacsony találatszám esetén.
- **Titkosított SQLite tárolás (Fernet + HMAC)**: A felderített oldalak, státuszkódok és halott címek determinisztikus HMAC-cal indexelt, Fernet szimmetrikus titkosítással ellátott SQLite adatbázisban tárolódnak.
- **Dual-Mode Hálózati Fetcher (Szinkron / Aszinkron)**: A meglévő szinkron (`requests` + szálak) működés az alapértelmezett. A Beállításokban opcióként bekapcsolható az aszinkron (`httpx` + `asyncio`) mód a magasabb párhuzamosságért és hatékonyságért.
- **Pánik törlés (Panic Shredder)**: Vészhelyzet esetén egyetlen billentyűkombinációval (`Ctrl+Shift+Delete`) az összes konfiguráció, indexelt adatbázis és magfájl biztonságosan felülíródik és megsemmisül.
- **Élő szűrés és tartalomkategorizálás**: Valós idejű gépelés közbeni szűrés kötelező és tiltott kulcsszavakra (*Must / Must Not Contain*), kategóriák (Market, Forum, Wiki, Library) és nyelvek szerint.
- **Halott linkek kiszűrése (Dead Blacklist)**: A nem elérhető vagy megszűnt szolgáltatások automatikusan feketelistára kerülnek az erőforrások kímélése érdekében.
- **Modern grafikus felület és webes dashboard**: Ergonomikus Tkinter GUI a napi használathoz és modern React + Tailwind webes vezérlőpult a konfiguráció szimulálásához és ellenőrzéséhez.

---

## 📋 Rendszerkövetelmények

- **Operációs rendszer**: Linux (Ubuntu, Debian, Fedora, Arch stb.), macOS vagy Windows 10/11
- **Python**: 3.9 vagy újabb verzió
- **Tor szolgáltatás**: Futó helyi Tor démon (`tor` csomag vagy Tor Browser)
  - Alapértelmezett SOCKS5h port: `9050` (rendszer démon) vagy `9150` (Tor Browser)
- **Opcionális (webes vezérlőpulthoz)**: Node.js 18+ és npm

---

## 📦 Telepítés lépésről lépésre

### 1. Tor szolgáltatás telepítése és elindítása

Linux rendszeren (Debian / Ubuntu):
```bash
sudo apt update
sudo apt install tor
sudo systemctl enable --now tor
```

Arch Linux rendszeren:
```bash
sudo pacman -S tor
sudo systemctl enable --now tor
```

Windows / macOS rendszeren:
Indítsd el a hivatalos [Tor Browser](https://www.torproject.org/) alkalmazást a háttérben (ez a `9150`-es porton biztosít proxykapcsolatot).

### 2. Forráskód letöltése

```bash
git clone https://github.com/hes-projects/tor-search.git
cd tor-search
```

### 3. Python virtuális környezet létrehozása és aktiválása

```bash
python3 -m venv .venv
source .venv/bin/activate
# Windows rendszeren: .venv\Scripts\activate
```

### 4. Függőségek telepítése

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

*(Amennyiben nincs külön requirements.txt:* `pip install requests[socks] beautifulsoup4 cryptography lxml httpx pytest`*)*

---

## 💻 Használat és indítás

### Asztali grafikus felület (GUI) indítása

A program legkényelmesebben a beépített grafikus felülettel használható:

```bash
python3 main.py
```
vagy közvetlenül a modulból:
```bash
python3 -m onion_search.main
```

### Gyorsbillentyűk és kezelőszervek:
- **🌱 Magok (Tor66, DeepSearch...)**: Azonnali többforrásos seed frissítés indítása a háttérben.
- **⚙️ (Jobb klikk a Magok gombra)**: Maglista Kezelő dialógus megnyitása (források ki-/bekapcsolása, frissítési időköz állítása, cache statisztika).
- **⚙️ Beállítások (`Ctrl+,`)**: Hálózat, Crawler (Szinkron / Aszinkron kísérleti mód), Titkosítás és Szűrők beállítása.
- **ℹ️ Licenc / Névjegy**: Licencinformációk és szerzői attribúció megtekintése.
- **🚨 Pánik törlés (`Ctrl+Shift+Delete`)**: Azonnali helyi adatbázis- és állapotmegsemmisítés.

> **Megjegyzés az Aszinkron Módhoz (kísérleti):**
> A Beállítások -> *Crawler / Teljesítmény* fülön bekapcsolható az „Aszinkron hálózati mód (kísérleti)” (`async_mode: true`). Ez az `httpx` és `asyncio` könyvtárakat használja a hálózati kérések magasabb szintű párhuzamosításához. Amennyiben az aszinkron környezetben hiba lépne fel vagy hiányozna egy függőség, a rendszer automatikusan visszaesik a stabil szinkron módra.

### Tesztek futtatása

A teljes tesztcsomag automatizáltan futtatható `pytest`-tel:

```bash
pytest
```
Fej nélküli (headless) Linux környezetben virtuális kijelzővel:
```bash
xvfb-run -a pytest
```

---

## 🧅 Seed Plugin / Adapter Architektúra és Fallback Rendszer

A maggyűjtő rendszer moduláris **Plugin / Adapter architektúrára** épül, nagy hangsúlyt fektetve a bővíthetőségre és robusztusságra.

Minden seed forrás egy önálló, független plugin, amely a `BaseSeedPlugin` absztrakt bázisosztályból származik.

| Prioritás | Plugin azonosító | Plugin neve | Típus | Végpont jellege |
|:---:|:---|:---|:---|:---|
| **10** | `tor66` | **Tor66** | Friss rejtett könyvtár | `.onion` szolgáltatás + clearnet tükör |
| **20** | `deepsearch` | **Deep Search** | Katalógus & Kereső | `.onion` katalógus + clearnet tükör |
| **30** | `haystak` | **Haystak** | Nagy lefedettségű kereső | `.onion` végpont + clearnet tükör |
| **40** | `onionland` | **OnionLand** | Keresőmotoros index | `.onion` végpont + clearnet tükör |
| **50** | `github` | **Curated GitHub** | Kézileg ellenőrzött listák | Alec Muffett & Dan McInerney gyűjtemények |
| **60** | `ose` | **OnionSearchEngine** | Metakereső aggregáció | Keresőmotoros API / web scraping |
| **70** | `torch` | **Torch** | Veterán mélywebes index | `.onion` végpont + clearnet tükör |
| **80** | `notevil` | **not Evil** | *Utolsó mentsvár fallback* | `.onion` vészhelyzeti tartalék kereső |
| **90** | `ahmia` | **Ahmia.fi** | Globális indexelő | `.onion` + clearnet index |
| **100** | `custom_regex` | **Custom Regex** | Egyéni URL + Regex/CSS | Tetszőleges felhasználói forrás |

### 🟢 Egészségügyi Ellenőrzés (Health-Check & Caching):
- Minden plugin saját gyors, kis erőforrás-igényű `health_check()` metódussal rendelkezik (gyors HEAD/GET választeszt).
- A health állapot automatikusan gyorsítótárazódik (`health_check_cache_ttl` pl. 10 percig), hogy elkerüljük a források túlterhelését.
- A GUI-ban minden forrás mellett vizuális állapotjelző látható:
  - 🟢 **Zöld**: Elérhető, egészséges forrás
  - 🟡 **Sárga**: Még nem ellenőrzött / határeset
  - 🔴 **Piros**: Elérhetetlen / hálózati hiba
- Opció: *"Csak az egészséges (🟢 OK) forrásokat használd"* mód a garantáltan működő források használatához.

### 🧩 Új Seed Forrás Írása (Fejlesztői Útmutató):
Új seed forrás hozzáadása mindössze egy új fájl létrehozásával jár az `onion_search/seeds/plugins/` mappában! A `PluginRegistry` automatikusan felfedezi és betölti az új modult:

```python
# onion_search/seeds/plugins/my_custom_source.py
from typing import Optional, Set
from onion_search.seeds.base import BaseSeedPlugin, extract_onion_urls_from_text

class MyCustomSeedPlugin(BaseSeedPlugin):
    id = "my_source"
    name = "Saját Kereső Plugin"
    priority = 25  # Kaszkád sorrend prioritása (kisebb = előbb fut)
    enabled = True

    def _do_fetch_seeds(
        self, query: Optional[str] = None, proxy_url: Optional[str] = None, allow_clearnet: bool = False, timeout: int = 15
    ) -> Set[str]:
        url = "http://mycustomoniondirectory.onion/list"
        resp = self._make_request(url, proxy_url=proxy_url, allow_clearnet=allow_clearnet, timeout=timeout)
        if resp and resp.status_code == 200:
            return extract_onion_urls_from_text(resp.text)
        return set()
```

---

## 💾 Absztrakt Tároló Architektúra (Storage Layer)

A tárolási réteg absztrakt, cserélhető architektúrára épül (`BaseStorage`), így a szoftver felkészült a skálázódásra több millió `.onion` cím kezelése esetén is.

### Támogatott Tároló Backendek:
- **`sqlite` (Alapértelmezett)**: Titkosított SQLite backend (Fernet + HMAC), PRAGMA WAL móddal, 5 mp-es busy timeout-tal, másodlagos indexekkel és batch műveletekkel (`executemany`).
- **`json`**: Egyszerű JSON alapú fájltároló (kisebb tesztadatkészletekhez).
- **`postgres` / `postgresql`**: Nagyléptékű vállalati skálázódáshoz előkészített PostgreSQL váz.

### 🔌 Új Storage Backend Írása (Fejlesztői Útmutató):
Egyedi tároló backend írásához származz a `BaseStorage` osztályból és regisztráld a `StorageFactory`-nál:

```python
from onion_search.storage import BaseStorage, StorageFactory

class CustomSearchIndexStorage(BaseStorage):
    def add_result(self, result: dict) -> bool:
        ...

    def add_results_batch(self, results: list) -> bool:
        ...

    def get_results(self, query=None, lang=None, category=None, limit=100, offset=0):
        ...

    def mark_dead(self, url: str, ts=None) -> None:
        ...

    def is_dead(self, url: str) -> bool:
        ...

    def get_stats(self) -> dict:
        return {"backend": "custom_search"}

    def cleanup_dead(self, cutoff_hours: float = 24.0) -> int:
        ...

# Regisztráció a StorageFactory-nál
StorageFactory.register("custom", CustomSearchIndexStorage)
```

---

## 🛡️ Biztonsági architektúra és adatvédelem

- **Kiszivárgás-megelőzés**: Ha a felhasználó nem engedélyezi kifejezetten a clearnet tükröket, a szoftver azonnal megtagad minden olyan kérést, amely nem `.onion` címre irányul vagy nincs aktív Tor proxy mögött.
- **HMAC determinisztikus keresés**: A titkosított adatbázisban a keresési teljesítmény megőrzése érdekében az URL-ek egy titkos HMAC kulccsal ellátott prefixszel rendelkeznek, így a relációs adatbázis indexelhető marad a nyers címek kiszivárgása nélkül.
- **Időzített mentés és memóriatisztítás**: A memóriában tartott címkészletek deduplikáltak, a fájlba írás atomi módon történik.

---

## 📄 Licenc

Ez a projekt az **Apache License 2.0** feltételei szerint került közzétételre.

A licenc teljes szövege a gyökérkönyvtárban található [LICENSE](LICENSE) fájlban olvasható.  
A hivatalos termék- és szerzői attribúció a [NOTICE](NOTICE) fájlban található.

```text
Copyright 2026 HES Projects by FePe

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

## ⚠️ Felelősségkizárás (Disclaimer)

Ez a szoftver **kizárólag oktatási, kiberbiztonsági kutatási és jogszerű tájékozódási célokra** készült.

- A fejlesztő nem vállal semmilyen felelősséget a szoftver helytelen, rosszindulatú vagy jogellenes használatáért.
- A szoftver futtatásával és a Tor hálózaton fellelhető oldalak meglátogatásával a felhasználó kizárólagosan felelős a saját cselekedeteiért és a helyi jogszabályok betartásáért.
- A szoftver nem tárol, nem hosztol és nem népszerűsít illegális tartalmakat; kizárólag a Tor protokollon keresztül nyilvánosan közzétett címek indexelését végzi el kliensoldalon.

---

## 👤 Szerzői információ

- **Szerző / Fejlesztő**: **HES Projects by FePe**
- **Kapcsolat & Projekt**: Nyílt forráskódú fejlesztés
- **Kiadás**: Onion Kereső (v5.0.0)
