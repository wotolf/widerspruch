"""
Widerspruch Discord Bot — Entry Point.

Startet den Bot und registriert die Slash-Commands.
"""
import asyncio
import difflib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

import structlog

from backend.config import settings
from backend.core.case_generator import CaseGenerationError, CaseGenerator
from backend.core.case_lifecycle import (
    VALID_PHASES,
    apply_transition,
    evaluate_transition,
    phase_transition_message,
)
from backend.core.llm import LLMClient
from backend.core.reality import DRIFT_THRESHOLD, corruption_intensity
from backend.core.timeline_scorer import TimelineScorer
from backend.core.timeline_seeder import TimelineSeeder, TimelineSeederError
from backend.core.truth_engine import TruthEngine
from backend.db import get_session, init_db
from backend.db.models import Case, CasePhaseHistory, Fact, FactLayer, NPC, Player, PlayerNote, PlayerProfile

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"

_ONBOARDING_TIMEOUT = 300  # Sekunden bis Abbruch (5 Minuten)

_ONBOARDING_QUESTIONS: list[tuple[str, str]] = [
    ("city_input",   "In welcher Stadt wohnst du? (Stadt + grobes Viertel)"),
    ("routine",      "Wie sieht dein typischer Morgen aus? (3-4 Sätze)"),
    ("close_people", "Drei Menschen die dir nahe stehen. Pseudonyme oder Vornamen."),
    ("location",     "Ein Ort den du regelmäßig besuchst (kein Zuhause, keine Arbeit)."),
    ("fear",         "Etwas, das dich nervös macht — kein Trauma, etwas Alltägliches."),
    ("memory",       "Eine Erinnerung, die du am liebsten löschen würdest. Eine Zeile reicht."),
    ("intensity",    "Wie intensiv soll das Spiel an dein echtes Leben andocken? (wenig / mittel / stark)"),
]

_PHASE_LABELS: dict[str, str] = {
    "opening": "Eröffnung",
    "investigation": "Ermittlung",
    "first_reveal": "Erste Enthüllung",
    "second_reveal": "Zweite Enthüllung",
    "finale": "Finale",
    "closed": "Abgeschlossen",
}

# Logging-Setup
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, settings.log_level.upper(), logging.INFO)
    ),
)
log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Onboarding-Helfer
# ---------------------------------------------------------------------------

def _dm_check(user_id: int, channel_id: int):
    """Gibt eine check-Funktion für bot.wait_for('message') zurück."""
    def check(m: discord.Message) -> bool:
        return m.author.id == user_id and m.channel.id == channel_id
    return check


def _parse_city(answer: str) -> tuple[str, str | None]:
    """'Berlin, Mitte' oder 'Berlin (Prenzlauer Berg)' → (city, neighborhood)."""
    parts = re.split(r"[,/]|\s*\(", answer.strip(), maxsplit=1)
    city = parts[0].strip()
    neighborhood = parts[1].strip().rstrip(")").strip() if len(parts) > 1 else None
    return city, neighborhood or None


def _parse_intensity(answer: str) -> str:
    """Normalisiert Frage-7-Antwort auf 'low' | 'medium' | 'high'."""
    lower = answer.strip().lower()
    if any(w in lower for w in ("wenig", "low", "gering", "kaum", "1")):
        return "low"
    if any(w in lower for w in ("stark", "high", "viel", "voll", "sehr", "3")):
        return "high"
    return "medium"


def _parse_list(answer: str) -> list[str]:
    """Komma-/Semikolon-/Zeilenumbruch-getrennte Antwort → Liste."""
    return [item.strip() for item in re.split(r"[,;\n]+", answer) if item.strip()]


# Discord Intents — wir brauchen DMs und Message Content für jetzt minimal
intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info("bot_ready", user=str(bot.user), guilds=len(bot.guilds))
    await init_db()

    # Slash-Commands syncen
    if settings.discord_guild_id:
        # Schneller für Dev: nur einem Guild syncen
        guild = discord.Object(id=int(settings.discord_guild_id))
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        log.info("commands_synced", guild_id=settings.discord_guild_id, count=len(synced))
    else:
        synced = await bot.tree.sync()
        log.info("commands_synced_global", count=len(synced))


