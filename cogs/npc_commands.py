"""
NPC Commands Cog
Handles NPC management via /npc subcommands.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import List
from models.game import GameStatus
from models.npc import NPC
from utils import database, permissions, game_logic


class NPCCommands(commands.GroupCog, group_name="npc"):
    """NPC management commands: /npc create, /npc list, /npc delete, /npc join, /npc vote"""

    def __init__(self, bot):
        self.bot = bot

    # --- Autocomplete helpers ---

    async def npc_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        npcs = database.load_npcs()
        choices = []
        for npc in npcs.values():
            if not current or current.lower() in npc.name.lower():
                choices.append(app_commands.Choice(name=f"🤖 {npc.name}", value=npc.name))
        return choices[:25]

    async def vote_target_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        choices = []
        player_actions_cog = self.bot.get_cog("PlayerActions")
        if not player_actions_cog:
            return choices

        game, day = player_actions_cog.get_game_from_channel(interaction.channel.id)
        if game and game.status == GameStatus.ACTIVE:
            for player_id in game.get_alive_players():
                if player_id < 0:
                    npc = database.get_npc_by_id(player_id)
                    if npc:
                        choices.append(app_commands.Choice(name=f"🤖 {npc.name}", value=npc.name))
                else:
                    member = interaction.guild.get_member(player_id)
                    if member:
                        choices.append(app_commands.Choice(name=member.display_name, value=f"<@{player_id}>"))

        import random
        random.shuffle(choices)
        choices.append(app_commands.Choice(name="Abstain", value="Abstain"))

        if current:
            choices = [c for c in choices if current.lower() in c.name.lower()]
        return choices[:25]

    # --- /npc create ---

    @app_commands.command(name="create", description="Create a new NPC")
    @app_commands.describe(name="Name of the NPC", persona="Character personality/description")
    async def create(self, interaction: discord.Interaction, name: str, persona: str):
        if database.npc_exists(name):
            await interaction.response.send_message(f"❌ An NPC named '{name}' already exists!", ephemeral=True)
            return

        npc = NPC(name=name, profile=persona)
        database.save_npc(npc)

        embed = discord.Embed(
            title=f"🤖 NPC Created: {name}",
            description=f"**Persona:** {npc.profile}\n**ID:** {npc.id}",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

    # --- /npc list ---

    @app_commands.command(name="list", description="List all NPCs")
    async def list_npcs(self, interaction: discord.Interaction):
        npcs = database.load_npcs()
        if not npcs:
            await interaction.response.send_message("📋 No NPCs have been created yet.", ephemeral=True)
            return

        npc_list = [f"**{npc.name}** (ID: {npc.id})\n└ *{npc.profile}*" for npc in npcs.values()]
        embed = discord.Embed(title="🤖 NPCs", description="\n\n".join(npc_list), color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- /npc delete ---

    @app_commands.command(name="delete", description="Delete an NPC")
    @app_commands.describe(name="Name of the NPC to delete")
    @app_commands.autocomplete(name=npc_name_autocomplete)
    async def delete(self, interaction: discord.Interaction, name: str):
        npc = database.get_npc(name)
        if not npc:
            await interaction.response.send_message(f"❌ NPC '{name}' not found!", ephemeral=True)
            return

        games = database.load_games()
        for game in games.values():
            if npc.id in game.players:
                game.remove_player(npc.id)
                database.save_game(game)

        database.delete_npc(name)
        await interaction.response.send_message(f"✅ NPC '{name}' has been deleted!", ephemeral=True)

    # --- /npc join ---

    @app_commands.command(name="join", description="Make an NPC join a game (use in signup thread)")
    @app_commands.describe(npc_name="Name of the NPC")
    @app_commands.autocomplete(npc_name=npc_name_autocomplete)
    async def join(self, interaction: discord.Interaction, npc_name: str):
        player_actions_cog = self.bot.get_cog("PlayerActions")
        if not player_actions_cog:
            await interaction.response.send_message("❌ PlayerActions cog not loaded!", ephemeral=True)
            return

        game, day = player_actions_cog.get_game_from_channel(interaction.channel.id)

        if not game:
            all_games = database.load_games()
            signup_games = [g for g in all_games.values() if g.status == GameStatus.SIGNUP]
            if signup_games:
                game_list = "\n".join(f"• **{g.name}**: <#{g.signup_thread_id}>" for g in signup_games)
                await interaction.response.send_message(
                    f"❌ Use this in a signup thread!\n\nAvailable games:\n{game_list}", ephemeral=True)
            else:
                await interaction.response.send_message("❌ No games in signup phase.", ephemeral=True)
            return

        if game.status != GameStatus.SIGNUP:
            await interaction.response.send_message(f"❌ Game '{game.name}' has already started or ended!", ephemeral=True)
            return

        npc = database.get_npc(npc_name)
        if not npc:
            await interaction.response.send_message(f"❌ NPC '{npc_name}' not found!", ephemeral=True)
            return

        if npc.id in game.players:
            await interaction.response.send_message(f"❌ NPC '{npc_name}' has already joined this game!", ephemeral=True)
            return

        game.add_player(npc.id)
        database.save_game(game)

        try:
            channel = await self.bot.fetch_channel(game.signup_thread_id)

            player_list = []
            for player_id in game.players:
                if player_id < 0:
                    player_npc = database.get_npc_by_id(player_id)
                    player_list.append(f"• 🤖 {player_npc.name}" if player_npc else f"• 🤖 NPC {player_id}")
                else:
                    player_list.append(f"• <@{player_id}>")

            embed = discord.Embed(
                title=f"🎮 {game.name} - Signup",
                description=f"A CSS Solaris game created by <@{game.creator_id}>!\n\n"
                           f"Use `/join` to join the game.",
                color=discord.Color.green()
            )
            embed.add_field(name=f"Players ({len(game.players)})", value="\n".join(player_list) or "None yet", inline=False)
            embed.set_footer(text=f"Game: {game.name}")

            await channel.send(f"✅ 🤖 **{npc.name}** (NPC) has joined the game!", embed=embed)
            await interaction.response.send_message(f"✅ NPC '{npc_name}' joined game '{game.name}'!", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"⚠️ NPC joined but failed to update signup message: {e}", ephemeral=True)

    # --- /npc vote ---

    @app_commands.command(name="vote", description="Make an NPC cast a vote")
    @app_commands.describe(npc_name="Name of the NPC", target="Player to vote for, or 'Abstain'")
    @app_commands.autocomplete(npc_name=npc_name_autocomplete, target=vote_target_autocomplete)
    async def vote(self, interaction: discord.Interaction, npc_name: str, target: str):
        await interaction.response.defer(ephemeral=True)

        player_actions_cog = self.bot.get_cog("PlayerActions")
        if not player_actions_cog:
            await interaction.followup.send("❌ PlayerActions cog not loaded!", ephemeral=True)
            return

        game, day = player_actions_cog.get_game_from_channel(interaction.channel.id)

        if not game:
            await interaction.followup.send("❌ Use this in a game discussion or votes thread.", ephemeral=True)
            return

        if day == 0 or day is None:
            if game.current_day in game.channels:
                disc_id = game.channels[game.current_day].get('discussion_channel_id')
                if disc_id:
                    await interaction.followup.send(f"❌ Use `/npc vote` in the discussion thread: <#{disc_id}>", ephemeral=True)
                    return
            await interaction.followup.send(f"❌ Could not find discussion thread for Day {game.current_day}!", ephemeral=True)
            return

        if game.status != GameStatus.ACTIVE:
            await interaction.followup.send(f"❌ Game '{game.name}' is not active!", ephemeral=True)
            return

        npc = database.get_npc(npc_name)
        if not npc:
            await interaction.followup.send(f"❌ NPC '{npc_name}' not found!", ephemeral=True)
            return
        if npc.id not in game.players:
            await interaction.followup.send(f"❌ NPC '{npc_name}' is not in this game!", ephemeral=True)
            return
        if not game.is_player_alive(npc.id):
            await interaction.followup.send(f"❌ NPC '{npc_name}' has been eliminated!", ephemeral=True)
            return

        # Parse target
        target_upper = target.upper()
        if target_upper == "ABSTAIN":
            vote_target = target_upper
            target_display = f"**{vote_target}**"
        else:
            vote_target = None
            target_display = None

            if target.startswith("<@") and target.endswith(">"):
                target_id_str = target[2:-1].replace("!", "")
                try:
                    vote_target = int(target_id_str)
                    if vote_target not in game.players:
                        await interaction.followup.send("❌ That player is not in this game!", ephemeral=True)
                        return
                    if not game.is_player_alive(vote_target):
                        await interaction.followup.send("❌ That player has been eliminated!", ephemeral=True)
                        return
                    if vote_target < 0:
                        t_npc = database.get_npc_by_id(vote_target)
                        target_display = f"🤖 **{t_npc.name}**" if t_npc else f"NPC {vote_target}"
                    else:
                        member = interaction.guild.get_member(vote_target)
                        target_display = member.mention if member else f"<@{vote_target}>"
                except ValueError:
                    pass

            if vote_target is None:
                target_npc = database.get_npc(target)
                if target_npc and target_npc.id in game.players and game.is_player_alive(target_npc.id):
                    vote_target = target_npc.id
                    target_display = f"🤖 **{target_npc.name}**"

            if vote_target is None:
                await interaction.followup.send("❌ Invalid target! Use @mention, NPC name, 'Abstain'.", ephemeral=True)
                return

        # Record vote and persist
        if day not in game.votes:
            game.votes[day] = {}
        game.votes[day][npc.id] = vote_target
        database.save_game(game)

        # Update vote tracking message
        if day not in game.channels:
            await interaction.followup.send("❌ Could not find channel data for this day!", ephemeral=True)
            return

        try:
            votes_channel_id = game.channels[day]["votes_channel_id"]
            votes_message_id = game.channels[day]["votes_message_id"]
            channel = await self.bot.fetch_channel(votes_channel_id)
            message = await channel.fetch_message(votes_message_id)

            user_names = {}
            for player_id in game.players:
                if player_id < 0:
                    p_npc = database.get_npc_by_id(player_id)
                    user_names[player_id] = f"🤖 {p_npc.name}" if p_npc else f"🤖 NPC {player_id}"
                else:
                    member = interaction.guild.get_member(player_id)
                    user_names[player_id] = member.display_name if member else f"User {player_id}"

            vote_display_text = game_logic.format_vote_message(game.votes.get(day, {}), user_names, game.get_alive_players())
            disc_channel_id = game.channels[day].get("discussion_channel_id")
            if disc_channel_id:
                vote_display_text += f"\n\n💬 Discussion: <#{disc_channel_id}>"
            embed = discord.Embed(title=f"📊 Day {day} Votes - {game.name}", description=vote_display_text, color=discord.Color.blue())
            await message.edit(embed=embed)

            # Post ledger entry in the voting thread
            await channel.send(f"🗳️ 🤖 **{npc.name}** voted for {target_display}")

            if interaction.channel.id != votes_channel_id:
                await interaction.channel.send(f"🗳️ 🤖 **{npc.name}** has cast their vote! (Tally: {channel.mention})")

            await interaction.followup.send(f"✅ NPC '{npc_name}' voted for {target_display}!", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to update vote display: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(NPCCommands(bot))
