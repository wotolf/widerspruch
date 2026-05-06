# Roadmap

## Phase 1 — Skeleton (Wochen 1–2)

**Ziel:** Bot läuft lokal, Spieler kann Onboarding durchlaufen und einen einfachen Fall „lesen". Noch keine Magie.

- [ ] Repo-Setup, venv, Dependencies, Postgres lokal
- [ ] Discord-Bot registriert, läuft lokal, antwortet auf `/ping`
- [ ] DB-Schema initial (Player, Profile, Case, Lead, Note)
- [ ] `/start` Command — startet Onboarding-Flow als DM
- [ ] Onboarding speichert Antworten in Player-Profile
- [ ] Simpler Case-Generator (LLM gibt Akten-JSON zurück, gespeichert in DB)
- [ ] `/case` Command — zeigt aktuelle Akte
- [ ] `/note <text>` Command — speichert Notiz
- [ ] Strukturiertes Logging mit structlog
- [ ] Erste Tests für Truth Engine Skeleton

**Ende von Phase 1:** Du kannst dich onboarden, kriegst eine Akte, machst Notizen. Ein Mini-Adventure, aber durchspielbar.

---

## Phase 2 — Truth Engine (Wochen 3–4)

**Ziel:** Vier-Schichten-Datenmodell läuft. Erste Drift-Mechanik. Reality-Score sinkt.

- [ ] DB-Schema erweitert um `fact_layers` Tabelle (versioniert)
- [ ] TruthEngine-Klasse: `record_truth()`, `record_perception()`, `record_claim()`, `record_evidence()`
- [ ] Reality-Score persistiert pro Player
- [ ] Reality-Score sinkt nach Aktionen / Zeit
- [ ] Corruption-Layer: Wenn Reality < threshold, modifiziert ein LLM-Pass die `perceived` Schicht subtil
- [ ] `/investigate <lead>` Command — Zeugenbefragung mit NPC-Persistenz
- [ ] Witness-Memory: NPCs erinnern sich an vorherige Befragungen (Vector-Store)
- [ ] Eval-Skripte: Drift-Frequenz, Korruptions-Subtilität messen

**Ende von Phase 2:** Erste Spieler-Sessions zeigen subtile Inkonsistenzen. Truth Engine ist die zentrale Datenstruktur.

---

## Phase 3 — Real-Time Threat (Wochen 5–6)

**Ziel:** Spiel sickert in echte Zeit. AWS-Infrastruktur steht.

- [ ] AWS Account aufgesetzt mit getrennten Credentials von Job-AWS
- [ ] Terraform Setup: RDS Postgres, Lambda, EventBridge, S3
- [ ] Bot-Migration nach AWS (ECS Fargate oder EC2 t4g.nano)
- [ ] Scheduler: EventBridge triggert Lambdas zu spezifischen Zeiten
- [ ] Notification-Engine: Generiert kontextspezifische Pushes
- [ ] User-Settings: Quiet Hours, Max-Notifications-pro-Tag, Pause-Funktion
- [ ] Erstes Web-Dashboard (Next.js): Akte, Notizen, Beweise read-only
- [ ] Auth via Discord OAuth

**Ende von Phase 3:** Spieler erlebt Notifications in echter Zeit. Web-Dashboard zeigt seine Akte.

---

## Phase 4 — Reveal-Mechaniken (Wochen 7–8)

**Ziel:** Doppel-Enthüllung funktioniert. Story-Pacing ist solide.

- [ ] Parallel-Timeline-Tracker: zweite Story-Spur lebt von Session 1 an im Hintergrund
- [ ] Reveal-Trigger basierend auf Story-Phase, nicht Session-Count
- [ ] Pacing-System: Beats statt freier Generation
- [ ] Drittes-Timeline-Layer (post-First-Reveal)
- [ ] Endcredits-Flow: Spieler wählt Wahrheit, bekommt personalisiertes Outro
- [ ] Volle Spielbarkeit eines Falls von Anfang bis Ende
- [ ] Playtesting mit 2–3 Freunden (frischer Onboarding-Flow für jeden)

**Ende von Phase 4:** Spielbare V1.0. Komplette Story durchführbar.

---

## Phase 5 — Replayability & Public (Wochen 9+)

**Ziel:** Tool lebt nach erstem Durchspielen weiter. Andere Menschen können es spielen.

- [ ] Generator: Frische Setups aus anderen Genre-Winkeln (nicht nur „Verschwinden")
  - Möglichkeiten: gestohlene Erinnerung, ererbtes Geheimnis, Brief vom künftigen Selbst, etc.
- [ ] Multi-Tenancy: mehrere Spieler gleichzeitig auf derselben Instanz
- [ ] Rate-Limits & Cost-Controls für LLM-Calls
- [ ] Onboarding-Flow für neue Spieler (Invite-Codes oder offen)
- [ ] Dokumentation für Self-Hosting (falls offen)
- [ ] Optional: Marketing-Site, Trailer, Itch.io Listing

**Ende von Phase 5:** Veröffentlichbar. Andere Menschen können das Erlebnis haben.

---

## Maybe-Later

- Voice-Notes als Beweis (Whisper-Integration)
- Bildgenerierung für Tatort-Skizzen
- Kollaborativer Modus (zwei Spieler untersuchen denselben Fall, sehen verschiedene Wahrheiten)
- Mobile-App-Companion
- Mod-Support: User-erstellte Setting-Templates