@bot.tree.command(name="ping", description="Prüfe ob der Bot lebt")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("pong.", ephemeral=True)


@bot.tree.command(name="start", description="Beginne ein neues Erlebnis")
async def start(interaction: discord.Interaction):
    discord_id = str(interaction.user.id)

    # Bereits registriert?
    async with get_session() as session:
        existing = await session.scalar(
            select(PlayerProfile)
            .join(Player, PlayerProfile.player_id == Player.id)
            .where(Player.discord_id == discord_id)
        )
    if existing is not None:
        await interaction.response.send_message(
            "Du bist bereits registriert. Nutze `/case` um deine Akte zu sehen.",
            ephemeral=True,
        )
        return

    # Sofort im Server antworten — dann läuft der Rest in der DM
    await interaction.response.send_message("Ich schreibe dir eine DM.", ephemeral=True)
    log.info("onboarding_start", discord_id=discord_id)

    # DM-Kanal öffnen
    try:
        dm = await interaction.user.create_dm()
        await dm.send("Bevor wir beginnen — ein paar Fragen. Antworte einfach in diesem Chat.")
    except discord.Forbidden:
        await interaction.followup.send(
            "Konnte keine DM öffnen. Bitte aktiviere DMs von Servermitgliedern "
            "in deinen Discord-Einstellungen (Privatsphäre & Sicherheit).",
            ephemeral=True,
        )
        return

    # Fragen sequenziell stellen, auf jede Antwort warten
    check = _dm_check(interaction.user.id, dm.id)
    raw_answers: dict[str, str] = {}

    for key, question in _ONBOARDING_QUESTIONS:
        await dm.send(question)
        try:
            msg = await bot.wait_for("message", check=check, timeout=_ONBOARDING_TIMEOUT)
            raw_answers[key] = msg.content
        except asyncio.TimeoutError:
            await dm.send(
                "Keine Antwort erhalten. Das Onboarding wird abgebrochen. "
                "Starte erneut mit `/start` wenn du bereit bist."
            )
            log.info("onboarding_timeout", discord_id=discord_id, last_question=key)
            return

    # Abschlussnachricht (aus Prompt)
    await dm.send("Eingang vermerkt. Du hörst von uns.")

    # Antworten parsen
    city, neighborhood = _parse_city(raw_answers["city_input"])
    intensity = _parse_intensity(raw_answers["intensity"])
    close_people = _parse_list(raw_answers["close_people"])
    now = datetime.now(timezone.utc)

    # In DB speichern
    try:
        async with get_session() as session:
            player = await session.scalar(
                select(Player).where(Player.discord_id == discord_id)
            )
            if player is None:
                player = Player(
                    id=uuid4(),
                    discord_id=discord_id,
                    reality_score=1.0,
                    created_at=now,
                    onboarded_at=now,
                )
                session.add(player)
            else:
                player.onboarded_at = now

            await session.flush()  # player.id für FK verfügbar machen

            session.add(PlayerProfile(
                player_id=player.id,
                city=city,
                neighborhood=neighborhood,
                routine=raw_answers["routine"],
                close_people=close_people,
                fears=[raw_answers["fear"]],
                locations=[raw_answers["location"]],
                raw_answers=raw_answers,
                personalization_intensity=intensity,
            ))
    except IntegrityError:
        log.info("onboarding_duplicate", discord_id=discord_id)
        return

    log.info("onboarding_complete", discord_id=discord_id, city=city, intensity=intensity)


