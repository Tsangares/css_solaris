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

    @app_commands.command(name="game", description="Create a new CSS Solaris game")
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
                           f"Once enough players have joined, a moderator can use `/start` to begin!",
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
            try:
                await signup_thread.message.pin()
            except discord.Forbidden:
                pass

            # Create game role and assign to creator
            from utils import role_manager
            try:
                discord_roles = await role_manager.create_game_roles(interaction.guild, name)
            except discord.Forbidden:
                discord_roles = {}

            # Create the game in database - creator auto-joins
            game = Game(
                name=name,
                creator_id=interaction.user.id,
                signup_thread_id=signup_thread.thread.id
            )
            game.discord_roles = discord_roles
            database.save_game(game)

            # Assign game role to creator
            player_role_id = discord_roles.get("player")
            if player_role_id:
                await role_manager.assign_player_role(interaction.guild, interaction.user.id, player_role_id)

            # Create game category with private channels
            guild = interaction.guild
            mod_role = discord.utils.get(guild.roles, name=permissions.MODERATOR_ROLE_NAME)
            bot_member = guild.get_member(self.bot.user.id)
            try:
                category, mc_channel, saboteur_channel, dead_channel = await forum_manager.create_private_channels(
                    guild, name, mod_role, bot_member, creator_id=interaction.user.id
                )
                game.team_channels = {
                    "category": category.id,
                    "mc": mc_channel.id,
                    "saboteurs": saboteur_channel.id,
                    "dead": dead_channel.id
                }
                database.save_game(game)
            except Exception as e:
                print(f"Failed to create private channels: {e}")
                import traceback
                traceback.print_exc()

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
        if not permissions.can_run_game(interaction.user.id, game):
            await interaction.response.send_message(
                "❌ Only the game creator or game mods can start this game!",
                ephemeral=True
            )
            return

        # Check if game is in signup status
        if game.status != GameStatus.SIGNUP:
            await interaction.response.send_message(
                f"❌ Game '{game.name}' has already started or ended!",
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
                title=f"💬 {game.name} - Day 1 Discussion",
                description=f"Discuss and strategize here!",
                color=discord.Color.blue()
            )

            discussion_thread = await discussions_forum.create_thread(
                name=f"💬 {game.name} - Day 1",
                content=f"**Day 1 Discussion for {game.name}**",
                embed=discussion_embed
            )

            # Send a pinnable welcome message in the discussion thread
            alive_mentions = ", ".join(f"<@{pid}>" for pid in game.players if pid > 0)
            npc_names = ", ".join(
                f"🤖 {database.get_npc_by_id(pid).name}" for pid in game.players
                if pid < 0 and database.get_npc_by_id(pid)
            )
            all_players = alive_mentions
            if npc_names:
                all_players += f", {npc_names}" if all_players else npc_names

            welcome_msg = await discussion_thread.thread.send(
                f"**Discussion for {game.name} is now open!**\n\n"
                f"Players: {all_players}\n\n"
                f"Use `/vote` to cast your vote. Good luck!"
            )
            try:
                await welcome_msg.pin()
            except discord.Forbidden:
                pass

            # Create Day 1 voting thread with vote tracking embed
            vote_embed = discord.Embed(
                title=f"📊 Day 1 Votes - {game.name}",
                description=f"No votes yet. Use `/vote @player` or `/vote Abstain`\n\n"
                            f"💬 Discussion: {discussion_thread.thread.mention}",
                color=discord.Color.blue()
            )

            voting_thread = await voting_forum.create_thread(
                name=f"🗳️ {game.name} - Day 1",
                content=f"**Day 1 Voting for {game.name}**",
                embed=vote_embed
            )

            # Send a welcome message in the voting thread tagging all players
            try:
                vote_welcome = await voting_thread.thread.send(
                    f"**Vote tracking for {game.name}**\n\n"
                    f"Players: {all_players}\n\n"
                    f"Votes will appear below as a ledger. The tally above updates live.\n"
                    f"📌 Click the pins icon to jump back to the tally."
                )
                try:
                    await vote_welcome.pin()
                except discord.Forbidden:
                    pass
            except discord.Forbidden:
                pass

            # Add players + MC to both threads
            users_to_add = set(pid for pid in game.players if pid > 0)
            users_to_add.add(game.creator_id)  # Always include MC
            for user_id in users_to_add:
                try:
                    await discussion_thread.thread.add_user(discord.Object(id=user_id))
                except Exception:
                    pass
                try:
                    await voting_thread.thread.add_user(discord.Object(id=user_id))
                except Exception:
                    pass

            # The first message is the one we just created with the embed
            vote_message = voting_thread.message

            # Update game state and save immediately so progress isn't lost
            from datetime import datetime, timezone
            game.start_game()
            game.day_started_at = datetime.now(timezone.utc).isoformat()
            game.channels[1] = {
                "votes_channel_id": voting_thread.thread.id,
                "discussion_channel_id": discussion_thread.thread.id,
                "votes_message_id": vote_message.id
            }
            database.save_game(game)

            # Assign game roles (crew/saboteur) internally
            from utils import roles as role_utils, role_manager
            saboteur_ratio = game.settings.get("saboteur_ratio", 0.33)
            game.roles = role_utils.assign_roles(list(game.players), saboteur_ratio=saboteur_ratio)

            # Roles already created when game was made and assigned on /join
            # Just ensure they exist
            if not game.discord_roles:
                try:
                    game.discord_roles = await role_manager.create_game_roles(guild, game.name)
                except discord.Forbidden:
                    pass

            # Private channels were created in /game - fetch them
            saboteur_channel = None
            sab_channel_id = game.team_channels.get("saboteurs")
            if sab_channel_id:
                try:
                    saboteur_channel = await self.bot.fetch_channel(sab_channel_id)
                except Exception:
                    pass

            # Give saboteurs access to their private channel (by user, not by role)
            saboteur_names = []
            if saboteur_channel:
                for player_id, role_name in game.roles.items():
                    if game.get_player_team(player_id) == "saboteur":
                        if player_id < 0:
                            npc = database.get_npc_by_id(player_id)
                            saboteur_names.append(f"🤖 {npc.name}" if npc else f"NPC {player_id}")
                        else:
                            try:
                                member = await guild.fetch_member(player_id)
                                await saboteur_channel.set_permissions(member, view_channel=True, send_messages=True)
                                saboteur_names.append(f"<@{player_id}>")
                            except Exception:
                                saboteur_names.append(f"<@{player_id}>")

                # Update saboteur channel with team roster
                if saboteur_names:
                    await saboteur_channel.send(
                        f"**Your team:**\n" +
                        "\n".join(f"- {name}" for name in saboteur_names)
                    )

            # Send role DMs to players with channel links
            disc_thread = discussion_thread.thread
            vote_thread = voting_thread.thread

            for player_id, role_name in game.roles.items():
                if player_id < 0:
                    continue

                try:
                    user = await self.bot.fetch_user(player_id)
                    role_info = role_utils.get_role_info(role_name)

                    dm_embed = discord.Embed(
                        title=f"🎮 {game.name} - Your Role",
                        description=f"{role_info['emoji']} **{role_name}**\n\n{role_info['description']}",
                        color=discord.Color.red() if role_info['team'] == "saboteur" else discord.Color.blue()
                    )

                    # Channel links
                    links = f"💬 Discussion: {disc_thread.mention}\n🗳️ Vote tally: {vote_thread.mention}"
                    if role_info['team'] == "saboteur" and saboteur_channel:
                        links += f"\n🔴 Saboteur chat: {saboteur_channel.mention}"
                    dm_embed.add_field(name="Channels", value=links, inline=False)

                    # Player list
                    alive_names = []
                    for pid in game.players:
                        if pid < 0:
                            npc = database.get_npc_by_id(pid)
                            alive_names.append(f"🤖 {npc.name}" if npc else f"NPC {pid}")
                        else:
                            alive_names.append(f"<@{pid}>")
                    dm_embed.add_field(
                        name=f"Players ({len(game.players)})",
                        value=", ".join(alive_names),
                        inline=False
                    )

                    dm_embed.set_footer(text="Good luck! Your role is secret - don't share it!")
                    await user.send(embed=dm_embed)
                except Exception:
                    pass

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
                "CSS Solaris is a social deduction game of **Crew vs Saboteurs**. "
                "The crew must identify and eliminate all saboteurs before they take control of the ship!\n\n"
                f"{role_utils.format_role_distribution(len(game.players))}\n\n"
                "**📜 How to Play:**\n"
                "• Discuss with other players to find suspicious behavior\n"
                "• Use `/vote @player` to vote someone out (or `/vote Abstain` to skip elimination)\n"
                "• Players with the most votes are eliminated at day's end\n"
                "• **Crew wins** if all saboteurs are eliminated\n"
                "• **Saboteurs win** if they control ≥50% of the ship\n\n"
                "**Your role has been sent to you via DM!** Check your messages! 📬\n\n"
            )

            # Announcement for players (don't mention hidden votes channel)
            player_announcement = discord.Embed(
                title=f"🌅 {game.name} - Day 1 Begins!",
                description=game_description +
                           f"**Players ({len(game.players)}):**\n" + ", ".join(player_mentions) + "\n\n"
                           f"**Discussion Thread:** {discussion_thread.thread.mention}\n"
                           f"Discuss and use `/vote @player` (or `/vote Abstain`) here!\n\n"
                           f"Good luck!",
                color=discord.Color.gold()
            )

            # Announcement for mods (includes votes channel)
            mod_announcement = discord.Embed(
                title=f"🌅 {game.name} - Day 1 Begins!",
                description=f"The game has started!\n\n"
                           f"**Players ({len(game.players)}):**\n" + ", ".join(player_mentions) + "\n\n"
                           f"**Threads:**\n"
                           f"💬 {discussion_thread.thread.mention} - Discussion and voting\n"
                           f"🗳️ {voting_thread.thread.mention} - Vote tracking (hidden from players)\n\n"
                           f"Good luck!",
                color=discord.Color.gold()
            )

            await interaction.followup.send(embed=player_announcement)
            # Don't post announcement in voting thread - keep it clean for vote tally only
            await discussion_thread.thread.send(embed=player_announcement)

        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Failed to start game: {e}")


async def setup(bot):
    """Setup function for cog."""
    await bot.add_cog(GameManagement(bot))
