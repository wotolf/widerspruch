# Timeline Seeding Prompt

Du generierst drei parallele Ereignis-Timelines für einen Vermissten-Fall. Jede Timeline zeigt dieselben Zeitfenster aus einer anderen Perspektive.

## Timelines

- **investigator**: Was der Ermittler (= Spieler) beobachtet oder erschließt — lückenhafte, subjektiv gefärbte Sicht
- **shadow_a**: Eine zweite unbekannte Partei die denselben Zeitraum erlebt — könnte Täter, Zeuge oder Unbeteiligter sein
- **shadow_b**: Eine dritte Partei mit weiterer abweichender Wahrnehmung — Details widersprechen gelegentlich den anderen Timelines

## Input

```json
{
  "case_title": "...",
  "disappearance_date": "YYYY-MM-DD",
  "city": "...",
  "missing_person_brief": "...",
  "investigator_profile": "..."
}
```

## Aufgabe

Generiere für jede Timeline **8–12 Events**. Jedes Event hat:

- `wall_clock_slot`: Gemeinsamer Zeitschlüssel als "DayN-HH:MM", z.B. "Day1-20:00". **Muss identisch** in allen drei Timelines sein — alle drei Timelines müssen exakt dieselbe Liste von wall_clock_slots abdecken.
- `occurred_at`: ISO-8601-Timestamp mit Zeitzone, passend zum wall_clock_slot und zum Verschwinden-Datum
- `description`: Was in diesem Zeitfenster aus dieser Perspektive passiert. Mindestens 20 Zeichen. Nüchtern-sachlicher Stil, deutsch, gelegentlich vage oder widersprüchlich zu den anderen Timelines.

## Regeln

- Exakt dieselben `wall_clock_slot`-Werte in allen drei Timelines (gleiche Reihenfolge)
- Keine identischen `wall_clock_slot`-Werte innerhalb einer Timeline
- Beschreibungen sind perspektivisch — was eine Timeline als Fakt schildert, ist in einer anderen nur Gerücht
- Mindestens ein Widerspruch zwischen shadow_a und shadow_b zu einem Event
- Kein happy ending, keine Auflösung — Lücken und Widersprüche bleiben offen
- Keine explizite Gewalt

## Output

Valides JSON mit drei Arrays, keine Markdown-Fences:

```json
{
  "investigator": [
    {"wall_clock_slot": "Day1-20:00", "occurred_at": "...", "description": "..."},
    ...
  ],
  "shadow_a": [
    {"wall_clock_slot": "Day1-20:00", "occurred_at": "...", "description": "..."},
    ...
  ],
  "shadow_b": [
    {"wall_clock_slot": "Day1-20:00", "occurred_at": "...", "description": "..."},
    ...
  ]
}
```

Nur JSON, keine Erklärung davor oder danach.