@bot.tree.command(name="case", description="Zeige deine aktuelle Akte")
async def case(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    async with get_session() as session:
        player = await session.scalar(
            select(Player).where(Player.discord_id == str(interaction.user.id))
        )
        if player is None:
            await interaction.followup.send(
                "Kein Profil gefunden. Starte mit `/start`.", ephemeral=True
            )
            return

        active_case = await session.scalar(
            select(Case)
            .where(Case.player_id == player.id, Case.phase != "closed")
            .order_by(Case.started_at.desc())
        )
        if active_case is None:
            await interaction.followup.send(
                "Du hast keinen aktiven Fall. Starte mit `/start`.", ephemeral=True
            )
            return

        notes = list(
            await session.scalars(
                select(PlayerNote)
                .where(PlayerNote.case_id == active_case.id)
                .order_by(PlayerNote.created_at.desc())
                .limit(5)
            )
        )

    embed = discord.Embed(
        title=f"Akte: {active_case.title}",
        description="*Beschreibung des Vermissten wird zusammengestellt...*",
        color=discord.Color.dark_red(),
    )
    embed.add_field(
        name="Phase",
        value=_PHASE_LABELS.get(active_case.phase, active_case.phase),
        inline=True,
    )
    embed.add_field(
        name="Eröffnet",
        value=discord.utils.format_dt(active_case.started_at, "D"),
        inline=True,
    )

    if notes:
        for i, n in enumerate(reversed(notes), 1):
            embed.add_field(name=f"Spur {i}", value=n.text[:1000], inline=False)
    else:
        embed.add_field(
            name="Offene Spuren",
            value="Noch keine Spuren erfasst. Nutze `/note <text>` um Hinweise zu dokumentieren.",
            inline=False,
        )

    embed.set_footer(text=f"Reality Score: {player.reality_score:.2f}")
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="note", description="Speichere eine Notiz zu deinem Fall")
@app_commands.describe(text="Was möchtest du notieren?", spur="Optionale Spurennummer aus /akte")
async def note(interaction: discord.Interaction, text: str, spur: int | None = None):
    await interaction.response.defer(ephemeral=True)
    now = datetime.now(timezone.utc)

    async with get_session() as session:
        player = await session.scalar(
            select(Player).where(Player.discord_id == str(interaction.user.id))
        )
        if player is None:
            await interaction.followup.send(
                "Kein Profil gefunden. Starte mit `/start`.", ephemeral=True
            )
            return

        active_case = await session.scalar(
            select(Case)
            .where(Case.player_id == player.id, Case.phase != "closed")
            .order_by(Case.started_at.desc())
        )
        if active_case is None:
            await interaction.followup.send(
                "Du hast keinen aktiven Fall. Starte mit `/start`.", ephemeral=True
            )
            return

        fact_id = None
        snapshot_value = None

        if spur is not None:
            facts = list(await session.scalars(
                select(Fact).where(Fact.case_id == active_case.id).order_by(Fact.created_at)
            ))
            if spur < 1 or spur > len(facts):
                await interaction.followup.send(
                    f"Ungültige Spurennummer {spur}. Nutze `/akte` für die Übersicht.",
                    ephemeral=True,
                )
                return
            linked_fact = facts[spur - 1]
            fact_id = linked_fact.id
            layer = await session.scalar(
                select(FactLayer)
                .where(FactLayer.fact_id == linked_fact.id, FactLayer.layer_type == "perceived")
                .order_by(FactLayer.version.desc())
            )
            snapshot_value = layer.value if layer else linked_fact.description

        session.add(
            PlayerNote(
                id=uuid4(),
                case_id=active_case.id,
                text=text,
                created_at=now,
                fact_id=fact_id,
                snapshot_value=snapshot_value,
            )
        )
        await TimelineScorer().score_action(active_case.id, "note", text, session)
        new_phase = await _check_lifecycle(session, active_case, player)

    suffix = f" (Spur {spur})" if spur is not None else ""
    await interaction.followup.send(
        f"Notiz gespeichert {discord.utils.format_dt(now, 'T')}{suffix}:\n> {text[:200]}",
        ephemeral=True,
    )
    if new_phase:
        await interaction.followup.send(phase_transition_message(new_phase), ephemeral=True)


