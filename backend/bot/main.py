"""
Widerspruch Discord Bot — Entry Point.

Startet den Bot und registriert die Slash-Commands.
"""
import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

import structlog

from backend.config import settings

# Logging-Setup
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, settings.log_level.upper(), logging.INFO)
    ),
)
log = structlog.get_logger()


# Discord Intents — wir brauchen DMs und Message Content für jetzt minimal
intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info("bot_ready", user=str(bot.user), guilds=len(bot.guilds))

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
    # TODO: Phase 1 — Onboarding-Flow als DM
    await interaction.response.send_message(
        "Onboarding ist noch nicht implementiert. Komm wieder.",
        ephemeral=True,
    )


@bot.tree.command(name="case", description="Zeige deine aktuelle Akte")
async def case(interaction: discord.Interaction):
    # TODO: Phase 1 — Aktuellen Case anzeigen
    await interaction.response.send_message(
        "Du hast keinen aktiven Fall.",
        ephemeral=True,
    )


@bot.tree.command(name="note", description="Speichere eine Notiz zu deinem Fall")
@app_commands.describe(text="Was möchtest du notieren?")
async def note(interaction: discord.Interaction, text: str):
    # TODO: Phase 1 — Notiz speichern
    await interaction.response.send_message(
        f"Notiz vermerkt (noch nicht persistiert): {text[:80]}",
        ephemeral=True,
    )


def main():
    log.info("bot_starting", environment=settings.environment)
    bot.run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
