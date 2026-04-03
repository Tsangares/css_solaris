"""
Communication Cog
Handles /say command for mods and players.
"""

import discord
from discord import app_commands
from discord.ext import commands
from models.game import GameStatus
from typing import List
from utils import database, permissions


class Communication(commands.Cog):
    """Cog for in-game communication commands."""

    def __init__(self, bot):
        self.bot = bot

    def _find_game_from_channel(self, channel_id: int):
        """Find a game from a channel ID. Returns (game, day) or (None, None)."""
        player_actions = self.bot.get_cog('PlayerActions')
        if player_actions:
            return player_actions.get_game_from_channel(channel_id)
        return None, None

    async def npc_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        npcs = database.load_npcs()
        choices = []
        for npc in npcs.values():
            if not current or current.lower() in npc.name.lower():
                choices.append(app_commands.Choice(name=f"\U0001f916 {npc.name}", value=npc.name))
        return choices[:25]

    @app_commands.command(name="say", description="Send a message in the game channel (anonymous or as NPC)")
    @app_commands.describe(
        message="The message to send",
        as_npc="(Mod only) Send the message as an NPC by name"
    )
    @app_commands.autocomplete(as_npc=npc_autocomplete)
    async def say(self, interaction: discord.Interaction, message: str, as_npc: str = None):
        """Send a message in the game channel."""
        game, day = self._find_game_from_channel(interaction.channel.id)

        if not game:
            await interaction.response.send_message(
                "This channel is not a game channel!",
                ephemeral=True
            )
            return

        if game.status != GameStatus.ACTIVE:
            await interaction.response.send_message(
                "This game is not currently active!",
                ephemeral=True
            )
            return

        is_mod = permissions.can_manage_game(interaction.user.id, interaction.user, game)

        # NPC speech is mod-only
        if as_npc and not is_mod:
            await interaction.response.send_message(
                "Only moderators can speak as NPCs!",
                ephemeral=True
            )
            return

        # Check if player is allowed to /say
        if not is_mod:
            if not permissions.is_player_in_game(interaction.user.id, game):
                await interaction.response.send_message(
                    "You are not a player in this game!",
                    ephemeral=True
                )
                return
            if not game.settings.get("player_say_enabled", False):
                await interaction.response.send_message(
                    "Player /say is not enabled for this game. A moderator can enable it with `/settings`.",
                    ephemeral=True
                )
                return

        # Acknowledge silently, then send as the bot so it doesn't show who used /say
        await interaction.response.send_message("Sent!", ephemeral=True)

        # Send as NPC
        if as_npc:
            npc = database.get_npc(as_npc)
            if not npc:
                await interaction.followup.send(f"NPC '{as_npc}' not found!", ephemeral=True)
                return

            embed = discord.Embed(
                description=message,
                color=discord.Color.dark_grey()
            )
            embed.set_author(name=f"\U0001f916 {npc.name}")

            await interaction.channel.send(embed=embed)
            return

        # Send as bot - no attribution
        if is_mod:
            embed = discord.Embed(
                description=message,
                color=discord.Color.gold()
            )
            embed.set_author(name="\U0001f4e2 Announcement")
            await interaction.channel.send(embed=embed)
        else:
            embed = discord.Embed(
                description=message,
                color=discord.Color.light_grey()
            )
            embed.set_author(name="\U0001f4ac Anonymous Message")
            await interaction.channel.send(embed=embed)


    @app_commands.command(name="narrate", description="Send narration to the discussion thread (MC only)")
    @app_commands.describe(
        text="Quick narration text, OR paste a message link to forward with images/formatting"
    )
    async def narrate(self, interaction: discord.Interaction, text: str = None):
        """Send narration to the discussion. Accepts text or a Discord message link."""
        game, day = self._find_game_from_channel(interaction.channel.id)
        if not game:
            games = database.load_games()
            for g in games.values():
                if g.team_channels.get("mc") == interaction.channel.id:
                    game = g
                    break

        if not game:
            await interaction.response.send_message("Use this in a game channel or the MC booth.", ephemeral=True)
            return

        if not permissions.can_run_game(interaction.user.id, game):
            await interaction.response.send_message("Only the MC can narrate!", ephemeral=True)
            return

        disc_id = game.channels.get(game.current_day, {}).get("discussion_channel_id")
        if not disc_id:
            await interaction.response.send_message("No active discussion thread found.", ephemeral=True)
            return

        try:
            disc_thread = await interaction.client.fetch_channel(disc_id)

            # Check if text contains a Discord message link
            import re, aiohttp, io
            link_match = re.search(r'https://(?:discord\.com|discordapp\.com)/channels/(\d+)/(\d+)/(\d+)', text or "")

            if link_match:
                # Forward a specific message by link
                _, channel_id, message_id = link_match.groups()
                try:
                    source_channel = await interaction.client.fetch_channel(int(channel_id))
                    source_msg = await source_channel.fetch_message(int(message_id))
                except Exception:
                    await interaction.response.send_message("Couldn't fetch that message. Make sure the link is correct and the bot can see the channel.", ephemeral=True)
                    return

                # Build preview embed
                preview_embed = discord.Embed(
                    title="📖 Narration Preview",
                    description=source_msg.content if source_msg.content else "*No text — images only*",
                    color=discord.Color.dark_purple()
                )
                image_attachments = [a for a in source_msg.attachments if _is_image(a)]
                if image_attachments:
                    preview_embed.set_image(url=image_attachments[0].url)
                if len(source_msg.attachments) > 1:
                    preview_embed.set_footer(text=f"+ {len(source_msg.attachments) - 1} more attachment(s)")

                # Show preview with confirm/cancel buttons
                view = NarrateConfirmView(source_msg, disc_thread)
                await interaction.response.send_message(
                    "**Preview — send this to the discussion?**",
                    embed=preview_embed,
                    view=view,
                    ephemeral=True
                )

            elif text:
                # Quick text narration
                embed = discord.Embed(
                    description=f"*{text}*",
                    color=discord.Color.dark_purple()
                )
                embed.set_author(name="\U0001f4d6 Narration")
                await disc_thread.send(embed=embed)
                await interaction.response.send_message("Narration sent!", ephemeral=True)

            else:
                await interaction.response.send_message(
                    "**How to use /narrate:**\n"
                    "- `/narrate The ship creaks ominously...` — quick text\n"
                    "- Write a message in the MC booth with images/markdown, right-click it → **Copy Message Link**, then `/narrate <link>`",
                    ephemeral=True
                )

        except Exception as e:
            try:
                await interaction.followup.send(f"Failed to send narration: {e}", ephemeral=True)
            except Exception:
                await interaction.response.send_message(f"Failed to send narration: {e}", ephemeral=True)


