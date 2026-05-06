# Case Generation Prompt

Du generierst eine Vermissten-Akte für ein Investigativ-Adventure. Der Spieler hat sein Profil im Onboarding angegeben — der Vermisste sollte verdächtig genau auf den Spieler passen, ohne identisch zu sein.

## Input

```json
{
  "city": "...",
  "neighborhood": "...",
  "routine": "...",
  "close_people": [...],
  "fears": [...],
  "locations": [...],
  "personalization_intensity": "low|medium|high"
}
```

## Aufgabe

Generiere als JSON:

- `title`: Akten-Titel, sachlich
- `missing_person`: Beschreibung des Vermissten (Alter, grobes Aussehen, Beruf, Routine — sollte 70-85% mit dem Spieler-Profil überlappen)
- `disappearance_circumstances`: Was passierte, knapp, mit Lücken
- `initial_leads`: 3-5 Spuren, jede mit `id`, `headline`, `details`
- `npcs`: 3-7 Personen, jede mit `name`, `relationship`, `personality_brief`
- `locations`: 2-3 Orte (Stadtteil = Spieler-Stadtteil)
- `timeline`: chronologische Liste der bekannten Ereignisse

## Regeln

- Halte Lücken offen — nicht alles auflösen
- Mindestens ein NPC sollte Detail-Aussagen machen die später widersprüchlich werden können
- Keine Auflösung im JSON — die wahren Ereignisse trackt das System separat
- Sprache der Akte: nüchtern-bürokratisch, deutsch, gelegentlich Behördenfloskeln
- Keine expliziten Gewalt-Beschreibungen, eher Andeutungen

## Output

Nur valides JSON, keine Markdown-Code-Fences, keine Erklärung davor oder danach.
