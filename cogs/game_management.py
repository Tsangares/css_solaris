"""
Game Management Cog
Handles /new_game and /start commands.
"""

import discord
from discord import app_commands
from discord.ext import commands
from models.game import Game, GameStatus
from utils import database, permissions


class GameManagement(commands.Cog):
    """Cog for game creation and starting."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="new_game", description="Create a new CSS Solaris game")
    @app_commands.describe(name="The name of your game")
    async def new_game(self, interaction: discord.Interaction, name: str):
        """Create a new game and open signups."""
        # Check if game already exists
        if database.game_exists(name):
            await interaction.response.send_message(
                f"❌ A game named '{name}' already exists!",
                ephemeral=True
            )
            return

        # Create a thread/post for signups
        # For now, we'll use the current channel as the signup location
        # In production, this should create a forum post in a designated channel
        try:
            # Create the game in database
            game = Game(
                name=name,
                creator_id=interaction.user.id,
                signup_thread_id=interaction.channel.id
            )
            database.save_game(game)

            # Send confirmation
            embed = discord.Embed(
                title=f"🎮 {name} - Signup",
                description=f"A new CSS Solaris game has been created by {interaction.user.mention}!\n\n"
                           f"Use `/join` to join the game.\n"
                           f"Once enough players have joined, a moderator can use `/start {name}` to begin!",
                color=discord.Color.green()
            )
            embed.add_field(name="Players", value="None yet", inline=False)
            embed.set_footer(text=f"Game: {name}")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to create game: {e}",
                ephemeral=True
            )

    @app_commands.command(name="start", description="Start a CSS Solaris game (Moderator only)")
    @app_commands.describe(name="The name of the game to start")
    async def start_game(self, interaction: discord.Interaction, name: str):
        """Start a game and create Day 1 channels."""
        # Load game
        game = database.get_game(name)
        if not game:
            await interaction.response.send_message(
                f"❌ No game named '{name}' found!",
                ephemeral=True
            )
            return

        # Check permissions
        if not permissions.can_manage_game(interaction.user.id, interaction.user, game):
            await interaction.response.send_message(
                "❌ You don't have permission to start this game!",
                ephemeral=True
            )
            return

        # Check if game is in signup status
        if game.status != GameStatus.SIGNUP:
            await interaction.response.send_message(
                f"❌ Game '{name}' has already started or ended!",
                ephemeral=True
            )
            return

        # Check minimum players
        if len(game.players) < 3:
            await interaction.response.send_message(
                f"❌ Need at least 3 players to start! Currently have {len(game.players)}.",
                ephemeral=True
            )
            return

        # Defer response as this might take a moment
        await interaction.response.defer()

        try:
            # Create forum channels for Day 1
            # Note: In production, these should be forum posts in a designated forum channel
            # For now, we'll create regular text channels
            guild = interaction.guild
            category_name = f"CSS Solaris: {name}"

            # Create or find category
            category = discord.utils.get(guild.categories, name=category_name)
            if not category:
                category = await guild.create_category(category_name)

            # Create Day 1 channels
            votes_channel = await guild.create_text_channel(
                f"{name}-day-1-votes",
                category=category,
                topic=f"Day 1 voting for {name}"
            )

            discussion_channel = await guild.create_text_channel(
                f"{name}-day-1-discussion",
                category=category,
                topic=f"Day 1 discussion for {name}"
            )

            # Create initial vote tracking message
            vote_embed = discord.Embed(
                title=f"📊 Day 1 Votes - {name}",
                description="No votes yet. Use `/vote @player` or `/vote Abstain` or `/vote Veto`",
                color=discord.Color.blue()
            )
            vote_message = await votes_channel.send(embed=vote_embed)

            # Update game state
            game.start_game()
            game.channels[1] = {
                "votes_channel_id": votes_channel.id,
                "discussion_channel_id": discussion_channel.id,
                "votes_message_id": vote_message.id
            }

            # Assign roles (for now, all players are villagers)
            for player_id in game.players:
                game.roles[player_id] = "villager"

            database.save_game(game)

            # Send announcement
            player_mentions = [f"<@{player_id}>" for player_id in game.players]
            announcement = discord.Embed(
                title=f"🌅 {name} - Day 1 Begins!",
                description=f"The game has started!\n\n"
                           f"**Players ({len(game.players)}):**\n" + ", ".join(player_mentions) + "\n\n"
                           f"**Channels:**\n"
                           f"🗳️ {votes_channel.mention} - Cast your votes here\n"
                           f"💬 {discussion_channel.mention} - Discuss here\n\n"
                           f"Good luck!",
                color=discord.Color.gold()
            )

            await interaction.followup.send(embed=announcement)
            await votes_channel.send(embed=announcement)
            await discussion_channel.send(embed=announcement)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to start game: {e}")


async def setup(bot):
    """Setup function for cog."""
    await bot.add_cog(GameManagement(bot))
