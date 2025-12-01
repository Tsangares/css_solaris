"""
NPC Commands Cog
Handles NPC management for all users.
"""

import discord
from discord import app_commands
from discord.ext import commands
from models.game import GameStatus
from models.npc import NPC
from utils import database, permissions
from typing import Dict


class NPCCommands(commands.Cog):
    """Cog for NPC commands available to all users."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="npc_create", description="Create an NPC player for testing")
    @app_commands.describe(
        name="Name of the NPC",
        persona="Character personality/description (e.g., 'Aggressive and suspicious')"
    )
    async def create_npc(self, interaction: discord.Interaction, name: str, persona: str):
        """Create a new NPC player."""

        # Check if NPC already exists
        if database.npc_exists(name):
            await interaction.response.send_message(
                f"❌ An NPC named '{name}' already exists!",
                ephemeral=True
            )
            return

        # Create NPC
        npc = NPC(name=name, profile=persona)
        database.save_npc(npc)

        embed = discord.Embed(
            title=f"🤖 NPC Created: {name}",
            description=f"**Persona:** {npc.profile}\n**ID:** {npc.id}",
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="npc_list", description="List all NPCs")
    async def list_npcs(self, interaction: discord.Interaction):
        """List all NPCs."""

        npcs = database.load_npcs()

        if not npcs:
            await interaction.response.send_message(
                "📋 No NPCs have been created yet.",
                ephemeral=True
            )
            return

        # Build NPC list
        npc_list = []
        for npc in npcs.values():
            npc_list.append(f"**{npc.name}** (ID: {npc.id})\n└ *Persona:* {npc.profile}")

        embed = discord.Embed(
            title="🤖 NPCs",
            description="\n\n".join(npc_list),
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def npc_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for NPC name."""
        npcs = database.load_npcs()
        choices = []

        for npc in npcs.values():
            # Show all NPCs if nothing typed yet, otherwise filter
            if not current or current.lower() in npc.name.lower():
                choices.append(app_commands.Choice(name=f"🤖 {npc.name}", value=npc.name))

        return choices[:25]  # Discord limit

    async def npc_delete_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for NPC deletion."""
        npcs = database.load_npcs()
        choices = []

        for npc in npcs.values():
            if current.lower() in npc.name.lower():
                choices.append(app_commands.Choice(name=f"🤖 {npc.name}", value=npc.name))

        return choices[:25]  # Discord limit

    async def npc_vote_target_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for vote target (same as regular /vote)."""
        choices = []

        # Get the player_actions cog to access get_game_from_channel
        player_actions_cog = self.bot.get_cog("PlayerActions")
        if not player_actions_cog:
            return choices

        # Try to find game from current channel
        game, day = player_actions_cog.get_game_from_channel(interaction.channel.id)

        if game and game.status == GameStatus.ACTIVE:
            alive_players = game.get_alive_players()

            # Get player names
            import random
            player_choices = []
            for player_id in alive_players:
                if player_id < 0:
                    # NPC
                    npc = database.get_npc_by_id(player_id)
                    if npc:
                        player_choices.append(app_commands.Choice(name=f"🤖 {npc.name}", value=npc.name))
                else:
                    # Real player - skip for autocomplete, they can use @mention
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

        return choices[:25]  # Discord limit

    @app_commands.command(name="npc_delete", description="Delete an NPC")
    @app_commands.describe(name="Name of the NPC to delete")
    @app_commands.autocomplete(name=npc_delete_autocomplete)
    async def delete_npc(self, interaction: discord.Interaction, name: str):
        """Delete an NPC."""

        # Check if NPC exists
        npc = database.get_npc(name)
        if not npc:
            await interaction.response.send_message(
                f"❌ NPC '{name}' not found!",
                ephemeral=True
            )
            return

        # Remove NPC from any games they're in
        games = database.load_games()
        for game in games.values():
            if npc.id in game.players:
                game.remove_player(npc.id)
                database.save_game(game)

        # Delete NPC
        database.delete_npc(name)

        await interaction.response.send_message(
            f"✅ NPC '{name}' has been deleted!",
            ephemeral=True
        )

    @app_commands.command(name="npc_join", description="Make an NPC join a game")
    @app_commands.describe(npc_name="Name of the NPC")
    @app_commands.autocomplete(npc_name=npc_name_autocomplete)
    async def npc_join(self, interaction: discord.Interaction, npc_name: str):
        """Make an NPC join a game (use in the game's signup thread)."""

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
            # Debug: show what channel ID we're checking
            all_games = database.load_games()
            game_info = []
            for g in all_games.values():
                if g.status == GameStatus.SIGNUP:
                    game_info.append(f"• **{g.name}**: Thread ID {g.signup_thread_id}")

            debug_msg = f"❌ This channel is not a game signup thread!\n\n"
            debug_msg += f"Current channel ID: {interaction.channel.id}\n\n"
            if game_info:
                debug_msg += "Available signup threads:\n" + "\n".join(game_info)
            else:
                debug_msg += "No games in signup phase."

            await interaction.response.send_message(debug_msg, ephemeral=True)
            return

        # Check if game is in signup phase
        if game.status != GameStatus.SIGNUP:
            await interaction.response.send_message(
                f"❌ Game '{game_name}' has already started or ended!",
                ephemeral=True
            )
            return

        # Check if NPC exists
        npc = database.get_npc(npc_name)
        if not npc:
            await interaction.response.send_message(
                f"❌ NPC '{npc_name}' not found!",
                ephemeral=True
            )
            return

        # Check if already joined
        if npc.id in game.players:
            await interaction.response.send_message(
                f"❌ NPC '{npc_name}' has already joined this game!",
                ephemeral=True
            )
            return

        # Add NPC to game
        game.add_player(npc.id)
        database.save_game(game)

        # Update signup message in the signup thread
        try:
            channel = await self.bot.fetch_channel(game.signup_thread_id)

            # Build player list
            player_list = []
            for player_id in game.players:
                if player_id < 0:
                    # NPC
                    player_npc = database.get_npc_by_id(player_id)
                    if player_npc:
                        player_list.append(f"• 🤖 {player_npc.name}")
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

            await channel.send(
                f"✅ 🤖 **{npc.name}** (NPC) has joined the game!",
                embed=embed
            )

            await interaction.response.send_message(
                f"✅ NPC '{npc_name}' joined game '{game.name}'!",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"⚠️ NPC joined but failed to update signup message: {e}",
                ephemeral=True
            )

    @app_commands.command(name="npc_vote", description="Make an NPC cast a vote")
    @app_commands.describe(
        npc_name="Name of the NPC",
        target="The player to vote for, or 'Abstain' or 'Veto'"
    )
    @app_commands.autocomplete(npc_name=npc_name_autocomplete, target=npc_vote_target_autocomplete)
    async def npc_vote(self, interaction: discord.Interaction, npc_name: str, target: str):
        """Make an NPC cast a vote (use in discussion or votes channel)."""

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
                "❌ This channel is not a game channel! Use this command in the discussion or votes thread.",
                ephemeral=True
            )
            return

        # Check if game is active
        if game.status != GameStatus.ACTIVE:
            await interaction.response.send_message(
                f"❌ Game '{game.name}' is not currently active!",
                ephemeral=True
            )
            return

        # Check if NPC exists
        npc = database.get_npc(npc_name)
        if not npc:
            await interaction.response.send_message(
                f"❌ NPC '{npc_name}' not found!",
                ephemeral=True
            )
            return

        # Check if NPC is in the game
        if npc.id not in game.players:
            await interaction.response.send_message(
                f"❌ NPC '{npc_name}' is not in this game!",
                ephemeral=True
            )
            return

        # Check if NPC is alive
        if not game.is_player_alive(npc.id):
            await interaction.response.send_message(
                f"❌ NPC '{npc_name}' has been eliminated!",
                ephemeral=True
            )
            return

        # Parse target
        target_upper = target.upper()
        if target_upper in ["VETO", "ABSTAIN"]:
            vote_target = target_upper
            target_display = f"**{vote_target}**"
        else:
            # Try to parse mention or NPC name
            vote_target = None
            target_display = None

            # Check if it's a mention
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

                    # Get display name
                    if vote_target < 0:
                        target_npc = database.get_npc_by_id(vote_target)
                        target_display = f"🤖 **{target_npc.name}**" if target_npc else f"NPC {vote_target}"
                    else:
                        try:
                            user = await self.bot.fetch_user(vote_target)
                            target_display = user.mention
                        except:
                            target_display = f"<@{vote_target}>"
                except ValueError:
                    pass

            # If not a mention, check if it's an NPC name
            if vote_target is None:
                target_npc = database.get_npc(target)
                if target_npc and target_npc.id in game.players and game.is_player_alive(target_npc.id):
                    vote_target = target_npc.id
                    target_display = f"🤖 **{target_npc.name}**"

            if vote_target is None:
                await interaction.response.send_message(
                    "❌ Invalid vote target! Use @mention, NPC name, 'Abstain', or 'Veto'.",
                    ephemeral=True
                )
                return

        # Import game_logic for vote formatting
        from utils import game_logic

        # day was retrieved earlier from get_game_from_channel
        # Initialize votes structure if needed
        if game.name not in player_actions_cog.votes:
            player_actions_cog.votes[game.name] = {}
        if day not in player_actions_cog.votes[game.name]:
            player_actions_cog.votes[game.name][day] = {}

        # Record vote
        player_actions_cog.votes[game.name][day][npc.id] = vote_target

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
                    player_npc = database.get_npc_by_id(player_id)
                    if player_npc:
                        user_names[player_id] = f"🤖 {player_npc.name}"
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
            vote_display_text = game_logic.format_vote_message(
                player_actions_cog.votes[game.name][day],
                user_names
            )

            embed = discord.Embed(
                title=f"📊 Day {day} Votes - {game.name}",
                description=vote_display_text,
                color=discord.Color.blue()
            )

            await message.edit(embed=embed)

            # Send public confirmation in discussion channel (if not in votes channel)
            if interaction.channel.id != votes_channel_id:
                await interaction.channel.send(
                    f"🗳️ 🤖 **{npc.name}** has cast their vote! "
                    f"(Vote tally: {channel.mention})"
                )

            # Confirm vote
            await interaction.response.send_message(
                f"✅ NPC '{npc_name}' voted for {target_display}!",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to update vote: {e}",
                ephemeral=True
            )

    @app_commands.command(name="npc_say", description="Make an NPC send a message")
    @app_commands.describe(
        npc_name="Name of the NPC",
        message="What the NPC should say"
    )
    @app_commands.autocomplete(npc_name=npc_name_autocomplete)
    async def npc_say(self, interaction: discord.Interaction, npc_name: str, message: str):
        """Make an NPC speak in the current channel."""

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
                "❌ This channel is not a game channel! Use this command in a discussion thread.",
                ephemeral=True
            )
            return

        # Check if NPC exists
        npc = database.get_npc(npc_name)
        if not npc:
            await interaction.response.send_message(
                f"❌ NPC '{npc_name}' not found!",
                ephemeral=True
            )
            return

        # Check if NPC is in the game
        if npc.id not in game.players:
            await interaction.response.send_message(
                f"❌ NPC '{npc_name}' is not in this game!",
                ephemeral=True
            )
            return

        # Check if NPC is alive
        if not game.is_player_alive(npc.id):
            await interaction.response.send_message(
                f"❌ NPC '{npc_name}' has been eliminated!",
                ephemeral=True
            )
            return

        # Format and send the message
        formatted_message = f"**🤖 {npc.name}** (*{npc.profile}*): {message}"

        # Acknowledge the command (ephemeral so only mod sees it)
        await interaction.response.send_message(
            f"✅ Sending message as {npc.name}...",
            ephemeral=True
        )

        # Send the NPC's message to the channel
        await interaction.channel.send(formatted_message)


async def setup(bot):
    """Setup function for cog."""
    await bot.add_cog(NPCCommands(bot))