@bot.tree.command(name="journal", description="Übersicht aller Notizen des aktiven Falls")
async def journal(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    async with get_session() as session:
        player = await session.scalar(
            select(Player).where(Player.discord_id == str(interaction.user.id))
        )
        if player is None:
            await interaction.followup.send(
                "Kein Profil gefunden. Starte mit `/start`.", ephemeral=True
            )
            return

        active_case = await session.scalar(
            select(Case)
            .where(Case.player_id == player.id, Case.phase != "closed")
            .order_by(Case.started_at.desc())
        )
        if active_case is None:
            await interaction.followup.send(
                "Du hast keinen aktiven Fall. Starte mit `/begin`.", ephemeral=True
            )
            return

        notes = list(await session.scalars(
            select(PlayerNote)
            .where(PlayerNote.case_id == active_case.id)
            .order_by(PlayerNote.created_at)
        ))
        if not notes:
            await interaction.followup.send("Noch keine Notizen. Nutze `/note <text>`.", ephemeral=True)
            return

        lines: list[str] = []
        for i, n in enumerate(notes, 1):
            ts = discord.utils.format_dt(n.created_at, "d")
            preview = n.text[:80].replace("\n", " ")
            marker = ""
            if n.fact_id is not None and n.snapshot_value is not None:
                current_layer = await session.scalar(
                    select(FactLayer)
                    .where(FactLayer.fact_id == n.fact_id, FactLayer.layer_type == "perceived")
                    .order_by(FactLayer.version.desc())
                )
                current_val = current_layer.value if current_layer else ""
                if current_val != n.snapshot_value:
                    marker = " ⚠️ Veränderung erkannt"
            lines.append(f"**{i}.** [{ts}] {preview}{marker}")

    embed = discord.Embed(
        title=f"Journal: {active_case.title}",
        description="\n".join(lines),
        color=discord.Color.dark_red(),
    )
    embed.set_footer(text="Nutze /vergleichen <nummer> für Details.")
    await interaction.followup.send(embed=embed, ephemeral=True)


def _word_diff(old: str, new: str) -> str:
    old_words = old.split()
    new_words = new.split()
    diff = list(difflib.ndiff(old_words, new_words))
    return " ".join(diff)


@bot.tree.command(name="vergleichen", description="Vergleiche eine Notiz mit dem aktuellen Spurenstand")
@app_commands.describe(nummer="Notiznummer aus /journal")
async def vergleichen(interaction: discord.Interaction, nummer: int):
    await interaction.response.defer(ephemeral=True)

    async with get_session() as session:
        player = await session.scalar(
            select(Player).where(Player.discord_id == str(interaction.user.id))
        )
        if player is None:
            await interaction.followup.send(
                "Kein Profil gefunden. Starte mit `/start`.", ephemeral=True
            )
            return

        active_case = await session.scalar(
            select(Case)
            .where(Case.player_id == player.id, Case.phase != "closed")
            .order_by(Case.started_at.desc())
        )
        if active_case is None:
            await interaction.followup.send(
                "Du hast keinen aktiven Fall. Starte mit `/begin`.", ephemeral=True
            )
            return

        notes = list(await session.scalars(
            select(PlayerNote)
            .where(PlayerNote.case_id == active_case.id)
            .order_by(PlayerNote.created_at)
        ))
        if nummer < 1 or nummer > len(notes):
            await interaction.followup.send(
                "Ungültige Notiznummer. Nutze `/journal` für die Übersicht.", ephemeral=True
            )
            return

        n = notes[nummer - 1]

        if n.fact_id is None:
            await interaction.followup.send(
                "Diese Notiz ist nicht an eine Spur gebunden.", ephemeral=True
            )
            return

        current_layer = await session.scalar(
            select(FactLayer)
            .where(FactLayer.fact_id == n.fact_id, FactLayer.layer_type == "perceived")
            .order_by(FactLayer.version.desc())
        )
        current_val = current_layer.value if current_layer else ""

    ts = discord.utils.format_dt(n.created_at, "f")
    embed = discord.Embed(title=f"Vergleich Notiz {nummer}", color=discord.Color.dark_red())
    embed.add_field(name="Deine Notiz", value=f"{n.text[:500]}\n*{ts}*", inline=False)
    embed.add_field(name="Spur damals", value=n.snapshot_value[:500] or "–", inline=False)
    embed.add_field(name="Spur jetzt", value=current_val[:500] or "–", inline=False)

    if current_val == n.snapshot_value:
        embed.set_footer(text="Keine Veränderungen seit deiner Notiz.")
    else:
        diff_text = _word_diff(n.snapshot_value, current_val)
        embed.add_field(
            name="Diff",
            value=f"```diff\n{diff_text[:900]}\n```",
            inline=False,
        )

    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="begin", description="Starte deinen ersten Fall")
