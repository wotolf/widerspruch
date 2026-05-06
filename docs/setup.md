# Setup-Anleitung

Detaillierte Schritte um alle externen Accounts und Tokens einzurichten.

---

## 1. Discord-Bot anlegen

1. Geh zu [Discord Developer Portal](https://discord.com/developers/applications)
2. „New Application" → Name: `Widerspruch` (oder dein gewählter Name)
3. Reiter „Bot" → „Add Bot" → bestätigen
4. Unter „Privileged Gateway Intents" aktivieren:
   - `MESSAGE CONTENT INTENT` (für Antworten lesen)
   - `SERVER MEMBERS INTENT` (optional, für DMs braucht's das nicht zwingend)
5. Bot-Token kopieren (Reset-Token-Knopf falls's verloren ging) → in `.env` als `DISCORD_TOKEN`
6. Reiter „OAuth2" → „URL Generator":
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Use Slash Commands`, `Read Message History`
7. Generierte URL öffnen → eigenen Test-Server auswählen → Bot einladen

**Test-Server anlegen:** Falls du keinen privaten Discord-Server hast, in Discord links auf „+" → eigenen Server erstellen. Den nutzt du nur zum Testen.

---

## 2. Anthropic API Key

1. [console.anthropic.com](https://console.anthropic.com)
2. Account anlegen, ggf. Kreditkarte hinterlegen (für API-Nutzung)
3. „API Keys" → „Create Key"
4. Key kopieren → in `.env` als `ANTHROPIC_API_KEY`
5. Setze ein **Spending Limit** in den Account-Settings (z.B. 20€/Monat) bevor du mit Iteration startest

**Tipp:** In Phase 1 nutzt du fast ausschließlich Sonnet oder Haiku für Tests, die sind günstig. Opus erst wenn du Pacing-kritische Prompts iterierst.

---

## 3. Lokales Postgres

Das machst du mit Docker, kein Account nötig:

```bash
# Voraussetzung: Docker Desktop installiert
docker compose up -d

# Verbindung testen
docker exec -it widerspruch-postgres psql -U widerspruch -d widerspruch -c "SELECT 1;"
```

---

## 4. AWS Account (erst Phase 3 nötig)

**Wichtig:** Nutze NICHT den Job-AWS-Account. Privater Account, separate Credentials.

1. [aws.amazon.com](https://aws.amazon.com) → „Create AWS Account"
2. Kreditkarte hinterlegen (Free Tier deckt Phase 3–4 fast komplett ab)
3. Im IAM einen User mit Programmatic Access anlegen — **nicht den Root-User benutzen**
4. Permissions: erstmal `AdministratorAccess` für Dev (später feiner restriktieren)
5. Access Key + Secret in `.env`
6. **Billing Alarm anlegen:** AWS Console → Billing → Budgets → 10€/Monat Alarm

---

## 5. GitHub Repo

```bash
cd widerspruch
git init
git add .
git commit -m "Initial skeleton"

# Repo auf github.com erstellen, dann:
git remote add origin git@github.com:dein-name/widerspruch.git
git branch -M main
git push -u origin main
```

**Repo public oder private?** Erstmal **private**. Public erst wenn du fertig bist und veröffentlichen willst — sonst kommen Leute auf Spoiler.
