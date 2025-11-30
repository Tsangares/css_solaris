"""
Player Actions Cog
Handles /join and /vote commands.
"""

import discord
from discord import app_commands
from discord.ext import commands
from models.game import Game, GameStatus
from utils import database, permissions, game_logic
from typing import Dict


class PlayerActions(commands.Cog):
    """Cog for player actions like joining and voting."""

    def __init__(self, bot):
        self.bot = bot
        # Store votes in memory: {game_name: {day: {voter_id: target_id}}}
        self.votes: Dict[str, Dict[int, Dict[int, int or str]]] = {}

    def get_game_from_channel(self, channel_id: int) -> tuple:
        """
        Find game and day from a channel ID.

        Returns:
            Tuple of (game, day) or (None, None) if not found
        """
        games = database.load_games()
        for game in games.values():
            for day, channels in game.channels.items():
                if channels.get("votes_channel_id") == channel_id:
                    return game, day
                if channels.get("discussion_channel_id") == channel_id:
                    return game, day
                if game.signup_thread_id == channel_id:
                    return game, 0
        return None, None

    @app_commands.command(name="join", description="Join a CSS Solaris game")
    async def join_game(self, interaction: discord.Interaction):
        """Join a game in the current signup thread."""
        # Find game from current channel
        game, day = self.get_game_from_channel(interaction.channel.id)

        if not game:
            await interaction.response.send_message(
                "❌ This channel is not a game signup thread!",
                ephemeral=True
            )
            return

        # Check if game is in signup phase
        if game.status != GameStatus.SIGNUP:
            await interaction.response.send_message(
                "❌ This game has already started or ended!",
                ephemeral=True
            )
            return

        # Check if already joined
        if interaction.user.id in game.players:
            await interaction.response.send_message(
                "❌ You've already joined this game!",
                ephemeral=True
            )
            return

        # Add player
        game.add_player(interaction.user.id)
        database.save_game(game)

        # Update signup message
        player_list = []
        for player_id in game.players:
            user = await self.bot.fetch_user(player_id)
            player_list.append(f"• {user.mention}")

        embed = discord.Embed(
            title=f"🎮 {game.name} - Signup",
            description=f"A CSS Solaris game created by <@{game.creator_id}>!\n\n"
                       f"Use `/join` to join the game.\n"
                       f"Once enough players have joined, a moderator can use `/start {game.name}` to begin!",
            color=discord.Color.green()
        )
        embed.add_field(
            name=f"Players ({len(game.players)})",
            value="\n".join(player_list) if player_list else "None yet",
            inline=False
        )
        embed.set_footer(text=f"Game: {game.name}")

        await interaction.response.send_message(
            f"✅ {interaction.user.mention} has joined the game!",
            embed=embed
        )

    @app_commands.command(name="vote", description="Vote for a player or Abstain/Veto")
    @app_commands.describe(target="The player to vote for, or 'Abstain' or 'Veto'")
    async def vote(self, interaction: discord.Interaction, target: str):
        """Cast or update a vote."""
        # Find game from current channel
        game, day = self.get_game_from_channel(interaction.channel.id)

        if not game:
            await interaction.response.send_message(
                "❌ This channel is not a game voting channel!",
                ephemeral=True
            )
            return

        # Check if game is active
        if game.status != GameStatus.ACTIVE:
            await interaction.response.send_message(
                "❌ This game is not currently active!",
                ephemeral=True
            )
            return

        # Check if user is in the game
        if not permissions.is_player_in_game(interaction.user.id, game):
            await interaction.response.send_message(
                "❌ You are not a player in this game!",
                ephemeral=True
            )
            return

        # Check if player is alive
        if not permissions.is_player_alive(interaction.user.id, game):
            await interaction.response.send_message(
                "❌ You have been eliminated and cannot vote!",
                ephemeral=True
            )
            return

        # Parse target
        target_upper = target.upper()
        if target_upper in ["VETO", "ABSTAIN"]:
            vote_target = target_upper
        else:
            # Try to parse mention
            # Format: <@USER_ID> or <@!USER_ID>
            if target.startswith("<@") and target.endswith(">"):
                target_id_str = target[2:-1].replace("!", "")
                try:
                    vote_target = int(target_id_str)

                    # Verify target is in game and alive
                    if vote_target not in game.players:
                        await interaction.response.send_message(
                            "❌ That player is not in this game!",
                            ephemeral=True
                        )
                        return

                    if not game.is_player_alive(vote_target):
                        await interaction.response.send_message(
                            "❌ That player has been eliminated!",
                            ephemeral=True
                        )
                        return

                except ValueError:
                    await interaction.response.send_message(
                        "❌ Invalid vote target! Use @mention, 'Abstain', or 'Veto'.",
                        ephemeral=True
                    )
                    return
            else:
                await interaction.response.send_message(
                    "❌ Invalid vote target! Use @mention, 'Abstain', or 'Veto'.",
                    ephemeral=True
                )
                return

        # Initialize votes structure if needed
        if game.name not in self.votes:
            self.votes[game.name] = {}
        if day not in self.votes[game.name]:
            self.votes[game.name][day] = {}

        # Record vote
        self.votes[game.name][day][interaction.user.id] = vote_target

        # Update vote tracking message
        votes_channel_id = game.channels[day]["votes_channel_id"]
        votes_message_id = game.channels[day]["votes_message_id"]

        try:
            channel = await self.bot.fetch_channel(votes_channel_id)
            message = await channel.fetch_message(votes_message_id)

            # Get user names
            user_names = {}
            for player_id in game.get_alive_players():
                try:
                    user = await self.bot.fetch_user(player_id)
                    user_names[player_id] = user.name
                except:
                    user_names[player_id] = f"User {player_id}"

            # Format vote message
            vote_display = game_logic.format_vote_message(
                self.votes[game.name][day],
                user_names
            )

            embed = discord.Embed(
                title=f"📊 Day {day} Votes - {game.name}",
                description=vote_display,
                color=discord.Color.blue()
            )

            await message.edit(embed=embed)

            # Confirm vote
            if isinstance(vote_target, int):
                target_user = await self.bot.fetch_user(vote_target)
                await interaction.response.send_message(
                    f"✅ Your vote for {target_user.mention} has been recorded!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"✅ Your vote to **{vote_target}** has been recorded!",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to update vote: {e}",
                ephemeral=True
            )


async def setup(bot):
    """Setup function for cog."""
    await bot.add_cog(PlayerActions(bot))