async def begin(interaction: discord.Interaction):
    discord_id = str(interaction.user.id)

    async with get_session() as session:
        player = await session.scalar(
            select(Player).where(Player.discord_id == discord_id)
        )
        if player is None:
            await interaction.response.send_message(
                "Starte zuerst mit `/start`.", ephemeral=True
            )
            return

        profile = await session.scalar(
            select(PlayerProfile).where(PlayerProfile.player_id == player.id)
        )
        if profile is None:
            await interaction.response.send_message(
                "Starte zuerst mit `/start`.", ephemeral=True
            )
            return

        active_case = await session.scalar(
            select(Case)
            .where(Case.player_id == player.id, Case.phase != "closed")
            .order_by(Case.started_at.desc())
        )
        if active_case is not None:
            await interaction.response.send_message(
                "Du hast bereits einen aktiven Fall. Nutze `/case`.", ephemeral=True
            )
            return

        player_id = player.id
        player_profile = {
            "city": profile.city,
            "neighborhood": profile.neighborhood,
            "routine": profile.routine,
            "close_people": profile.close_people,
            "fears": profile.fears,
            "locations": profile.locations,
            "personalization_intensity": profile.personalization_intensity,
        }

    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send("Die Akte wird zusammengestellt...", ephemeral=True)

    try:
        async with get_session() as session:
            await CaseGenerator().generate(
                player_id=player_id,
                player_profile=player_profile,
                session=session,
            )
    except CaseGenerationError as exc:
        log.error("case_generation_failed", discord_id=discord_id, error=str(exc))
        await interaction.followup.send(
            "Fehler beim Erstellen der Akte. Versuche es erneut.", ephemeral=True
        )
        return
    except Exception as exc:
        log.error("case_generation_unexpected_error", discord_id=discord_id, error=str(exc), exc_info=True)
        await interaction.followup.send("Unbekannter Fehler. Bitte melde das.", ephemeral=True)
        return

    log.info("case_generation_done", discord_id=discord_id)
    await interaction.followup.send(
        "Ermittlungsakte angelegt. Verfügbare Befehle:\n"
        "`/akte` — Übersicht aller Spuren\n"
        "`/spur <nr>` — Spur verfolgen\n"
        "`/befragen <name>` — Zeugen befragen\n\n"
        "Viel Erfolg, Ermittler.",
        ephemeral=True,
    )


