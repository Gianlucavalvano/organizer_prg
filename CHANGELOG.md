# Changelog

## 2026-04-08 - backend refactor a domini + fix stampa progetto

### Added
- Nuova struttura backend per domini in `backend/domains/`:
  - `auth`
  - `admin_moduli`
  - `progetti_task`
  - `utenti`
  - `ore_progetto`
  - `organizer_ict`
- Nuovo entrypoint `backend/app.py`.

### Changed
- `backend/main.py` semplificato:
  - bootstrap app
  - registrazione router dominio
  - endpoint infrastrutturali (`/health`, `/health/db`, `/apps/me`)
- Logica API spostata da `main.py` ai router/service di dominio.
- `backend/auth.py` mantenuto come facade compatibile verso il nuovo dominio `auth`.

### Fixed
- Risolto bug stampa PDF dettaglio progetto su PostgreSQL in `src/organizer_ict/services/gestore_report.py`:
  - rimosso uso non compatibile di `id_parent IS ?`
  - separati i casi corretti:
    - `id_parent IS NULL`
    - `id_parent = ?`

### Validation
- Smoke test rapido API completato con esito positivo su endpoint core e domini principali.
