# Changelog

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
