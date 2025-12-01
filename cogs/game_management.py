"""
Game Management Cog
Handles /new_game and /start commands.
"""

import discord
from discord import app_commands
from discord.ext import commands
from models.game import Game, GameStatus
from utils import database, permissions, forum_manager


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

        # Defer as this might take a moment
        await interaction.response.defer()

        try:
            # Get or create the lobby forum
            lobby_forum = await forum_manager.get_or_create_lobby_forum(interaction.guild)

            # Create signup embed
            embed = discord.Embed(
                title=f"🎮 {name} - Signup",
                description=f"A new CSS Solaris game created by {interaction.user.mention}!\n\n"
                           f"Use `/join` in this thread to join the game.\n"
                           f"Once enough players have joined, a moderator can use `/start {name}` to begin!",
                color=discord.Color.green()
            )
            embed.add_field(name="Players", value="None yet", inline=False)
            embed.set_footer(text=f"Game: {name}")

            # Create forum post in lobby
            signup_thread = await lobby_forum.create_thread(
                name=f"🎮 {name}",
                content=f"**{name}** - Sign up below!",
                embed=embed
            )

            # Create the game in database
            game = Game(
                name=name,
                creator_id=interaction.user.id,
                signup_thread_id=signup_thread.thread.id  # Forum posts create a thread
            )
            database.save_game(game)

            # Send confirmation
            await interaction.followup.send(
                f"✅ Game **{name}** created! Players can sign up in {signup_thread.thread.mention}",
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to create game: {e}",
            )

    @app_commands.command(name="start", description="Start a CSS Solaris game (Moderator only)")
    async def start_game(self, interaction: discord.Interaction):
        """Start a game and create Day 1 channels (use in the signup thread)."""
        # Get the player_actions cog to access get_game_from_channel
        player_actions_cog = self.bot.get_cog("PlayerActions")
        if not player_actions_cog:
            await interaction.response.send_message(
                "❌ PlayerActions cog not loaded!",
                ephemeral=True
            )
            return

        # Find game from current channel
        game, day = player_actions_cog.get_game_from_channel(interaction.channel.id)

        if not game:
            await interaction.response.send_message(
                "❌ This channel is not a game signup thread! Use this command in the signup thread.",
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
            guild = interaction.guild

            # Get moderator role and bot member for permissions
            mod_role = discord.utils.get(guild.roles, name=permissions.MODERATOR_ROLE_NAME)
            bot_member = guild.get_member(self.bot.user.id)

            # Get or create game forums
            discussions_forum, voting_forum = await forum_manager.get_or_create_game_forums(
                guild,
                mod_role=mod_role,
                bot_member=bot_member
            )

            # Create Day 1 discussion thread
            discussion_embed = discord.Embed(
                title=f"💬 {name} - Day 1 Discussion",
                description=f"Discuss and strategize here!",
                color=discord.Color.blue()
            )

            discussion_thread = await discussions_forum.create_thread(
                name=f"💬 {name} - Day 1",
                content=f"**Day 1 Discussion for {name}**",
                embed=discussion_embed
            )

            # Create Day 1 voting thread with vote tracking embed
            vote_embed = discord.Embed(
                title=f"📊 Day 1 Votes - {name}",
                description="No votes yet. Use `/vote @player` or `/vote Abstain` or `/vote Veto`",
                color=discord.Color.blue()
            )

            voting_thread = await voting_forum.create_thread(
                name=f"🗳️ {name} - Day 1",
                content=f"**Day 1 Voting for {name}**",
                embed=vote_embed
            )

            # The first message is the one we just created with the embed
            vote_message = voting_thread.message

            # Update game state
            game.start_game()
            game.channels[1] = {
                "votes_channel_id": voting_thread.thread.id,
                "discussion_channel_id": discussion_thread.thread.id,
                "votes_message_id": vote_message.id
            }

            # Assign roles (for now, all players are villagers)
            for player_id in game.players:
                game.roles[player_id] = "villager"

            database.save_game(game)

            # Send announcement
            player_mentions = []
            for player_id in game.players:
                if player_id < 0:
                    # NPC
                    npc = database.get_npc_by_id(player_id)
                    if npc:
                        player_mentions.append(f"🤖 {npc.name}")
                    else:
                        player_mentions.append(f"🤖 NPC {player_id}")
                else:
                    # Real user
                    player_mentions.append(f"<@{player_id}>")

            # Game description
            game_description = (
                "**🎭 About CSS Solaris**\n"
                "CSS Solaris is a social deduction game where players must work together to eliminate threats "
                "while hidden adversaries work against them. Use discussion, voting, and deduction to survive!\n\n"
                "**📜 How to Play:**\n"
                "• Discuss with other players to find suspicious behavior\n"
                "• Use `/vote @player` to vote someone out (or `/vote Abstain` to skip elimination)\n"
                "• Players with the most votes are eliminated at day's end\n"
                "• Work together to identify and eliminate all threats!\n\n"
            )

            # Announcement for players (don't mention hidden votes channel)
            player_announcement = discord.Embed(
                title=f"🌅 {name} - Day 1 Begins!",
                description=game_description +
                           f"**Players ({len(game.players)}):**\n" + ", ".join(player_mentions) + "\n\n"
                           f"**Discussion Thread:** {discussion_thread.thread.mention}\n"
                           f"Discuss and use `/vote @player` (or `/vote Abstain` or `/vote Veto`) here!\n\n"
                           f"Good luck!",
                color=discord.Color.gold()
            )

            # Announcement for mods (includes votes channel)
            mod_announcement = discord.Embed(
                title=f"🌅 {name} - Day 1 Begins!",
                description=f"The game has started!\n\n"
                           f"**Players ({len(game.players)}):**\n" + ", ".join(player_mentions) + "\n\n"
                           f"**Threads:**\n"
                           f"💬 {discussion_thread.thread.mention} - Discussion and voting\n"
                           f"🗳️ {voting_thread.thread.mention} - Vote tracking (hidden from players)\n\n"
                           f"Good luck!",
                color=discord.Color.gold()
            )

            await interaction.followup.send(embed=player_announcement)
            await voting_thread.thread.send(embed=mod_announcement)
            await discussion_thread.thread.send(embed=player_announcement)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to start game: {e}")


async def setup(bot):
    """Setup function for cog."""
    await bot.add_cog(GameManagement(bot))
