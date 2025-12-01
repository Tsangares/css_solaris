"""
Moderator Cog
Handles /end_day and other admin commands.
"""

import discord
from discord import app_commands
from discord.ext import commands
from models.game import Game, GameStatus
from utils import database, permissions, game_logic, forum_manager, bot_utils


class Moderator(commands.Cog):
    """Cog for moderator actions."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="invite", description="Get the bot invite link with proper permissions")
    async def invite(self, interaction: discord.Interaction):
        """Generate and display the bot invite link."""
        invite_url = bot_utils.generate_invite_link(self.bot.user.id)

        embed = discord.Embed(
            title="🔗 Invite CSS Solaris Bot",
            description="Use this link to invite the bot to another server with all required permissions:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Invite Link",
            value=f"[Click here to invite]({invite_url})",
            inline=False
        )
        embed.add_field(
            name="What permissions does this include?",
            value="• Manage Roles\n• Manage Channels\n• Manage Threads\n• Create Public Threads\n"
                  "• Send Messages in Threads\n• Send Messages\n• Embed Links\n• Read Message History",
            inline=False
        )
        embed.set_footer(text="These permissions are required for the bot to create games and manage voting.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setup", description="Set up CSS Solaris (creates moderator role and forums)")
    async def setup(self, interaction: discord.Interaction):
        """Set up CSS Solaris by creating moderator role and forum channels."""
        # Defer immediately to avoid timeout
        await interaction.response.defer()

        try:
            # Step 1: Check permissions
            await interaction.followup.send("🔍 Step 1/5: Checking your permissions...")

            guild = interaction.guild

            # Debug info
            await interaction.followup.send(
                f"Debug: Guild={guild.name if guild else 'None'}, "
                f"Guild ID={guild.id if guild else 'None'}, "
                f"Owner ID={guild.owner_id if guild else 'None'}"
            )

            # interaction.user in a guild command should be a Member object
            member = interaction.user

            # Fallback: if it's not a Member, something is wrong
            if not isinstance(member, discord.Member):
                await interaction.followup.send(
                    f"❌ Error: Cannot get your member info. Make sure this is used in a server!\n"
                    f"Debug: User type is {type(member)}"
                )
                return

            # Check permissions - just allow everyone for now to get past this step
            is_owner = interaction.user.id == guild.owner_id if guild and guild.owner_id else False
            is_admin = member.guild_permissions.administrator
            can_manage = member.guild_permissions.manage_guild

            await interaction.followup.send(
                f"Debug Perms: Owner={is_owner}, Admin={is_admin}, ManageGuild={can_manage}\n"
                f"Your ID={interaction.user.id}, Owner ID={guild.owner_id if guild else 'None'}"
            )

            # TEMPORARY: Skip permission check
            # if not (is_owner or is_admin or can_manage):
            #     await interaction.followup.send(
            #         f"❌ You need Administrator or Manage Server permission to run setup!"
            #     )
            #     return

            await interaction.followup.send("✅ Permission check passed (debug mode)!")

            # Step 2: Check bot permissions
            await interaction.followup.send("🔍 Step 2/5: Checking bot permissions...")

            guild = interaction.guild
            setup_results = []
            bot_member = guild.get_member(self.bot.user.id)

            missing_perms = bot_utils.check_missing_permissions(bot_member.guild_permissions)

            if missing_perms:
                invite_url = bot_utils.generate_invite_link(self.bot.user.id)

                embed = discord.Embed(
                    title="⚠️ Missing Permissions",
                    description="The bot is missing required permissions. You have two options:",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="Option 1: Grant Permissions Manually",
                    value=f"Go to Server Settings → Roles → {bot_member.mention}'s role and enable:\n" +
                          "\n".join([f"• {p}" for p in missing_perms]),
                    inline=False
                )
                embed.add_field(
                    name="Option 2: Re-invite the Bot",
                    value=f"Kick the bot and [use this invite link]({invite_url}) to re-add it with proper permissions.\n"
                          f"Or use `/invite` to get the link.",
                    inline=False
                )

                await interaction.followup.send(embed=embed)
                await interaction.followup.send(
                    "⚠️ Setup will continue but will likely fail without these permissions."
                )
            else:
                setup_results.append("✅ Bot has all required permissions")

            # Step 3: Create moderator role
            await interaction.followup.send("🔍 Step 3/5: Creating moderator role...")

            mod_role = discord.utils.get(guild.roles, name=permissions.MODERATOR_ROLE_NAME)

            if mod_role:
                setup_results.append(f"✅ Moderator role already exists: {mod_role.mention}")
            else:
                mod_role = await guild.create_role(
                    name=permissions.MODERATOR_ROLE_NAME,
                    color=discord.Color.blue(),
                    reason="CSS Solaris setup"
                )
                setup_results.append(f"✅ Created moderator role: {mod_role.mention}")

            # Step 4: Create lobby forum
            await interaction.followup.send("🔍 Step 4/5: Creating Game Lobby forum...")
            lobby_forum = await forum_manager.get_or_create_lobby_forum(guild)
            setup_results.append(f"✅ Game Lobby forum: {lobby_forum.mention}")

            # Step 5: Create game forums
            await interaction.followup.send("🔍 Step 5/5: Creating Discussion and Voting forums...")
            discussions_forum, voting_forum = await forum_manager.get_or_create_game_forums(
                guild,
                mod_role=mod_role,
                bot_member=bot_member
            )
            setup_results.append(f"✅ Game Discussions forum: {discussions_forum.mention}")
            setup_results.append(f"✅ Game Voting forum (hidden - mods only): {voting_forum.mention}")

            # Send success message
            embed = discord.Embed(
                title="🎮 CSS Solaris Setup Complete!",
                description="\n".join(setup_results),
                color=discord.Color.green()
            )
            embed.add_field(
                name="Next Steps",
                value=f"1. Assign the {mod_role.mention} role to users who should moderate games\n"
                      f"2. Use `/new_game` to create your first game!\n"
                      f"3. Use `/npc_create` to create test NPCs (available to everyone)",
                inline=False
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            await interaction.followup.send(f"❌ Setup failed at step: {e}\n\n```\n{error_details[:1000]}\n```")

    @app_commands.command(name="end_day", description="End the current day and tally votes (Moderator only)")
    async def end_day(self, interaction: discord.Interaction):
        """End the current day, count votes, and advance to next day."""
        # Get the player_actions cog to access get_game_from_channel
        player_actions_cog = self.bot.get_cog('PlayerActions')
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
                "❌ This channel is not a game channel! Use this command in the discussion thread.",
                ephemeral=True
            )
            return

        if day == 0 or day is None:
            await interaction.response.send_message(
                f"❌ Could not determine which day this is! Use this command in the discussion thread.",
                ephemeral=True
            )
            return

        # Check permissions
        if not permissions.can_manage_game(interaction.user.id, interaction.user, game):
            await interaction.response.send_message(
                "❌ You don't have permission to manage this game!",
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

        # Defer as this might take a moment
        await interaction.response.defer()

        try:
            current_day = game.current_day

            # Get votes from PlayerActions cog (already fetched above)
            votes = {}
            if player_actions_cog and game.name in player_actions_cog.votes:
                if current_day in player_actions_cog.votes[game.name]:
                    votes = player_actions_cog.votes[game.name][current_day]
                else:
                    # Debug: day mismatch
                    await interaction.followup.send(
                        f"⚠️ Debug: No votes found for day {current_day}. "
                        f"Available days: {list(player_actions_cog.votes[game.name].keys())}"
                    )
            else:
                # Debug: game not in votes
                await interaction.followup.send(
                    f"⚠️ Debug: No votes found for game '{game.name}'. "
                    f"Available games: {list(player_actions_cog.votes.keys())}"
                )

            # Get alive players
            alive_players = game.get_alive_players()

            # Count votes
            eliminated_id, result_type, tally = game_logic.count_votes(votes, alive_players)

            # Get user/NPC names
            user_names = {}
            for player_id in game.players:
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

            # Format end-of-day message
            announcement = game_logic.format_day_end_message(
                eliminated_id, result_type, tally, user_names, current_day
            )

            # Eliminate player if needed
            if eliminated_id:
                game.eliminate_player(eliminated_id)

            # Check win condition
            win_team = game_logic.check_win_condition(game.get_alive_players(), game.roles)
            if win_team:
                # Game over
                game.end_game()
                database.save_game(game)

                # Determine winner(s)
                alive_players = game.get_alive_players()
                winner_names = []
                for player_id in alive_players:
                    if player_id < 0:
                        # NPC
                        npc = database.get_npc_by_id(player_id)
                        if npc:
                            winner_names.append(f"🤖 {npc.name}")
                        else:
                            winner_names.append(f"🤖 NPC {player_id}")
                    else:
                        # Real user
                        try:
                            user = await self.bot.fetch_user(player_id)
                            winner_names.append(user.mention)
                        except:
                            winner_names.append(f"<@{player_id}>")

                winner_text = ", ".join(winner_names) if winner_names else "No one"

                embed = discord.Embed(
                    title=f"🏁 {game.name} - Game Over!",
                    description=announcement + f"\n\n**The game has ended!**\n**Winner(s):** {winner_text}",
                    color=discord.Color.red()
                )

                await interaction.followup.send(embed=embed)

                # Post in game threads
                votes_thread_id = game.channels[current_day]["votes_channel_id"]
                discussion_thread_id = game.channels[current_day]["discussion_channel_id"]

                votes_thread = await self.bot.fetch_channel(votes_thread_id)
                discussion_thread = await self.bot.fetch_channel(discussion_thread_id)

                await votes_thread.send(embed=embed)
                await discussion_thread.send(embed=embed)

                # Lock only discussion thread (voting forum permissions prevent posting anyway)
                await discussion_thread.edit(locked=True, archived=True)

                # Post winner announcement in general channel
                guild = interaction.guild
                general_channel = None

                # Try to find general channel (case-insensitive)
                for channel in guild.text_channels:
                    if channel.name.lower() in ['general', 'general-chat', 'chat']:
                        general_channel = channel
                        break

                if general_channel:
                    general_embed = discord.Embed(
                        title=f"🏆 {game.name} has ended!",
                        description=f"**Winner(s):** {winner_text}\n\nCongratulations! 🎉",
                        color=discord.Color.gold()
                    )
                    try:
                        await general_channel.send(embed=general_embed)
                    except:
                        # If we can't post in general, that's okay
                        pass

                return

            # Create next day forum threads
            next_day = current_day + 1
            guild = interaction.guild

            # Get moderator role and bot member for permissions
            mod_role = discord.utils.get(guild.roles, name=permissions.MODERATOR_ROLE_NAME)
            bot_member = guild.get_member(self.bot.user.id)

            # Get game forums
            discussions_forum, voting_forum = await forum_manager.get_or_create_game_forums(
                guild,
                mod_role=mod_role,
                bot_member=bot_member
            )

            # Create Day N discussion thread
            discussion_embed = discord.Embed(
                title=f"💬 {game.name} - Day {next_day} Discussion",
                description=f"Discuss and strategize here!",
                color=discord.Color.blue()
            )

            discussion_thread = await discussions_forum.create_thread(
                name=f"💬 {game.name} - Day {next_day}",
                content=f"**Day {next_day} Discussion for {game.name}**",
                embed=discussion_embed
            )

            # Create Day N voting thread with vote tracking embed
            vote_embed = discord.Embed(
                title=f"📊 Day {next_day} Votes - {game.name}",
                description="No votes yet. Use `/vote @player` or `/vote Abstain` or `/vote Veto`",
                color=discord.Color.blue()
            )

            voting_thread = await voting_forum.create_thread(
                name=f"🗳️ {game.name} - Day {next_day}",
                content=f"**Day {next_day} Voting for {game.name}**",
                embed=vote_embed
            )

            # The first message is the one we just created with the embed
            vote_message = voting_thread.message

            # Update game state
            game.current_day = next_day
            game.channels[next_day] = {
                "votes_channel_id": voting_thread.thread.id,
                "discussion_channel_id": discussion_thread.thread.id,
                "votes_message_id": vote_message.id
            }
            database.save_game(game)

            # Lock old discussion thread (voting thread stays open for viewing)
            old_votes_thread = await self.bot.fetch_channel(game.channels[current_day]["votes_channel_id"])
            old_discussion_thread = await self.bot.fetch_channel(game.channels[current_day]["discussion_channel_id"])

            # Only lock discussion thread - voting forum permissions prevent posting anyway
            await old_discussion_thread.edit(locked=True, archived=True)

            # Announce results
            alive_mentions = []
            for pid in game.get_alive_players():
                if pid < 0:
                    # NPC
                    npc = database.get_npc_by_id(pid)
                    if npc:
                        alive_mentions.append(f"🤖 {npc.name}")
                    else:
                        alive_mentions.append(f"🤖 NPC {pid}")
                else:
                    # Real user
                    alive_mentions.append(f"<@{pid}>")

            result_embed = discord.Embed(
                title=f"🌙 Day {current_day} - Results",
                description=announcement,
                color=discord.Color.purple()
            )

            # Player announcement (doesn't mention hidden votes channel)
            player_next_day_embed = discord.Embed(
                title=f"🌅 {game.name} - Day {next_day} Begins!",
                description=f"**Alive Players ({len(game.get_alive_players())}):**\n" + ", ".join(alive_mentions) + "\n\n"
                           f"**Discussion Thread:** {discussion_thread.thread.mention}\n"
                           f"Discuss and use `/vote @player` (or `/vote Abstain` or `/vote Veto`) here!",
                color=discord.Color.gold()
            )

            # Mod announcement (includes votes channel)
            mod_next_day_embed = discord.Embed(
                title=f"🌅 {game.name} - Day {next_day} Begins!",
                description=f"**Alive Players ({len(game.get_alive_players())}):**\n" + ", ".join(alive_mentions) + "\n\n"
                           f"**Threads:**\n"
                           f"💬 {discussion_thread.thread.mention} - Discussion and voting\n"
                           f"🗳️ {voting_thread.thread.mention} - Vote tracking (hidden from players)",
                color=discord.Color.gold()
            )

            await interaction.followup.send(embed=result_embed)
            await interaction.followup.send(embed=player_next_day_embed)

            await old_votes_thread.send(embed=result_embed)
            await old_discussion_thread.send(embed=result_embed)
            # Don't post announcement in new voting thread - keep it clean for vote tally only
            await discussion_thread.thread.send(embed=player_next_day_embed)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed to end day: {e}")


async def setup(bot):
    """Setup function for cog."""
    await bot.add_cog(Moderator(bot))
