"""
Reality Score Management.

Steuert wie schnell die Wahrnehmung des Spielers driftet.

Werte:
- 1.0: stabile Realität, keine Korruption
- 0.7: erste subtile Drifts möglich
- 0.4: häufigere Drifts, NPC-Aussagen können widersprechen
- 0.1: Realität bröckelt aktiv, Akten ändern sich erkennbar
- 0.0: Reveal-Phase wird vorbereitet
"""
from __future__ import annotations

# Threshold ab dem Korruption überhaupt anfängt
DRIFT_THRESHOLD = 0.7

# Standard-Sink pro Session
DEFAULT_SESSION_DRIFT = 0.05

# Modifier für bestimmte Spieler-Aktionen
ACTION_DRIFTS = {
    "investigate_emotional_lead": 0.03,   # emotional belastend
    "interview_npc_long": 0.02,           # tiefe Befragung
    "discover_contradiction": -0.02,      # Spieler erkennt Drift -> Reality stabilisiert leicht
    "ignore_threat_notification": 0.04,   # Verdrängung
}


def corruption_intensity(reality_score: float) -> float:
    """
    Wie stark sollte Korruption bei diesem Score sein? 0..1.
    
    Linear unterhalb des Thresholds.
    """
    if reality_score >= DRIFT_THRESHOLD:
        return 0.0
    return (DRIFT_THRESHOLD - reality_score) / DRIFT_THRESHOLD


def apply_action_drift(current_score: float, action: str) -> float:
    """Berechnet neuen Score nach einer Spieler-Aktion."""
    delta = ACTION_DRIFTS.get(action, 0.0)
    new_score = max(0.0, min(1.0, current_score - delta))
    return new_score