class NarrateConfirmView(discord.ui.View):
    def __init__(self, source_msg, disc_thread):
        super().__init__(timeout=120)
        self.source_msg = source_msg
        self.disc_thread = disc_thread

    @discord.ui.button(label="Send to Discussion", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        msg = self.source_msg
        image_attachments = [a for a in msg.attachments if _is_image(a)]
        other_files = [a for a in msg.attachments if not _is_image(a)]

        # Build narration embed
        narration_embed = discord.Embed(color=discord.Color.dark_purple())
        narration_embed.set_author(name="\U0001f4d6 Narration")
        if msg.content:
            narration_embed.description = msg.content
        if image_attachments:
            narration_embed.set_image(url=image_attachments[0].url)

        await self.disc_thread.send(embed=narration_embed)

        # Additional images as files
        for attachment in image_attachments[1:]:
            try:
                file = await attachment.to_file()
                await self.disc_thread.send(file=file)
            except Exception:
                pass

        # Non-image files
        for attachment in other_files:
            try:
                file = await attachment.to_file()
                await self.disc_thread.send(file=file)
            except Exception:
                pass

        await interaction.edit_original_response(content="✅ Narration sent!", embed=None, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Narration cancelled.", embed=None, view=None)


def _is_image(attachment) -> bool:
    """Check if an attachment is an image."""
    if attachment.content_type and attachment.content_type.startswith("image"):
        return True
    ext = attachment.filename.lower().rsplit(".", 1)[-1] if "." in attachment.filename else ""
    return ext in ("png", "jpg", "jpeg", "gif", "webp")


async def setup(bot):
    """Setup function for cog."""
    await bot.add_cog(Communication(bot))
