"""
Widerspruch Discord Bot — Entry Point.

Startet den Bot und registriert die Slash-Commands.
"""
import asyncio
import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

import structlog

from backend.config import settings
from backend.core.case_generator import CaseGenerationError, CaseGenerator
from backend.db import get_session, init_db
from backend.db.models import Case, Player, PlayerNote, PlayerProfile

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
    async with get_session() as session:
        player = await session.scalar(
            select(Player).where(Player.discord_id == str(interaction.user.id))
        )
        if player is None:
            await interaction.response.send_message(
                "Kein Profil gefunden. Starte mit `/start`.", ephemeral=True
            )
            return

        active_case = await session.scalar(
            select(Case)
            .where(Case.player_id == player.id, Case.phase != "closed")
            .order_by(Case.started_at.desc())
        )
        if active_case is None:
            await interaction.response.send_message(
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
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="note", description="Speichere eine Notiz zu deinem Fall")
@app_commands.describe(text="Was möchtest du notieren?")
async def note(interaction: discord.Interaction, text: str):
    now = datetime.now(timezone.utc)

    async with get_session() as session:
        player = await session.scalar(
            select(Player).where(Player.discord_id == str(interaction.user.id))
        )
        if player is None:
            await interaction.response.send_message(
                "Kein Profil gefunden. Starte mit `/start`.", ephemeral=True
            )
            return

        active_case = await session.scalar(
            select(Case)
            .where(Case.player_id == player.id, Case.phase != "closed")
            .order_by(Case.started_at.desc())
        )
        if active_case is None:
            await interaction.response.send_message(
                "Du hast keinen aktiven Fall. Starte mit `/start`.", ephemeral=True
            )
            return

        session.add(
            PlayerNote(id=uuid4(), case_id=active_case.id, text=text, created_at=now)
        )

    await interaction.response.send_message(
        f"Notiz gespeichert {discord.utils.format_dt(now, 'T')}:\n> {text[:200]}",
        ephemeral=True,
    )


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

    log.info("case_generation_done", discord_id=discord_id)
    await interaction.followup.send("Deine Akte ist bereit. Nutze `/case`.", ephemeral=True)


def main():
    log.info("bot_starting", environment=settings.environment)
    bot.run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
