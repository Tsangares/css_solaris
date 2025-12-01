"""
Player Actions Cog
Handles /join and /vote commands.
"""

import discord
from discord import app_commands
from discord.ext import commands
from models.game import Game, GameStatus
from utils import database, permissions, game_logic
from typing import Dict, List
import random


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
            # Handle potential type mismatch (int vs string)
            if int(game.signup_thread_id) == int(channel_id):
                return game, 0
        return None, None

    @app_commands.command(name="join", description="Join a CSS Solaris game")
    async def join_game(self, interaction: discord.Interaction):
        """Join a game in the current signup thread."""
        # Find game from current channel
        game, day = self.get_game_from_channel(interaction.channel.id)

        if not game:
            # Find all games in signup phase and provide helpful information
            all_games = database.load_games()
            signup_games = [g for g in all_games.values() if g.status == GameStatus.SIGNUP]

            if len(signup_games) == 0:
                await interaction.response.send_message(
                    "❌ This channel is not a game signup thread!\n\n"
                    "There are currently no games available to join.",
                    ephemeral=True
                )
            elif len(signup_games) == 1:
                signup_game = signup_games[0]
                await interaction.response.send_message(
                    "❌ This channel is not a game signup thread!\n\n"
                    f"To join **{signup_game.name}**, use `/join` in <#{signup_game.signup_thread_id}>",
                    ephemeral=True
                )
            else:
                game_list = "\n".join([f"• **{g.name}**: <#{g.signup_thread_id}>" for g in signup_games])
                await interaction.response.send_message(
                    "❌ This channel is not a game signup thread!\n\n"
                    f"Available games to join:\n{game_list}",
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
            if player_id < 0:
                # NPC player
                npc = database.get_npc_by_id(player_id)
                if npc:
                    player_list.append(f"• 🤖 {npc.name}")
                else:
                    player_list.append(f"• 🤖 NPC {player_id}")
            else:
                # Real user
                try:
                    user = await self.bot.fetch_user(player_id)
                    player_list.append(f"• {user.mention}")
                except:
                    player_list.append(f"• <@{player_id}>")

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

    async def vote_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for vote target."""
        choices = []

        # Try to find game from current channel
        game, day = self.get_game_from_channel(interaction.channel.id)

        if game and game.status == GameStatus.ACTIVE:
            alive_players = game.get_alive_players()

            # Get player names
            player_choices = []
            for player_id in alive_players:
                if player_id < 0:
                    # NPC
                    npc = database.get_npc_by_id(player_id)
                    if npc:
                        player_choices.append(app_commands.Choice(name=f"🤖 {npc.name}", value=npc.name))
                else:
                    # Real player - we'll use their name if we can fetch it
                    try:
                        # For autocomplete, we can't await fetch_user, so we'll just use their ID
                        # The user can still use @mention which will work
                        pass  # Skip real players for autocomplete for now, they can use @mention
                    except:
                        pass

            # If <= 20 players, show all NPCs
            # If > 20, randomly sample 10
            if len(player_choices) <= 20:
                choices.extend(player_choices)
            else:
                choices.extend(random.sample(player_choices, min(10, len(player_choices))))

        # Always add Abstain and Veto options
        choices.append(app_commands.Choice(name="Abstain", value="Abstain"))
        choices.append(app_commands.Choice(name="Veto", value="Veto"))

        # Filter based on what user is currently typing
        if current:
            choices = [c for c in choices if current.lower() in c.name.lower()]

        return choices[:25]  # Discord limit is 25 choices

    @app_commands.command(name="vote", description="Vote for a player or Abstain/Veto")
    @app_commands.describe(target="The player to vote for, or 'Abstain' or 'Veto'")
    @app_commands.autocomplete(target=vote_autocomplete)
    async def vote(self, interaction: discord.Interaction, target: str):
        """Cast or update a vote."""
        # Find game from current channel
        game, day = self.get_game_from_channel(interaction.channel.id)

        if not game:
            await interaction.response.send_message(
                "❌ This channel is not a game channel! Use `/vote` in the discussion or votes thread.",
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

        # Defer immediately to avoid timeout (vote processing can be slow)
        await interaction.response.defer(ephemeral=True)

        # Parse target
        target_upper = target.upper()
        if target_upper in ["VETO", "ABSTAIN"]:
            vote_target = target_upper
        else:
            vote_target = None

            # Try to parse mention first
            # Format: <@USER_ID> or <@!USER_ID>
            if target.startswith("<@") and target.endswith(">"):
                target_id_str = target[2:-1].replace("!", "")
                try:
                    vote_target = int(target_id_str)

                    # Verify target is in game and alive
                    if vote_target not in game.players:
                        await interaction.followup.send(
                            "❌ That player is not in this game!",
                            ephemeral=True
                        )
                        return

                    if not game.is_player_alive(vote_target):
                        await interaction.followup.send(
                            "❌ That player has been eliminated!",
                            ephemeral=True
                        )
                        return

                except ValueError:
                    pass  # Not a valid mention, will try NPC name next

            # If not a mention, try NPC name
            if vote_target is None:
                npc = database.get_npc(target)
                if npc and npc.id in game.players and game.is_player_alive(npc.id):
                    vote_target = npc.id
                else:
                    await interaction.followup.send(
                        "❌ Invalid vote target! Use @mention, NPC name, 'Abstain', or 'Veto'.",
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

            # Get user/NPC names
            user_names = {}
            for player_id in game.get_alive_players():
                if player_id < 0:
                    # NPC
                    npc = database.get_npc_by_id(player_id)
                    if npc:
                        user_names[player_id] = f"🤖 {npc.name}"
                    else:
                        user_names[player_id] = f"🤖 NPC {player_id}"
                else:
                    # Real user
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

            # Send public confirmation in discussion channel (if not in votes channel)
            if interaction.channel.id != votes_channel_id:
                votes_thread = await self.bot.fetch_channel(votes_channel_id)
                await interaction.channel.send(
                    f"🗳️ {interaction.user.mention} has cast their vote! "
                    f"(Vote tally: {votes_thread.mention})"
                )

            # Confirm vote privately to user
            if isinstance(vote_target, int):
                # Check if it's an NPC or real player
                if vote_target < 0:
                    target_npc = database.get_npc_by_id(vote_target)
                    if target_npc:
                        await interaction.followup.send(
                            f"✅ Your vote for 🤖 **{target_npc.name}** has been recorded!",
                            ephemeral=True
                        )
                    else:
                        await interaction.followup.send(
                            f"✅ Your vote has been recorded!",
                            ephemeral=True
                        )
                else:
                    target_user = await self.bot.fetch_user(vote_target)
                    await interaction.followup.send(
                        f"✅ Your vote for {target_user.mention} has been recorded!",
                        ephemeral=True
                    )
            else:
                await interaction.followup.send(
                    f"✅ Your vote to **{vote_target}** has been recorded!",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to update vote: {e}",
                ephemeral=True
            )

    @app_commands.command(name="players", description="List all players in the current game")
    async def list_players(self, interaction: discord.Interaction):
        """List all players in the current game with their status."""
        # Find game from current channel
        game, day = self.get_game_from_channel(interaction.channel.id)

        if not game:
            await interaction.response.send_message(
                "❌ This channel is not a game channel! Use this command in a game thread.",
                ephemeral=True
            )
            return

        # Build player list
        alive_players = []
        eliminated_players = []

        for player_id in game.players:
            is_alive = game.is_player_alive(player_id)

            if player_id < 0:
                # NPC
                npc = database.get_npc_by_id(player_id)
                if npc:
                    player_name = f"🤖 {npc.name}"
                else:
                    player_name = f"🤖 NPC {player_id}"
            else:
                # Real user
                try:
                    user = await self.bot.fetch_user(player_id)
                    player_name = user.mention
                except:
                    player_name = f"<@{player_id}>"

            if is_alive:
                alive_players.append(player_name)
            else:
                eliminated_players.append(player_name)

        # Build embed
        embed = discord.Embed(
            title=f"👥 Players - {game.name}",
            color=discord.Color.blue()
        )

        if game.status == GameStatus.SIGNUP:
            embed.description = "Game is in signup phase"
            embed.add_field(
                name=f"Signed Up ({len(game.players)})",
                value="\n".join(alive_players) if alive_players else "None yet",
                inline=False
            )
        elif game.status == GameStatus.ACTIVE:
            embed.description = f"Day {game.current_day}"
            embed.add_field(
                name=f"✅ Alive ({len(alive_players)})",
                value="\n".join(alive_players) if alive_players else "None",
                inline=False
            )
            if eliminated_players:
                embed.add_field(
                    name=f"💀 Eliminated ({len(eliminated_players)})",
                    value="\n".join(eliminated_players),
                    inline=False
                )
        else:
            embed.description = "Game has ended"
            embed.add_field(
                name=f"All Players ({len(game.players)})",
                value="\n".join(alive_players + eliminated_players),
                inline=False
            )

        embed.set_footer(text=f"Game: {game.name}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    """Setup function for cog."""
    await bot.add_cog(PlayerActions(bot))
