# Widerspruch — Konzept

## Pitch (ein Satz)

**Du untersuchst dein eigenes Verschwinden — in deinem echten Leben — und das System lügt dich von der ersten Sekunde an.**

---

## Was der Spieler erlebt

### Onboarding (15 Minuten)

Die App stellt scheinbar harmlose Fragen, verkauft als „damit das Spiel persönlich wird":

- Wo wohnst du (Stadt, grober Stadtteil)
- Wie sieht deine Morgenroutine aus
- Welche Menschen stehen dir nahe (Vornamen oder Pseudonyme reichen)
- Wovor hast du Angst
- Eine Erinnerung die du am liebsten löschen würdest
- Ein Ort den du regelmäßig besuchst
- Etwas was dich nervös macht

Die Daten werden im Profil verschlüsselt persistiert und füttern später den Personal Layer.

### Cooldown-Phase (5 Tage)

Nach Onboarding: nichts. Absichtliches Schweigen. Erzeugt Unsicherheit ob die App überhaupt was tut.

### First Strike

Notification um 21:47 Uhr (lokale Zeit, abendlich): „Polizei sucht Hinweise zu Vermisstem-Fall — bitte um Mithilfe der Bevölkerung."

Spieler öffnet die App. Die Akte beschreibt eine Person die verdächtig genau auf den Spieler passt: selber Stadtteil, selber Job, ähnliche Routine. Aber der Spieler ist offensichtlich da. Verwechslung? Doppelgänger? Identitätsdiebstahl? Spieler wird Investigator.

### Game Loop (mehrere Wochen)

Pro Session (5–20 Minuten):

- Akte lesen / aktuelle Spuren reviewen
- Zeugen befragen (LLM-NPCs mit Persistenz)
- Beweise sammeln und einsortieren
- Notizen anlegen
- Hypothesen aufstellen

Sessions können tagesweit auseinanderliegen. Zwischen Sessions schickt der Bot manchmal Real-Time-Threats (siehe unten).

---

## Mechaniken

### 1. Truth Engine

Jedes Faktum existiert in vier Schichten:

| Schicht | Wer es weiß | Beispiel |
|---|---|---|
| `truth` | Nur das System | Was tatsächlich passiert ist |
| `perceived` | Spieler + System | Was der Spieler wahrgenommen / gelesen hat |
| `claimed` | NPCs + System | Was Zeugen behaupten |
| `evidence` | Beweisstücke + System | Was Fotos / Logs / Dokumente zeigen |

Die Layer können widersprechen. Das ist Feature, nicht Bug. Drift-Mechanik nutzt Differenzen zwischen `perceived` und `truth` aus.

### 2. Hidden State (Reality)

- Versteckte Variable `reality_score` (0.0 – 1.0), startet bei 1.0
- Sinkt mit jeder Session leicht (~0.05), zusätzlich basierend auf bestimmten Aktionen
- Niedrigerer Wert → höhere Wahrscheinlichkeit dass `perceived` und `claimed` Layer modifiziert werden
- Modifikationen sind selten und subtil: einzelne Wörter, Zeitangaben um wenige Minuten, Detailbeschreibungen von Räumen

### 3. Real-Time Threat

- Async-Job-System (AWS EventBridge + Lambda) sendet zeitgenau Notifications
- Trigger: Zeit seit letzter Session, Story-Phase, Random
- Beispiele:
  - 3:14 morgens: anonyme SMS im Spiel mit Bild-Beschreibung
  - Sonntagvormittag: „Zeuge meldet sich nochmal — er möchte etwas korrigieren"
  - Nach langer Inaktivität: „Die Spur kühlt ab. Etwas ändert sich am Tatort."
- User kann Frequenz und Zeitfenster konfigurieren (Quiet Hours, Max-pro-Tag)

### 4. Personal Layer

- NPCs erhalten verfremdete Versionen der Onboarding-Personen
- Tatorte sind reale Locations in der Stadt des Spielers (basierend auf Onboarding)
- Routinen des Vermissten überlappen mit den eingegebenen Routinen
- **Konfigurierbar:** Personalisierungs-Intensität als Slider beim Onboarding (low / medium / high)

### 5. Doppel-Enthüllung

- Ab Session ~8: Spieler stolpert über eine zweite Zeitlinie — was *er selbst* in der Zeit getan hat während er „untersucht" hat
- Erste offensichtliche Lesart: Spieler ist der Täter
- Ab Session ~10: dritte Zeitlinie wird sichtbar, die der zweiten widerspricht
- Finale Erkenntnis: Es gab nie eine einzige Wahrheit. Das System hat von Anfang an Versionen gebaut die mit den Spieler-Inputs konsistent waren — nichts mehr.
- Endcredits-Trigger: Spieler entscheidet welche Version er als „seine" akzeptiert

---

## Was das Tool *nicht* ist

- Kein klassisches Whodunit mit fester Lösung
- Kein endloses Sandbox-Adventure
- Kein Multiplayer
- Keine generische LLM-Roleplay-Plattform
- Nicht für Spieler die schnelle Action wollen

## Was das Tool *ist*

- Ein einmaliges, intensives Story-Erlebnis über mehrere Wochen
- Eine Erfahrung die man eher *macht* als *spielt*
- Ein Projekt das saubere LLM-State-Architektur und Real-Time-Distributed-Systems demonstriert

---

## Risiken & Mitigationen

| Risiko | Mitigation |
|---|---|
| LLM kann keinen Horror | Iterative Prompt-Entwicklung mit Eval-Set, Pacing-Templates statt freier Generation |
| Zu nah an realer Person → unangenehm | Personalisierungs-Intensität als Slider, Quiet Hours, Crisis-Off-Switch |
| Notifications nervig | User-konfigurierbare Frequenz, max 2 pro Tag default |
| Hohe LLM-Kosten | Lambda + Batching, billigeres Modell für NPC-Witness, Opus nur für Pacing-kritische Momente |
| State-Inkonsistenz / Bugs | Truth Engine als zentrale Source-of-Truth mit Audit-Log; alle Schicht-Changes versioniert |