async def _check_lifecycle(session, case, player) -> str | None:
    """Queries action_count + unique_npcs, evaluates transition, applies if needed.
    Returns new phase name if a transition happened, else None.
    Must be called inside an open session before commit.
    """
    note_count = await session.scalar(
        select(func.count()).select_from(PlayerNote).where(PlayerNote.case_id == case.id)
    ) or 0
    # Each /befragen creates one FactLayer "claimed" row — direct count of befragen calls.
    befragen_count = await session.scalar(
        select(func.count())
        .select_from(FactLayer)
        .join(Fact, FactLayer.fact_id == Fact.id)
        .where(Fact.case_id == case.id, FactLayer.layer_type == "claimed")
    ) or 0
    # /spur has no dedicated table; count perceived layers with version > 1 as a lower bound
    # (each corruption round on a perceived layer means /spur was called heavily enough to drift).
    spur_count = await session.scalar(
        select(func.count())
        .select_from(FactLayer)
        .join(Fact, FactLayer.fact_id == Fact.id)
        .where(Fact.case_id == case.id, FactLayer.layer_type == "perceived", FactLayer.version > 1)
    ) or 0
    action_count = note_count + befragen_count + spur_count

    unique_npcs = await session.scalar(
        select(func.count(func.distinct(FactLayer.modified_by)))
        .join(Fact, FactLayer.fact_id == Fact.id)
        .where(Fact.case_id == case.id, FactLayer.layer_type == "claimed")
    ) or 0
    new_phase = evaluate_transition(case, action_count, unique_npcs, player.reality_score)
    if new_phase:
        await apply_transition(session, case, new_phase, reason="player_action")
    return new_phase


def _reality_label(score: float) -> str:
    if score >= 0.9:
        return "Realität stabil"
    if score >= 0.7:
        return "Leichte Unschärfen"
    return "Realität instabil"


