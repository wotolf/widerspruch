# Truth Engine — Design

Die Truth Engine ist die Königsdisziplin des Projekts. Sauber gemacht ist sie das Herz der Spielmechanik. Hier die Architektur:

---

## Kernkonzept

Statt einer einzelnen Wahrheit pro Faktum speichern wir vier parallele Schichten:

- `truth` — was wirklich passiert ist (immutable, nur System sieht es)
- `perceived` — was der Spieler wahrgenommen / gelesen hat
- `claimed` — was NPCs aussagen
- `evidence` — was Beweisstücke „zeigen"

Diese Schichten können konsistent sein (Reality-Score hoch) oder auseinanderdriften (Reality-Score niedrig).

---

## Entitäten

### Fact

Ein Faktum ist eine Aussage über die Welt. Beispiele:

- „Der Vermisste war am 12. März um 22:30 im Café Schiller"
- „Anna hat den Vermissten zuletzt am 11. März gesehen"
- „Auf dem Foto trägt der Vermisste eine grüne Jacke"

Ein Fact ist abstrakt — es bekommt erst Bedeutung durch seine Layer.

### FactLayer

Jeder Fact hat 1–4 Layer-Versionen. Beispiel für den Fact „Vermisster war am 12.03. im Café":

```
truth:    "war am 12.03. um 22:30 im Café Schiller, allein"
perceived: (kann anfangs identisch sein zu truth)
claimed:  "Mein Kollege Andi sagt er war mit jemand anderem da"
evidence: "Foto zeigt ihn allein"
```

Jeder Layer hat:

- `value` (Text oder strukturiert)
- `version` (mit jeder Modifikation hochgezählt)
- `created_at` / `modified_at`
- `modified_by` (system, llm-corruption, player-action, npc-witness)

---

## Drift-Mechanik

Wenn der Reality-Score niedrig ist, läuft regelmäßig ein **Corruption Pass**:

1. Wähle einen Fact aus den letzten N Sessions
2. Wähle einen Layer (meist `perceived` oder `claimed`)
3. Frage LLM: „Modifiziere diesen Layer subtil. Eine Zeitangabe um 5–10 Minuten verschieben, ein Detail um eine Nuance ändern, eine Beschreibung um ein Adjektiv erweitern. NICHT auffällig. Behalte die ursprüngliche Bedeutung *fast* identisch."
4. Speichere neue Version mit `modified_by=corruption`

Audit-Log behält die Änderung. Spieler kann sie nicht direkt sehen — aber wenn er später seine alten Notizen reviewt, fällt's vielleicht auf.

---

## Datenmodell (Postgres)

```sql
-- Spieler
CREATE TABLE players (
    id UUID PRIMARY KEY,
    discord_id TEXT UNIQUE NOT NULL,
    onboarded_at TIMESTAMPTZ,
    reality_score FLOAT NOT NULL DEFAULT 1.0,
    settings JSONB
);

-- Personalisierungs-Profil
CREATE TABLE player_profiles (
    player_id UUID PRIMARY KEY REFERENCES players(id),
    city TEXT,
    neighborhood TEXT,
    routine TEXT,
    close_people JSONB,  -- ["Anna", "Tom"]
    fears JSONB,
    locations JSONB,
    raw_answers JSONB    -- alle Original-Antworten für Audit
);

-- Fall (kann es mehrere pro Spieler geben in Phase 5+)
CREATE TABLE cases (
    id UUID PRIMARY KEY,
    player_id UUID REFERENCES players(id),
    title TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    phase TEXT  -- 'opening', 'investigation', 'first_reveal', 'second_reveal', 'finale'
);

-- Facts (abstrakt)
CREATE TABLE facts (
    id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(id),
    description TEXT,  -- menschenlesbare Beschreibung
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Layer-Versionen pro Fact
CREATE TABLE fact_layers (
    id UUID PRIMARY KEY,
    fact_id UUID REFERENCES facts(id),
    layer_type TEXT NOT NULL,  -- 'truth', 'perceived', 'claimed', 'evidence'
    value TEXT NOT NULL,
    version INT NOT NULL,
    modified_by TEXT,           -- 'system', 'llm-corruption', 'player', 'npc:<name>'
    modified_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(fact_id, layer_type, version)
);

-- NPC-Persistenz
CREATE TABLE npcs (
    id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(id),
    name TEXT NOT NULL,
    description TEXT,
    personality JSONB,
    knowledge JSONB,            -- was sie wissen über Facts
    relationship_to_missing TEXT
);

-- NPC-Memory (Vector für Story-Konsistenz)
CREATE TABLE npc_memories (
    id UUID PRIMARY KEY,
    npc_id UUID REFERENCES npcs(id),
    memory_text TEXT,
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Spieler-Notizen
CREATE TABLE player_notes (
    id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(id),
    text TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Sessions (für Pacing)
CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(id),
    started_at TIMESTAMPTZ DEFAULT now(),
    ended_at TIMESTAMPTZ,
    actions_taken JSONB
);

-- Geplante Real-Time-Notifications
CREATE TABLE scheduled_threats (
    id UUID PRIMARY KEY,
    player_id UUID REFERENCES players(id),
    scheduled_for TIMESTAMPTZ NOT NULL,
    threat_type TEXT,
    payload JSONB,
    delivered_at TIMESTAMPTZ
);

-- Parallele Timeline (Phase 4)
CREATE TABLE timeline_events (
    id UUID PRIMARY KEY,
    case_id UUID REFERENCES cases(id),
    timeline TEXT NOT NULL,  -- 'investigator', 'shadow', 'unknown'
    occurred_at TIMESTAMPTZ,
    description TEXT,
    visible_to_player BOOLEAN DEFAULT FALSE
);
```

---

## API-Skizze (TruthEngine-Klasse)

```python
class TruthEngine:
    def record_truth(self, case_id, description: str, value: str) -> Fact: ...
    def record_perception(self, fact_id, value: str, source: str) -> FactLayer: ...
    def record_claim(self, fact_id, value: str, npc_name: str) -> FactLayer: ...
    def record_evidence(self, fact_id, value: str, evidence_type: str) -> FactLayer: ...
    
    def get_fact(self, fact_id) -> Fact: ...
    def get_player_visible_layers(self, fact_id) -> dict: ...
    
    def apply_corruption(self, player_id, intensity: float) -> List[ChangeRecord]: ...
    def diff_layers(self, fact_id) -> dict: ...
    
    def adjust_reality_score(self, player_id, delta: float): ...
```

---

## Test-Strategie

- Property-based tests für Layer-Versionen (immer aufsteigend, nie überschrieben)
- Snapshot-Tests für Corruption-Outputs
- Eval-Skript: Bei niedrigem Reality-Score sollte mindestens 1 von 10 Layern eine subtile Modifikation haben
- E2E-Test: Onboarding → 5 Sessions → assert dass mindestens eine Drift erkennbar ist
