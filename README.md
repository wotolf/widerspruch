# Widerspruch

> A horror investigation engine where you investigate your own disappearance — in your real life — and the system lies to you from second one.

Ein AI-gesteuertes Solo-Horror-Adventure mit Hidden State, Personal Layer, Real-Time-Threat und einer Truth Engine die mehrere Wahrheiten parallel trackt.

**Status:** 🚧 In Entwicklung — Phase 1 (Skeleton)

---

## Konzept (Kurzfassung)

Du wirst Investigator deines eigenen Vermissten-Falls. Die Personenbeschreibung in der Akte passt verdächtig genau auf dich — selber Stadtteil, selber Job, selbe Routine. Über Wochen baust du den Fall auf, befragst NPCs, sammelst Beweise. Die App lügt dich subtil an. Eine versteckte "Reality"-Variable destabilisiert deine Wahrnehmung. Real-Time-Notifications dringen aus dem Spiel in deinen Alltag. Am Ende stehen mehrere mögliche Wahrheiten — und du kannst nie sicher sein welche deine ist.

Vollständiges Konzept: [`docs/concept.md`](docs/concept.md)

---

## Tech Stack

- **Backend:** Python 3.11+, discord.py, SQLAlchemy, Anthropic SDK
- **DB:** PostgreSQL 16 mit pgvector (für Story-Memory)
- **Cloud:** AWS (Lambda, EventBridge, RDS, S3) via Terraform
- **Frontend (Phase 3+):** Next.js Web-Dashboard für die Akte

---

## Projektstruktur

```
widerspruch/
├── backend/
│   ├── bot/             # Discord-Bot Entry Point + Commands
│   ├── core/            # Truth Engine, LLM, Case Generator
│   ├── db/              # SQLAlchemy Models, Schema
│   └── prompts/         # LLM-Prompts (versioniert als Markdown)
├── infra/terraform/     # AWS-Infrastruktur als Code
├── docs/                # Konzept, Roadmap, Architektur
├── tests/               # Pytest-Tests
└── scripts/             # Setup, Seeding, Migrations
```

---

## Quickstart (Lokal)

### Voraussetzungen

- Python 3.11+
- Docker & Docker Compose
- Git
- Ein Discord-Bot-Token ([Setup-Anleitung](docs/setup.md))
- Ein Anthropic API Key

### Setup

```bash
# Repo clonen
git clone <dein-repo-url> widerspruch
cd widerspruch

# Python venv anlegen
python3 -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# Dependencies installieren
pip install -r requirements.txt

# Env-Datei vorbereiten
cp .env.example .env
# Trag in .env deinen DISCORD_TOKEN und ANTHROPIC_API_KEY ein

# Postgres lokal starten
docker compose up -d

# Schema initialisieren
psql postgresql://widerspruch:dev@localhost:5432/widerspruch -f backend/db/schema.sql

# Bot starten
python -m backend.bot.main
```

---

## Roadmap

Siehe [`docs/roadmap.md`](docs/roadmap.md) für die volle Phasen-Aufteilung.

- **Phase 1 (Wochen 1–2):** Skeleton — Onboarding, basisches Case-Setup, Discord-Commands, kein Hidden State
- **Phase 2 (Wochen 3–4):** Truth Engine — Vier-Schichten-Datenmodell, erste Drift-Mechanik
- **Phase 3 (Wochen 5–6):** Real-Time Threat — AWS-Scheduler, Push-Notifications, Web-Dashboard
- **Phase 4 (Wochen 7–8):** Reveal-Mechaniken — parallele Zeitlinie, Doppel-Enthüllung
- **Phase 5 (Wochen 9+):** Replayability — Generator für neue Setups

---

## Lizenz

TBD — entscheide dich vor dem ersten Public-Push.