@bot.tree.command(name="akte", description="Übersicht aller Spuren des aktiven Falls")
async def akte(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    async with get_session() as session:
        player = await session.scalar(
            select(Player).where(Player.discord_id == str(interaction.user.id))
        )
        if player is None:
            await interaction.followup.send(
                "Kein Profil gefunden. Starte mit `/start`.", ephemeral=True
            )
            return

        active_case = await session.scalar(
            select(Case)
            .where(Case.player_id == player.id, Case.phase != "closed")
            .order_by(Case.started_at.desc())
        )
        if active_case is None:
            await interaction.followup.send(
                "Du hast keinen aktiven Fall. Starte mit `/begin`.", ephemeral=True
            )
            return

        facts = list(await session.scalars(
            select(Fact).where(Fact.case_id == active_case.id).order_by(Fact.created_at)
        ))
        perceived: dict = {}
        for fact in facts:
            layer = await session.scalar(
                select(FactLayer)
                .where(FactLayer.fact_id == fact.id, FactLayer.layer_type == "perceived")
                .order_by(FactLayer.version.desc())
            )
            if layer:
                perceived[fact.id] = layer.value


    embed = discord.Embed(
        title=f"Akte: {active_case.title}",
        color=discord.Color.dark_red(),
    )
    embed.add_field(
        name="Phase",
        value=_PHASE_LABELS.get(active_case.phase, active_case.phase),
        inline=True,
    )
    embed.set_footer(
        text=f"Reality Score: {player.reality_score:.2f} — {_reality_label(player.reality_score)}"
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

    for i, fact in enumerate(facts, 1):
        text = perceived.get(fact.id, fact.description)
        await interaction.followup.send(f"**[{i}]** {text}", ephemeral=True)

    await interaction.followup.send(
        "Nutze `/spur <nummer>` um eine Spur zu verfolgen, `/befragen <name>` für Zeugen.",
        ephemeral=True,
    )


@bot.tree.command(name="spur", description="Spur verfolgen")
@app_commands.describe(nummer="Spurennummer aus /akte")
async def spur(interaction: discord.Interaction, nummer: int):
    await interaction.response.defer(ephemeral=True)
    new_score: float

    async with get_session() as session:
        player = await session.scalar(
            select(Player).where(Player.discord_id == str(interaction.user.id))
        )
        if player is None:
            await interaction.followup.send(
                "Kein Profil gefunden. Starte mit `/start`.", ephemeral=True
            )
            return

        active_case = await session.scalar(
            select(Case)
            .where(Case.player_id == player.id, Case.phase != "closed")
            .order_by(Case.started_at.desc())
        )
        if active_case is None:
            await interaction.followup.send(
                "Du hast keinen aktiven Fall. Starte mit `/begin`.", ephemeral=True
            )
            return

        facts = list(await session.scalars(
            select(Fact).where(Fact.case_id == active_case.id).order_by(Fact.created_at)
        ))
        if nummer < 1 or nummer > len(facts):
            await interaction.followup.send(
                "Ungültige Spurennummer. Nutze `/akte` für die Übersicht.", ephemeral=True
            )
            return

        fact = facts[nummer - 1]
        layer = await session.scalar(
            select(FactLayer)
            .where(FactLayer.fact_id == fact.id, FactLayer.layer_type == "perceived")
            .order_by(FactLayer.version.desc())
        )
        text = layer.value if layer else fact.description

        truth_engine = TruthEngine(db_session=session)
        new_score = await truth_engine.adjust_reality_score(player.id, -0.02)
        if new_score < DRIFT_THRESHOLD:
            await truth_engine.apply_corruption(player.id, corruption_intensity(new_score))
        await TimelineScorer().score_action(active_case.id, "spur", text, session)
        new_phase = await _check_lifecycle(session, active_case, player)

    embed = discord.Embed(
        title=f"Spur {nummer}",
        description=text,
        color=discord.Color.dark_red(),
    )
    embed.set_footer(text=f"Reality Score: {new_score:.2f} — {_reality_label(new_score)}")
    await interaction.followup.send(embed=embed, ephemeral=True)
    if new_phase:
        await interaction.followup.send(phase_transition_message(new_phase), ephemeral=True)


@bot.tree.command(name="befragen", description="Zeugen befragen")
@app_commands.describe(name="Name des Zeugen")
async def befragen(interaction: discord.Interaction, name: str):
    await interaction.response.defer(ephemeral=True)
    testimony: str
    npc_found: NPC

    async with get_session() as session:
        player = await session.scalar(
            select(Player).where(Player.discord_id == str(interaction.user.id))
        )
        if player is None:
            await interaction.followup.send(
                "Kein Profil gefunden. Starte mit `/start`.", ephemeral=True
            )
            return

        active_case = await session.scalar(
            select(Case)
            .where(Case.player_id == player.id, Case.phase != "closed")
            .order_by(Case.started_at.desc())
        )
        if active_case is None:
            await interaction.followup.send(
                "Du hast keinen aktiven Fall. Starte mit `/begin`.", ephemeral=True
            )
            return

        npcs = list(await session.scalars(
            select(NPC).where(NPC.case_id == active_case.id)
        ))
        npc_found = next((n for n in npcs if name.lower() in n.name.lower()), None)
        if npc_found is None:
            await interaction.followup.send(
                f"Kein Zeuge namens '{name}' bekannt.", ephemeral=True
            )
            return

        existing = await session.scalar(
            select(FactLayer)
            .join(Fact, FactLayer.fact_id == Fact.id)
            .where(
                Fact.case_id == active_case.id,
                FactLayer.layer_type == "claimed",
                FactLayer.modified_by == f"npc:{npc_found.name}",
            )
            .order_by(FactLayer.modified_at.desc())
        )

        if existing:
            testimony = existing.value
        else:
            npc_prompt = (_PROMPT_DIR / "npc_witness.md").read_text("utf-8")
            npc_prompt = (npc_prompt
                .replace("{{ name }}", npc_found.name)
                .replace("{{ relationship }}", npc_found.relationship_to_missing or "unbekannt")
                .replace("{{ personality_brief }}", npc_found.personality.get("brief", ""))
                .replace("{{ knowledge }}", json.dumps(npc_found.knowledge, ensure_ascii=False))
                .replace("{{ memory_snippets }}", "Erste Befragung."))

            response = await asyncio.to_thread(
                LLMClient().complete,
                system=npc_prompt,
                user="Der Ermittler fragt nach dem Vermisstenfall.",
                max_tokens=512,
                temperature=0.8,
            )
            testimony = response.text.strip()

            first_fact = await session.scalar(
                select(Fact).where(Fact.case_id == active_case.id)
                .order_by(Fact.created_at).limit(1)
            )
            truth_engine = TruthEngine(db_session=session)
            await truth_engine.record_claim(
                fact_id=first_fact.id, value=testimony, npc_name=npc_found.name
            )

        # Reality-Score senken (eigene Session da die obige ggf. schon committed hat)
        async with get_session() as s2:
            te2 = TruthEngine(db_session=s2)
            new_score = await te2.adjust_reality_score(player.id, -0.01)

        await TimelineScorer().score_action(active_case.id, "befragen", testimony, session)
        player.reality_score = new_score  # sync in-memory so evaluate_transition sees updated score
        new_phase = await _check_lifecycle(session, active_case, player)

    embed = discord.Embed(
        title=npc_found.name,
        description=testimony,
        color=discord.Color.greyple(),
    )
    embed.set_footer(text=npc_found.relationship_to_missing or "")
    await interaction.followup.send(embed=embed, ephemeral=True)
    if new_phase:
        await interaction.followup.send(phase_transition_message(new_phase), ephemeral=True)


@bot.tree.command(name="admin_seed_timeline", description="[Admin] Timeline für einen Fall seeden")
@app_commands.describe(case_id="UUID des Falls (aus der DB)")
async def admin_seed_timeline(interaction: discord.Interaction, case_id: str):
    if str(interaction.user.id) not in settings.admin_discord_ids:
        await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        case_uuid = __import__("uuid").UUID(case_id)
    except ValueError:
        await interaction.followup.send("Ungültige UUID.", ephemeral=True)
        return

    try:
        async with get_session() as session:
            case = await session.scalar(select(Case).where(Case.id == case_uuid))
            if case is None:
                await interaction.followup.send(f"Fall `{case_id}` nicht gefunden.", ephemeral=True)
                return

            profile = await session.scalar(
                select(PlayerProfile).where(PlayerProfile.player_id == case.player_id)
            )
            if profile is None:
                await interaction.followup.send("Kein Spieler-Profil für diesen Fall.", ephemeral=True)
                return

            seeder = TimelineSeeder(db_session=session)
            result = await seeder.seed_case(case_uuid, profile)

    except TimelineSeederError as exc:
        log.error("timeline_seeder_failed", case_id=case_id, error=str(exc))
        await interaction.followup.send(f"Fehler beim Seeden: {exc}", ephemeral=True)
        return

    await interaction.followup.send(
        f"Timeline für Fall `{case_id}` geseedet:\n"
        f"investigator: **{result.investigator_count}** Events\n"
        f"shadow_a: **{result.shadow_a_count}** Events\n"
        f"shadow_b: **{result.shadow_b_count}** Events",
        ephemeral=True,
    )


@bot.tree.command(name="admin_force_phase", description="[Admin] Setzt die Phase des aktiven Falls direkt")
@app_commands.describe(phase="Ziel-Phase")
async def admin_force_phase(interaction: discord.Interaction, phase: str):
    if str(interaction.user.id) not in settings.admin_discord_ids:
        await interaction.response.send_message("Keine Berechtigung.", ephemeral=True)
        return

    if phase not in VALID_PHASES:
        await interaction.response.send_message(
            f"Ungültige Phase. Erlaubt: {', '.join(VALID_PHASES)}", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    async with get_session() as session:
        player = await session.scalar(
            select(Player).where(Player.discord_id == str(interaction.user.id))
        )
        if player is None:
            await interaction.followup.send("Kein Profil gefunden.", ephemeral=True)
            return

        active_case = await session.scalar(
            select(Case)
            .where(Case.player_id == player.id, Case.phase != "closed")
            .order_by(Case.started_at.desc())
        )
        if active_case is None:
            await interaction.followup.send("Kein aktiver Fall.", ephemeral=True)
            return

        await apply_transition(session, active_case, phase, reason="admin_override")

    await interaction.followup.send(
        f"Fall `{active_case.title}` — Phase auf `{phase}` gesetzt.", ephemeral=True
    )


def main():
    log.info("bot_starting", environment=settings.environment)
    bot.run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
