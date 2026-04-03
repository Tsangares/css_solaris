"""
Moderator Cog
Handles /end_day and other admin commands.
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timezone
from models.game import Game, GameStatus
from utils import database, permissions, game_logic, forum_manager, bot_utils, server_config


class Moderator(commands.Cog):
    """Cog for moderator actions."""

    def __init__(self, bot):
        self.bot = bot
        self.phase_timer.start()

    def cog_unload(self):
        self.phase_timer.cancel()

    @tasks.loop(minutes=5)
    async def phase_timer(self):
        """Check for expired day/night phases and auto-lock/resolve."""
        games = database.load_games()
        for game in games.values():
            if game.status != GameStatus.ACTIVE:
                continue

            now = datetime.now(timezone.utc)
            duration_hours = game.settings.get("day_duration_hours", 24)

            # Auto-lock day discussion after timer expires
            if game.phase == "day" and game.day_started_at:
                started = datetime.fromisoformat(game.day_started_at)
                if (now - started).total_seconds() > duration_hours * 3600:
                    # Lock the discussion thread
                    disc_id = game.channels.get(game.current_day, {}).get("discussion_channel_id")
                    if disc_id:
                        try:
                            thread = await self.bot.fetch_channel(disc_id)
                            await thread.send("⏰ **Time's up!** Discussion is now locked. A moderator should run `/endday`.")
                            await thread.edit(locked=True)
                        except Exception:
                            pass
                    # Clear the timer so we don't spam
                    game.day_started_at = None
                    database.save_game(game)

            # Auto-resolve night after timer expires
            if game.phase == "night" and game.night_started_at:
                started = datetime.fromisoformat(game.night_started_at)
                if (now - started).total_seconds() > duration_hours * 3600:
                    # Auto-vote for any saboteurs that haven't voted, then resolve
                    import random as _random
                    alive_non_sab = [pid for pid in game.get_alive_players() if game.get_player_team(pid) != "saboteur"]
                    for pid in game.get_alive_players():
                        if game.get_player_team(pid) == "saboteur" and pid not in game.night_kill_votes:
                            if alive_non_sab:
                                game.night_kill_votes[pid] = _random.choice(alive_non_sab)

                    # Notify saboteur channel
                    sab_channel_id = game.team_channels.get("saboteurs")
                    if sab_channel_id:
                        try:
                            sab_ch = await self.bot.fetch_channel(sab_channel_id)
                            await sab_ch.send("⏰ **Night timer expired.** Kill target auto-resolved.")
                        except Exception:
                            pass

                    # Clear timer - a mod still needs to /endnight to execute
                    game.night_started_at = None
                    database.save_game(game)

    @phase_timer.before_loop
    async def before_phase_timer(self):
        await self.bot.wait_until_ready()

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
            guild = interaction.guild

            # Check permissions
            if not permissions.is_admin(interaction.user):
                await interaction.followup.send(
                    "❌ You need Administrator or Manage Server permission to run setup!",
                    ephemeral=True
                )
                return

            # Check bot permissions
            await interaction.followup.send("🔍 Checking bot permissions...")

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

            # Create moderator role
            await interaction.followup.send("🔍 Creating moderator role...")

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

            # Create lobby forum
            await interaction.followup.send("🔍 Creating Game Lobby forum...")
            lobby_forum = await forum_manager.get_or_create_lobby_forum(guild)
            setup_results.append(f"✅ Game Lobby forum: {lobby_forum.mention}")

            # Create game forums
            await interaction.followup.send("🔍 Creating Discussion and Voting forums...")
            discussions_forum, voting_forum = await forum_manager.get_or_create_game_forums(
                guild,
                mod_role=mod_role,
                bot_member=bot_member
            )
            setup_results.append(f"✅ Game Discussions forum: {discussions_forum.mention}")
            setup_results.append(f"✅ Game Voting forum: {voting_forum.mention}")

            # Organize - move forums into the category if not already
            category = await forum_manager.get_or_create_main_category(guild)
            for forum in [lobby_forum, discussions_forum, voting_forum]:
                if forum.category != category:
                    try:
                        await forum.edit(category=category)
                    except Exception:
                        pass
            setup_results.append(f"✅ Organized under: {category.name}")

            # Send success message
            embed = discord.Embed(
                title="🎮 CSS Solaris Setup Complete!",
                description="\n".join(setup_results),
                color=discord.Color.green()
            )
            embed.add_field(
                name="Next Steps",
                value=f"1. Assign the {mod_role.mention} role to users who should moderate games\n"
                      f"2. Use `/game` to create your first game!\n"
                      f"3. Use `/npc create` to create test NPCs",
                inline=False
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            await interaction.followup.send(f"❌ Setup failed at step: {e}\n\n```\n{error_details[:1000]}\n```")

    @app_commands.command(name="endday", description="End the current day and tally votes (Moderator only)")
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

        # Check permissions - only game creator and game mods can run game actions
        if not permissions.can_run_game(interaction.user.id, game):
            await interaction.response.send_message(
                "❌ Only the game creator or game mods can end the day!",
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
            guild = interaction.guild
            current_day = game.current_day

            # Get votes from game model (persisted to database)
            votes = game.votes.get(current_day, {})

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
                    # Real user - use server display name
                    member = guild.get_member(player_id)
                    user_names[player_id] = member.display_name if member else f"User {player_id}"

            # Format end-of-day message (role hidden until dawn)
            announcement = game_logic.format_day_end_message(
                eliminated_id, result_type, tally, user_names, current_day, game.roles, reveal_role=False
            )

            # Eliminate player if needed
            if eliminated_id:
                game.eliminate_player(eliminated_id)
                game.last_vote_eliminated = eliminated_id

                # NEW: Handle death permissions for Discord roles and channels
                if eliminated_id > 0:  # Only for real players, not NPCs
                    from utils import role_manager
                    guild = interaction.guild

                    # Get Discord role IDs
                    dead_role_id = game.discord_roles.get("dead")
                    team = game.get_player_team(eliminated_id)
                    team_role_id = game.discord_roles.get(team)

                    # Move player to dead role
                    if dead_role_id:
                        await role_manager.assign_player_role(guild, eliminated_id, dead_role_id)

                    # Remove from team role
                    if team_role_id:
                        await role_manager.remove_player_role(guild, eliminated_id, team_role_id)

                    # Give access to dead channel
                    dead_channel_id = game.team_channels.get("dead")
                    if dead_channel_id:
                        try:
                            dead_channel = await self.bot.fetch_channel(dead_channel_id)
                            member = await guild.fetch_member(eliminated_id)

                            # Give read-only access to dead channel
                            await dead_channel.set_permissions(
                                member,
                                view_channel=True,
                                send_messages=False
                            )

                            # Send notification in dead channel
                            eliminated_name = user_names.get(eliminated_id, f"User {eliminated_id}")
                            eliminated_role = game.roles.get(eliminated_id, "Unknown")
                            from utils import roles as role_utils
                            role_info = role_utils.get_role_info(eliminated_role)
                            await dead_channel.send(
                                f"💀 **{eliminated_name}** ({role_info['emoji']} {eliminated_role}) has joined the afterlife..."
                            )
                        except Exception:
                            pass

                    # If saboteur died, make saboteur channel read-only for them
                    if team == "saboteur":
                        sab_channel_id = game.team_channels.get("saboteurs")
                        if sab_channel_id:
                            try:
                                sab_channel = await self.bot.fetch_channel(sab_channel_id)
                                member = await guild.fetch_member(eliminated_id)
                                await sab_channel.set_permissions(member, view_channel=True, send_messages=False)
                            except Exception:
                                pass

            # Check win condition
            win_team = game_logic.check_win_condition(game.get_alive_players(), game.roles, game.settings)
            if win_team:
                # Game over
                game.end_game()
                database.save_game(game)

                from utils import roles as role_utils

                # Build team victory message
                if win_team == "crew":
                    title = "🏆 Crew Victory!"
                    victory_headline = "> *The crew has successfully eliminated all saboteurs!*"
                    color = discord.Color.blue()
                elif win_team == "saboteur":
                    title = "🔴 Saboteur Victory!"
                    victory_headline = "> *The saboteurs have taken control of the ship!*"
                    color = discord.Color.red()
                else:
                    title = "🏁 Game Over!"
                    victory_headline = "> *The game has ended!*"
                    color = discord.Color.red()

                alive_players = game.get_alive_players()

                # Winners - only the winning team
                winner_lines = []
                for player_id in game.players:
                    team = game.get_player_team(player_id)
                    if team == win_team or (win_team == "crew" and team != "saboteur") or (win_team == "game_over"):
                        name = user_names.get(player_id, f"User {player_id}")
                        role_name = game.roles.get(player_id, "Unknown")
                        role_info = role_utils.get_role_info(role_name)
                        role_emoji = role_info.get('emoji', '')
                        status = "✅" if player_id in alive_players else "💀"
                        winner_lines.append(f"- {status} {role_emoji} **{name}** — {role_name}")

                # All players
                all_lines = []
                for player_id in game.players:
                    name = user_names.get(player_id, f"User {player_id}")
                    role_name = game.roles.get(player_id, "Unknown")
                    role_info = role_utils.get_role_info(role_name)
                    role_emoji = role_info.get('emoji', '')
                    status = "💀" if player_id not in alive_players else "✅"
                    all_lines.append(f"- {status} {role_emoji} **{name}** — {role_name}")

                # Game stats
                total_days = game.current_day
                total_elim = len(game.eliminated_players)

                victory_desc = (
                    f"{victory_headline}\n\n"
                    f"## Winners\n" +
                    ("\n".join(winner_lines) if winner_lines else "- No one survived") +
                    f"\n\n## All Players\n" +
                    "\n".join(all_lines) +
                    f"\n\n## Stats\n"
                    f"- Days played: **{total_days}**\n"
                    f"- Players eliminated: **{total_elim}**\n"
                    f"- Total players: **{len(game.players)}**"
                )

                embed = discord.Embed(
                    title=title,
                    description=announcement + f"\n\n{victory_desc}",
                    color=color
                )

                await interaction.followup.send(embed=embed)

                # Post in game threads
                votes_thread_id = game.channels[current_day]["votes_channel_id"]
                discussion_thread_id = game.channels[current_day]["discussion_channel_id"]

                votes_thread = await self.bot.fetch_channel(votes_thread_id)
                discussion_thread = await self.bot.fetch_channel(discussion_thread_id)

                # Post to threads (skip if command was run from that thread)
                if interaction.channel.id != votes_thread_id:
                    await votes_thread.send(embed=embed)
                if interaction.channel.id != discussion_thread_id:
                    await discussion_thread.send(embed=embed)

                # Lock last day's threads
                try:
                    await discussion_thread.edit(locked=True, archived=True)
                except Exception:
                    pass

                # Create post-game discussion thread with summary
                discussions_forum, voting_forum = await forum_manager.get_or_create_game_forums(
                    guild,
                    mod_role=discord.utils.get(guild.roles, name=permissions.MODERATOR_ROLE_NAME),
                    bot_member=guild.get_member(self.bot.user.id)
                )

                # Build day-by-day summary with links
                summary_lines = []
                for day_num in sorted(game.channels.keys()):
                    ch = game.channels[day_num]
                    disc_id = ch.get("discussion_channel_id")
                    vote_id = ch.get("votes_channel_id")
                    summary_lines.append(
                        f"**Day {day_num}:** "
                        f"[Discussion](https://discord.com/channels/{guild.id}/{disc_id}) · "
                        f"[Votes](https://discord.com/channels/{guild.id}/{vote_id})"
                    )

                postgame_embed = discord.Embed(
                    title=f"🎉 {game.name} - Post-Game Chat",
                    description=(
                        f"{victory_desc}\n"
                        f"**Game History**\n" + "\n".join(summary_lines) + "\n\n"
                        f"Feel free to discuss the game! All roles are revealed above."
                    ),
                    color=discord.Color.gold()
                )

                postgame_thread = await discussions_forum.create_thread(
                    name=f"🎉 {game.name} - Post-Game",
                    content=f"**{game.name} has ended!**",
                    embed=postgame_embed
                )

                # Tag all players in the post-game thread
                all_player_mentions = []
                for pid in game.players:
                    if pid > 0:
                        all_player_mentions.append(f"<@{pid}>")
                    else:
                        npc = database.get_npc_by_id(pid)
                        all_player_mentions.append(f"🤖 {npc.name}" if npc else f"🤖 NPC {pid}")

                welcome = await postgame_thread.thread.send(
                    f"GG! {', '.join(all_player_mentions)}\n\n"
                    f"All roles have been revealed. Chat freely!"
                )
                try:
                    await welcome.pin()
                except discord.Forbidden:
                    pass

                # Add all players to post-game thread
                for pid in game.players:
                    if pid > 0:
                        try:
                            await postgame_thread.thread.add_user(discord.Object(id=pid))
                        except Exception:
                            pass

                # Keep private channels (saboteur/dead) for post-game reading
                # They'll be cleaned up by /purge
                # Just make saboteur channel visible to all players so they can read the scheming
                from utils import role_manager
                sab_channel_id = game.team_channels.get("saboteurs")
                if sab_channel_id:
                    try:
                        sab_ch = await self.bot.fetch_channel(sab_channel_id)
                        player_role_id = game.discord_roles.get("player")
                        if player_role_id:
                            player_role = guild.get_role(player_role_id)
                            if player_role:
                                await sab_ch.set_permissions(player_role, view_channel=True, send_messages=False)
                    except Exception:
                        pass

                return

            # Transition to night phase
            from datetime import datetime, timezone
            game.phase = "night"
            game.night_kill_votes = {}
            game.night_started_at = datetime.now(timezone.utc).isoformat()
            database.save_game(game)

            # Lock current discussion thread
            old_votes_thread = await self.bot.fetch_channel(game.channels[current_day]["votes_channel_id"])
            old_discussion_thread = await self.bot.fetch_channel(game.channels[current_day]["discussion_channel_id"])

            # Send results before locking
            result_embed = discord.Embed(
                title=f"Day {current_day} Results",
                description=announcement,
                color=discord.Color.purple()
            )
            # Send results to threads (skip current channel to avoid duplicates)
            votes_thread_id = game.channels[current_day]["votes_channel_id"]
            disc_thread_id = game.channels[current_day]["discussion_channel_id"]
            if interaction.channel.id != votes_thread_id:
                await old_votes_thread.send(embed=result_embed)
            if interaction.channel.id != disc_thread_id:
                await old_discussion_thread.send(embed=result_embed)
            await old_discussion_thread.edit(locked=True, archived=True)

            # Night announcement
            night_embed = discord.Embed(
                title=f"🌙 {game.name} — Night Falls",
                description=(
                    "The discussion is over. Night has fallen.\n\n"
                    "The saboteurs are choosing their target...\n"
                    "Saboteurs: use `/kill` then `/endnight` when ready."
                ),
                color=discord.Color.dark_purple()
            )
            await interaction.followup.send(embed=result_embed)
            await interaction.followup.send(embed=night_embed)

            # Notify saboteur channel
            sab_channel_id = game.team_channels.get("saboteurs")
            if sab_channel_id:
                try:
                    sab_channel = await self.bot.fetch_channel(sab_channel_id)
                    alive_non_sab = [
                        user_names.get(pid, f"Player {pid}")
                        for pid in game.get_alive_players()
                        if game.get_player_team(pid) != "saboteur"
                    ]
                    sab_embed = discord.Embed(
                        title="🔪 Night Phase — Choose Your Target",
                        description=(
                            "Use `/kill @player` to vote on who to eliminate tonight.\n\n"
                            "**Available targets:**\n" +
                            "\n".join(f"- {name}" for name in alive_non_sab)
                        ),
                        color=discord.Color.red()
                    )
                    await sab_channel.send(embed=sab_embed)
                except Exception:
                    pass

            # DM alive players
            for player_id in game.get_alive_players():
                if player_id < 0:
                    continue
                try:
                    user = await self.bot.fetch_user(player_id)
                    dm_embed = discord.Embed(
                        title=f"🌙 {game.name} — Night",
                        description=f"{announcement}\n\nNight has fallen. The saboteurs are choosing their target...",
                        color=discord.Color.dark_purple()
                    )
                    await user.send(embed=dm_embed)
                except Exception:
                    pass

        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Failed to end day: {e}")


    # --- MC Commands ---

    @app_commands.command(name="smite", description="Instantly eliminate a player (MC only)")
    @app_commands.describe(target="The player to eliminate", reason="What happened to them")
    async def smite(self, interaction: discord.Interaction, target: discord.Member, reason: str = "struck down by fate"):
        """MC kills a player instantly with a custom reason."""
        game, day = self._find_game_from_channel(interaction.channel.id)
        if not game:
            games = database.load_games()
            for g in games.values():
                if g.team_channels.get("mc") == interaction.channel.id:
                    game = g
                    break

        if not game:
            await interaction.response.send_message("Use this in a game channel or MC booth.", ephemeral=True)
            return
        if not permissions.can_run_game(interaction.user.id, game):
            await interaction.response.send_message("Only the MC can smite!", ephemeral=True)
            return
        if target.id not in game.players or not game.is_player_alive(target.id):
            await interaction.response.send_message("That player is not alive in this game!", ephemeral=True)
            return

        await interaction.response.defer()
        guild = interaction.guild

        game.eliminate_player(target.id)

        # Get role info
        from utils import roles as role_utils, role_manager
        player_role = game.roles.get(target.id, "Unknown")
        role_info = role_utils.get_role_info(player_role)
        role_emoji = role_info.get('emoji', '')

        # Handle death permissions
        dead_role_id = game.discord_roles.get("dead")
        player_role_id = game.discord_roles.get("player")
        if dead_role_id:
            await role_manager.assign_player_role(guild, target.id, dead_role_id)
        if player_role_id:
            await role_manager.remove_player_role(guild, target.id, player_role_id)

        # Afterlife access
        dead_channel_id = game.team_channels.get("dead")
        if dead_channel_id:
            try:
                dead_ch = await self.bot.fetch_channel(dead_channel_id)
                await dead_ch.set_permissions(target, view_channel=True, send_messages=False)
            except Exception:
                pass

        # Saboteur channel read-only if they were a saboteur
        if game.get_player_team(target.id) == "saboteur":
            sab_id = game.team_channels.get("saboteurs")
            if sab_id:
                try:
                    sab_ch = await self.bot.fetch_channel(sab_id)
                    await sab_ch.set_permissions(target, view_channel=True, send_messages=False)
                except Exception:
                    pass

        database.save_game(game)

        # Announce in discussion
        smite_embed = discord.Embed(
            title="💥 Divine Intervention",
            description=(
                f"**{target.display_name}** was *{reason}*...\n"
                f"They were: {role_emoji} **{player_role}**"
            ),
            color=discord.Color.dark_red()
        )

        disc_id = game.channels.get(game.current_day, {}).get("discussion_channel_id")
        if disc_id:
            try:
                disc_ch = await self.bot.fetch_channel(disc_id)
                await disc_ch.send(embed=smite_embed)
            except Exception:
                pass

        await interaction.followup.send(embed=smite_embed)

        # Check win condition
        win_team = game_logic.check_win_condition(game.get_alive_players(), game.roles, game.settings)
        if win_team:
            game.end_game()
            database.save_game(game)
            if win_team == "crew":
                await interaction.followup.send(embed=discord.Embed(title="🏆 Crew Victory!", color=discord.Color.blue()))
            elif win_team == "saboteur":
                await interaction.followup.send(embed=discord.Embed(title="🔴 Saboteur Victory!", color=discord.Color.red()))

    @app_commands.command(name="revive", description="Bring a dead player back to life (MC only)")
    @app_commands.describe(target="The player to revive")
    async def revive(self, interaction: discord.Interaction, target: discord.Member):
        """MC revives an eliminated player."""
        game, day = self._find_game_from_channel(interaction.channel.id)
        if not game:
            games = database.load_games()
            for g in games.values():
                if g.team_channels.get("mc") == interaction.channel.id:
                    game = g
                    break

        if not game:
            await interaction.response.send_message("Use this in a game channel or MC booth.", ephemeral=True)
            return
        if not permissions.can_run_game(interaction.user.id, game):
            await interaction.response.send_message("Only the MC can revive!", ephemeral=True)
            return
        if target.id not in game.eliminated_players:
            await interaction.response.send_message("That player is not dead!", ephemeral=True)
            return

        guild = interaction.guild

        # Remove from eliminated
        game.eliminated_players.remove(target.id)

        # Restore roles
        from utils import role_manager
        dead_role_id = game.discord_roles.get("dead")
        player_role_id = game.discord_roles.get("player")
        if dead_role_id:
            await role_manager.remove_player_role(guild, target.id, dead_role_id)
        if player_role_id:
            await role_manager.assign_player_role(guild, target.id, player_role_id)

        # Remove afterlife access
        dead_channel_id = game.team_channels.get("dead")
        if dead_channel_id:
            try:
                dead_ch = await self.bot.fetch_channel(dead_channel_id)
                await dead_ch.set_permissions(target, overwrite=None)
            except Exception:
                pass

        # Restore saboteur channel access if they're a saboteur
        if game.get_player_team(target.id) == "saboteur":
            sab_id = game.team_channels.get("saboteurs")
            if sab_id:
                try:
                    sab_ch = await self.bot.fetch_channel(sab_id)
                    await sab_ch.set_permissions(target, view_channel=True, send_messages=True)
                except Exception:
                    pass

        database.save_game(game)

        # Announce
        revive_embed = discord.Embed(
            title="✨ Resurrection",
            description=f"**{target.display_name}** has been brought back from the dead!",
            color=discord.Color.green()
        )

        disc_id = game.channels.get(game.current_day, {}).get("discussion_channel_id")
        if disc_id:
            try:
                disc_ch = await self.bot.fetch_channel(disc_id)
                await disc_ch.send(embed=revive_embed)
            except Exception:
                pass

        # Add them back to current threads
        if game.current_day in game.channels:
            try:
                disc_thread = await self.bot.fetch_channel(game.channels[game.current_day]["discussion_channel_id"])
                vote_thread = await self.bot.fetch_channel(game.channels[game.current_day]["votes_channel_id"])
                await disc_thread.add_user(target)
                await vote_thread.add_user(target)
            except Exception:
                pass

        await interaction.response.send_message(embed=revive_embed)

    # --- Night Phase Commands ---

    async def kill_target_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        import random as _random
        choices = []
        game, day = self._find_game_from_channel(interaction.channel.id)
        if not game:
            games = database.load_games()
            for g in games.values():
                if g.team_channels.get("saboteurs") == interaction.channel.id:
                    game = g
                    break
        if game and game.phase == "night":
            for pid in game.get_alive_players():
                if game.get_player_team(pid) == "saboteur":
                    continue
                if pid < 0:
                    npc = database.get_npc_by_id(pid)
                    if npc:
                        choices.append(app_commands.Choice(name=f"🤖 {npc.name}", value=npc.name))
                else:
                    member = interaction.guild.get_member(pid)
                    if member:
                        choices.append(app_commands.Choice(name=member.display_name, value=f"<@{pid}>"))
            _random.shuffle(choices)
        if current:
            choices = [c for c in choices if current.lower() in c.name.lower()]
        return choices[:25]

    @app_commands.command(name="kill", description="Choose a target to eliminate tonight (Saboteurs only, night phase)")
    @app_commands.describe(target="The player to kill tonight")
    @app_commands.autocomplete(target=kill_target_autocomplete)
    async def kill(self, interaction: discord.Interaction, target: str):
        """Saboteur kill vote during night phase."""
        # Find game - check saboteur channel or game channels
        game, day = self._find_game_from_channel(interaction.channel.id)
        if not game:
            games = database.load_games()
            for g in games.values():
                if g.team_channels.get("saboteurs") == interaction.channel.id:
                    game = g
                    break

        if not game:
            await interaction.response.send_message(
                "Use `/kill` in the saboteur channel or a game channel during night phase.",
                ephemeral=True
            )
            return

        if game.phase != "night":
            await interaction.response.send_message("It's not nighttime! `/kill` only works during the night phase.", ephemeral=True)
            return

        # Check if user is an alive saboteur
        if not permissions.is_player_in_game(interaction.user.id, game):
            await interaction.response.send_message("You're not in this game!", ephemeral=True)
            return
        if not game.is_player_alive(interaction.user.id):
            await interaction.response.send_message("You've been eliminated!", ephemeral=True)
            return
        if game.get_player_team(interaction.user.id) != "saboteur":
            await interaction.response.send_message("Only saboteurs can use `/kill`!", ephemeral=True)
            return

        # Parse target
        target_id = None
        if target.startswith("<@") and target.endswith(">"):
            try:
                target_id = int(target[2:-1].replace("!", ""))
            except ValueError:
                pass
        if target_id is None:
            npc = database.get_npc(target)
            if npc:
                target_id = npc.id

        if target_id is None or target_id not in game.players or not game.is_player_alive(target_id):
            await interaction.response.send_message("Invalid target! Pick an alive player.", ephemeral=True)
            return
        if game.get_player_team(target_id) == "saboteur":
            await interaction.response.send_message("You can't kill a fellow saboteur!", ephemeral=True)
            return

        # Record kill vote
        game.night_kill_votes[interaction.user.id] = target_id
        database.save_game(game)

        # Get target name
        if target_id < 0:
            npc = database.get_npc_by_id(target_id)
            target_name = f"🤖 {npc.name}" if npc else f"NPC {target_id}"
        else:
            member = interaction.guild.get_member(target_id)
            target_name = member.display_name if member else f"<@{target_id}>"

        # Show vote status
        alive_sabs = [pid for pid in game.get_alive_players() if game.get_player_team(pid) == "saboteur" and pid > 0]
        voted_count = sum(1 for s in alive_sabs if s in game.night_kill_votes)
        total_sabs = len(alive_sabs)
        all_voted = voted_count == total_sabs and total_sabs > 0

        status = f"\n\n{'✅' if all_voted else '⏳'} **{voted_count}/{total_sabs}** saboteurs have voted"
        if all_voted:
            status += "\nAll votes in — any saboteur can run `/endnight` to execute the kill."

        sab_channel_id = game.team_channels.get("saboteurs")
        if sab_channel_id and interaction.channel.id == sab_channel_id:
            await interaction.response.send_message(f"🔪 Your kill target: **{target_name}**{status}")
        else:
            await interaction.response.send_message(f"🔪 Your kill target: **{target_name}**{status}", ephemeral=True)

    @app_commands.command(name="endnight", description="End the night phase and start the next day")
    async def endnight(self, interaction: discord.Interaction):
        """End night, execute kill, create next day. Saboteurs can run this once all have voted."""
        player_actions_cog = self.bot.get_cog('PlayerActions')
        if not player_actions_cog:
            await interaction.response.send_message("❌ PlayerActions cog not loaded!", ephemeral=True)
            return

        game, day = player_actions_cog.get_game_from_channel(interaction.channel.id)
        if not game:
            games = database.load_games()
            for g in games.values():
                if g.team_channels.get("saboteurs") == interaction.channel.id:
                    game = g
                    break

        if not game:
            await interaction.response.send_message("❌ Use this in a game channel.", ephemeral=True)
            return

        if game.phase != "night":
            await interaction.response.send_message("❌ It's not nighttime! Use `/endday` first.", ephemeral=True)
            return

        is_game_mod = permissions.can_run_game(interaction.user.id, game)
        is_saboteur = (
            permissions.is_player_in_game(interaction.user.id, game)
            and game.is_player_alive(interaction.user.id)
            and game.get_player_team(interaction.user.id) == "saboteur"
        )

        if not is_game_mod and not is_saboteur:
            await interaction.response.send_message("❌ Only the game creator, game mods, or saboteurs can end the night.", ephemeral=True)
            return

        # If saboteur, check all alive (real) saboteurs have voted
        if is_saboteur and not is_game_mod:
            alive_sabs = [pid for pid in game.get_alive_players() if game.get_player_team(pid) == "saboteur" and pid > 0]
            not_voted = [pid for pid in alive_sabs if pid not in game.night_kill_votes]
            if not_voted:
                names = [interaction.guild.get_member(pid).display_name if interaction.guild.get_member(pid) else f"<@{pid}>" for pid in not_voted]
                await interaction.response.send_message(
                    f"⏳ Not all saboteurs have voted yet.\nWaiting on: {', '.join(names)}",
                    ephemeral=True
                )
                return

        await interaction.response.defer()

        try:
            guild = interaction.guild
            current_day = game.current_day

            # Auto-vote for NPC saboteurs that haven't voted
            import random as _random
            alive_non_sab = [pid for pid in game.get_alive_players() if game.get_player_team(pid) != "saboteur"]
            npc_comments = [
                "This one looks suspicious...", "Easy target.", "They won't see it coming.",
                "Strategic choice.", "Let's do this.", "No mercy tonight.",
            ]
            sab_channel_id = game.team_channels.get("saboteurs")
            for pid in game.get_alive_players():
                if pid < 0 and game.get_player_team(pid) == "saboteur" and pid not in game.night_kill_votes:
                    if alive_non_sab:
                        pick = _random.choice(alive_non_sab)
                        game.night_kill_votes[pid] = pick
                        # Post a comment in saboteur channel
                        if sab_channel_id:
                            try:
                                npc = database.get_npc_by_id(pid)
                                npc_name = npc.name if npc else f"NPC {pid}"
                                if pick < 0:
                                    t_npc = database.get_npc_by_id(pick)
                                    t_name = f"🤖 {t_npc.name}" if t_npc else f"NPC {pick}"
                                else:
                                    member = guild.get_member(pick)
                                    t_name = member.display_name if member else f"<@{pick}>"
                                sab_ch = await self.bot.fetch_channel(sab_channel_id)
                                await sab_ch.send(f"🤖 **{npc_name}**: \"{_random.choice(npc_comments)}\" → /kill **{t_name}**")
                            except Exception:
                                pass

            # Resolve kill
            killed_id = game_logic.resolve_night_kill(game.night_kill_votes)

            # Get user names
            user_names = {}
            for player_id in game.players:
                if player_id < 0:
                    npc = database.get_npc_by_id(player_id)
                    user_names[player_id] = f"🤖 {npc.name}" if npc else f"🤖 NPC {player_id}"
                else:
                    member = guild.get_member(player_id)
                    user_names[player_id] = member.display_name if member else f"User {player_id}"

            # Reveal yesterday's vote elimination role
            from utils import roles as role_utils
            dawn_lines = []
            if game.last_vote_eliminated:
                ve_name = user_names.get(game.last_vote_eliminated, f"Player {game.last_vote_eliminated}")
                ve_role = game.roles.get(game.last_vote_eliminated, "Unknown")
                ve_info = role_utils.get_role_info(ve_role)
                dawn_lines.append(f"**{ve_name}**'s role revealed: {ve_info.get('emoji', '')} **{ve_role}**")
                game.last_vote_eliminated = None

            # Execute night kill
            kill_announcement = ""
            if killed_id:
                game.eliminate_player(killed_id)
                killed_name = user_names.get(killed_id, f"Player {killed_id}")
                killed_role = game.roles.get(killed_id, "Unknown")
                role_info = role_utils.get_role_info(killed_role)
                role_emoji = role_info.get('emoji', '')
                dawn_lines.append(
                    f"**{killed_name}** was found dead...\n"
                    f"They were: {role_emoji} **{killed_role}**"
                )

                # Handle dead player Discord roles
                if killed_id > 0:
                    from utils import role_manager
                    dead_role_id = game.discord_roles.get("dead")
                    player_role_id = game.discord_roles.get("player")
                    if dead_role_id:
                        await role_manager.assign_player_role(guild, killed_id, dead_role_id)
                    if player_role_id:
                        await role_manager.remove_player_role(guild, killed_id, player_role_id)

                    # Give access to dead channel
                    dead_channel_id = game.team_channels.get("dead")
                    if dead_channel_id:
                        try:
                            dead_ch = await self.bot.fetch_channel(dead_channel_id)
                            member = await guild.fetch_member(killed_id)
                            await dead_ch.set_permissions(member, view_channel=True, send_messages=False)
                        except Exception:
                            pass
            else:
                dawn_lines.append("The night passes quietly... no one was killed.")

            kill_announcement = "\n\n".join(dawn_lines) if dawn_lines else "A new day begins."

            # Check win condition
            win_team = game_logic.check_win_condition(game.get_alive_players(), game.roles, game.settings)
            if win_team:
                game.end_game()
                database.save_game(game)
                # Reuse existing win handling - post result and return
                # (simplified - post the kill + win embed)
                from utils import roles as role_utils
                if win_team == "crew":
                    title = "🏆 Crew Victory!"
                    color = discord.Color.blue()
                elif win_team == "saboteur":
                    title = "🔴 Saboteur Victory!"
                    color = discord.Color.red()
                else:
                    title = "🏁 Game Over!"
                    color = discord.Color.red()

                embed = discord.Embed(title=title, description=kill_announcement, color=color)
                await interaction.followup.send(embed=embed)
                return

            # Transition to day - create next day threads
            next_day = current_day + 1
            game.phase = "day"
            game.night_kill_votes = {}
            game.current_day = next_day
            from datetime import datetime, timezone
            game.day_started_at = datetime.now(timezone.utc).isoformat()

            mod_role = discord.utils.get(guild.roles, name=permissions.MODERATOR_ROLE_NAME)
            bot_member = guild.get_member(self.bot.user.id)
            discussions_forum, voting_forum = await forum_manager.get_or_create_game_forums(
                guild, mod_role=mod_role, bot_member=bot_member
            )

            # Build alive list
            alive_mention_parts = []
            for pid in game.get_alive_players():
                if pid > 0:
                    alive_mention_parts.append(f"<@{pid}>")
                else:
                    npc = database.get_npc_by_id(pid)
                    alive_mention_parts.append(f"🤖 {npc.name}" if npc else f"🤖 NPC {pid}")
            alive_mentions = ", ".join(alive_mention_parts)

            # Create discussion thread
            discussion_embed = discord.Embed(
                title=f"💬 {game.name} - Day {next_day} Discussion",
                description="Discuss and strategize here!",
                color=discord.Color.blue()
            )
            discussion_thread = await discussions_forum.create_thread(
                name=f"💬 {game.name} - Day {next_day}",
                content=f"**Day {next_day} Discussion for {game.name}**",
                embed=discussion_embed
            )
            welcome_msg = await discussion_thread.thread.send(
                f"**Day {next_day} — {game.name}**\n\n"
                f"{kill_announcement}\n\n"
                f"Alive: {alive_mentions}\n\nUse `/vote` to cast your vote."
            )
            try:
                await welcome_msg.pin()
            except discord.Forbidden:
                pass

            # Create voting thread
            vote_embed = discord.Embed(
                title=f"📊 Day {next_day} Votes - {game.name}",
                description=f"No votes yet. Use `/vote @player` or `/vote Abstain`\n\n"
                            f"💬 Discussion: {discussion_thread.thread.mention}",
                color=discord.Color.blue()
            )
            voting_thread = await voting_forum.create_thread(
                name=f"🗳️ {game.name} - Day {next_day}",
                content=f"**Day {next_day} Voting for {game.name}**",
                embed=vote_embed
            )
            try:
                vote_welcome = await voting_thread.thread.send(
                    f"**Vote tracking for {game.name} - Day {next_day}**\n\n"
                    f"Alive: {alive_mentions}\n\n"
                    f"Votes will appear below as a ledger. The tally above updates live.\n"
                    f"📌 Click the pins icon to jump back to the tally."
                )
                await vote_welcome.pin()
            except discord.Forbidden:
                pass

            # Invite players + MC
            users_to_add = set(pid for pid in game.get_alive_players() if pid > 0)
            users_to_add.add(game.creator_id)
            for user_id in users_to_add:
                try:
                    await discussion_thread.thread.add_user(discord.Object(id=user_id))
                    await voting_thread.thread.add_user(discord.Object(id=user_id))
                except Exception:
                    pass

            # Save game state
            game.channels[next_day] = {
                "votes_channel_id": voting_thread.thread.id,
                "discussion_channel_id": discussion_thread.thread.id,
                "votes_message_id": voting_thread.message.id
            }
            database.save_game(game)

            # Dawn announcement
            dawn_embed = discord.Embed(
                title=f"🌅 {game.name} — Day {next_day}",
                description=(
                    f"{kill_announcement}\n\n"
                    f"**Alive ({len(game.get_alive_players())}):** {alive_mentions}\n\n"
                    f"💬 Discussion: {discussion_thread.thread.mention}\n"
                    f"🗳️ Votes: {voting_thread.thread.mention}"
                ),
                color=discord.Color.gold()
            )
            await interaction.followup.send(embed=dawn_embed)

            # DM alive players
            for player_id in game.get_alive_players():
                if player_id < 0:
                    continue
                try:
                    user = await self.bot.fetch_user(player_id)
                    dm_embed = discord.Embed(
                        title=f"🌅 {game.name} — Day {next_day}",
                        description=kill_announcement,
                        color=discord.Color.gold()
                    )
                    dm_embed.add_field(
                        name="Channels",
                        value=f"💬 Discussion: {discussion_thread.thread.mention}\n"
                              f"🗳️ Votes: {voting_thread.thread.mention}",
                        inline=False
                    )
                    await user.send(embed=dm_embed)
                except Exception:
                    pass

        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Failed to end night: {e}")

    def _find_game_from_channel(self, channel_id: int):
        """Find a game from a channel ID using the PlayerActions cog."""
        player_actions_cog = self.bot.get_cog('PlayerActions')
        if player_actions_cog:
            return player_actions_cog.get_game_from_channel(channel_id)
        return None, None

    # --- Game Settings ---

    SETTING_LABELS = {
        "player_say_enabled": "Player /say",
    }

    # --- Game Panel ---

    @app_commands.command(name="panel", description="View game overview panel (Moderator only)")
    async def panel(self, interaction: discord.Interaction):
        """Show a comprehensive game state overview for moderators."""
        game, day = self._find_game_from_channel(interaction.channel.id)

        if not game:
            await interaction.response.send_message(
                "This channel is not a game channel!",
                ephemeral=True
            )
            return

        if not permissions.can_manage_game(interaction.user.id, interaction.user, game):
            await interaction.response.send_message(
                "You don't have permission to view this game's panel!",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Game Panel - {game.name}",
            color=discord.Color.blue()
        )

        # Status
        status_text = game.status.value.capitalize()
        if game.status == GameStatus.ACTIVE:
            status_text += f" (Day {game.current_day})"
        embed.add_field(name="Status", value=status_text, inline=True)
        embed.add_field(name="Creator", value=f"<@{game.creator_id}>", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)  # spacer

        # Players
        alive = game.get_alive_players()
        dead = game.eliminated_players
        player_lines = []
        for pid in game.players:
            if pid < 0:
                npc = database.get_npc_by_id(pid)
                name = f"\U0001f916 {npc.name}" if npc else f"\U0001f916 NPC {pid}"
            else:
                name = f"<@{pid}>"
            status = "\U0001f480" if pid in dead else "\u2705"
            role_name = game.roles.get(pid, "")
            role_suffix = f" ({role_name})" if role_name else ""
            player_lines.append(f"{status} {name}{role_suffix}")

        embed.add_field(
            name=f"Players ({len(alive)} alive / {len(dead)} dead)",
            value="\n".join(player_lines) if player_lines else "None",
            inline=False
        )

        # Current day votes
        if game.status == GameStatus.ACTIVE:
            current_votes = game.votes.get(game.current_day, {})
            if current_votes:
                vote_lines = []
                for voter_id, target in current_votes.items():
                    if isinstance(target, str):
                        target_name = target
                    elif target < 0:
                        npc = database.get_npc_by_id(target)
                        target_name = f"\U0001f916 {npc.name}" if npc else f"NPC {target}"
                    else:
                        target_name = f"<@{target}>"
                    voter_name = f"<@{voter_id}>" if voter_id > 0 else f"\U0001f916 NPC"
                    vote_lines.append(f"{voter_name} \u2192 {target_name}")
                embed.add_field(
                    name=f"Day {game.current_day} Votes ({len(current_votes)})",
                    value="\n".join(vote_lines),
                    inline=False
                )
            else:
                embed.add_field(name=f"Day {game.current_day} Votes", value="No votes yet", inline=False)

        # Settings
        settings_lines = []
        for key, label in self.SETTING_LABELS.items():
            val = game.settings.get(key, "N/A")
            display = "Enabled" if val is True else "Disabled" if val is False else str(val)
            settings_lines.append(f"{label}: {display}")
        embed.add_field(
            name="Settings",
            value="\n".join(settings_lines) if settings_lines else "Default",
            inline=False
        )

        # NPCs in game
        npc_ids = [pid for pid in game.players if pid < 0]
        if npc_ids:
            npc_names = []
            for npc_id in npc_ids:
                npc = database.get_npc_by_id(npc_id)
                if npc:
                    status = "\U0001f480" if npc_id in dead else "\u2705"
                    npc_names.append(f"{status} {npc.name}")
            embed.add_field(name=f"NPCs ({len(npc_ids)})", value="\n".join(npc_names), inline=False)

        embed.set_footer(text="Use /settings to modify game configuration")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Server Configuration ---

    def _build_configure_embed(self) -> discord.Embed:
        """Build the configure panel embed showing current state."""
        config = server_config.load_config()
        lobby_id = config.get("lobby_forum_id")
        disc_id = config.get("discussions_forum_id")
        vote_id = config.get("voting_forum_id")

        embed = discord.Embed(
            title="Server Configuration Panel",
            description=(
                "Configure which forum channels CSS Solaris uses.\n"
                "Click a button below to change a setting, or use the dropdown to pick a forum channel."
            ),
            color=discord.Color.blue()
        )

        lobby_val = f"<#{lobby_id}>" if lobby_id else "Not set"
        disc_val = f"<#{disc_id}>" if disc_id else "Not set"
        vote_val = f"<#{vote_id}>" if vote_id else "Not set"

        embed.add_field(name="Lobby Forum", value=f"{lobby_val}\n*Where new games are created*", inline=False)
        embed.add_field(name="Discussions Forum", value=f"{disc_val}\n*Daily discussion threads go here*", inline=False)
        embed.add_field(name="Voting Forum", value=f"{vote_val}\n*Vote tally threads (read-only for players)*", inline=False)

        all_set = all([lobby_id, disc_id, vote_id])
        if all_set:
            embed.set_footer(text="All forums configured! You're ready to create games.")
        else:
            embed.set_footer(text="Set all three forums to get started. Run /setup to auto-create them.")

        return embed

    @app_commands.command(name="configure", description="Open the server configuration panel (Admin only)")
    async def configure(self, interaction: discord.Interaction):
        """Show the interactive configuration panel."""
        if not permissions.is_admin(interaction.user):
            await interaction.response.send_message(
                "Only server admins can use /configure!",
                ephemeral=True
            )
            return

        # If in a game channel, also show game settings
        game, day = self._find_game_from_channel(interaction.channel.id)
        embed = self._build_configure_embed()
        view = ConfigureView(self, game)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # --- Per-Game Moderator Management ---

    @app_commands.command(name="mod", description="Add or remove a game moderator")
    @app_commands.describe(
        action="add, remove, or list",
        user="The user to add/remove as mod"
    )
    async def mod(self, interaction: discord.Interaction, action: str, user: discord.Member = None):
        """Manage per-game moderators."""
        game, day = self._find_game_from_channel(interaction.channel.id)

        usage_embed = discord.Embed(
            title="How to use /mod",
            description=(
                "**/mod list** - See who can manage this game\n"
                "**/mod add @user** - Give someone mod access to this game\n"
                "**/mod remove @user** - Remove someone's mod access\n\n"
                "*Use this command inside a game channel (signup, discussion, or voting thread).*"
            ),
            color=discord.Color.greyple()
        )

        if not game:
            await interaction.response.send_message(embed=usage_embed, ephemeral=True)
            return

        action_lower = action.lower()

        if action_lower not in ("add", "remove", "list"):
            await interaction.response.send_message(embed=usage_embed, ephemeral=True)
            return

        if action_lower == "list":
            embed = discord.Embed(title=f"Moderators - {game.name}", color=discord.Color.blue())
            embed.add_field(name="Creator", value=f"<@{game.creator_id}>", inline=False)
            if game.moderators:
                mod_mentions = "\n".join(f"<@{mid}>" for mid in game.moderators)
                embed.add_field(name="Added Mods", value=mod_mentions, inline=False)
            else:
                embed.add_field(name="Added Mods", value="None - use `/mod add @user` to add", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if not permissions.can_manage_game(interaction.user.id, interaction.user, game):
            await interaction.response.send_message(
                "You don't have permission to manage mods for this game!\n"
                "Only the game creator or existing mods can do this.",
                ephemeral=True
            )
            return

        if user is None:
            await interaction.response.send_message(
                f"You need to specify a user!\nExample: `/mod {action_lower} @someone`",
                ephemeral=True
            )
            return

        if action_lower == "add":
            if user.id == game.creator_id:
                await interaction.response.send_message("The game creator is already a mod!", ephemeral=True)
                return
            if user.id in game.moderators:
                await interaction.response.send_message(f"{user.mention} is already a mod for this game!", ephemeral=True)
                return
            game.moderators.append(user.id)
            database.save_game(game)
            await interaction.response.send_message(f"{user.mention} has been added as a mod for **{game.name}**.")

        elif action_lower == "remove":
            if user.id not in game.moderators:
                await interaction.response.send_message(
                    f"{user.mention} is not a mod for this game!\nUse `/mod list` to see current mods.",
                    ephemeral=True
                )
                return
            game.moderators.remove(user.id)
            database.save_game(game)
            await interaction.response.send_message(f"{user.mention} has been removed as a mod for **{game.name}**.")

    # --- Purge ---

    @app_commands.command(name="purge", description="Delete all games and threads (iron_helmet_games only)")
    async def purge(self, interaction: discord.Interaction):
        """Wipe all game data and Discord threads."""
        if interaction.user.name.lower() != "iron_helmet_games":
            await interaction.response.send_message("Only iron_helmet_games can use this command.", ephemeral=True)
            return

        game_count = len(database.load_games())
        embed = discord.Embed(
            title="Purge All Game Data?",
            description=(
                f"This will **permanently delete**:\n"
                f"- **{game_count}** game(s) from the database\n"
                f"- **All** forum threads in Lobby, Discussions, and Voting\n\n"
                f"This cannot be undone."
            ),
            color=discord.Color.red()
        )
        view = PurgeConfirmView(self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # --- Sync Commands ---

    @app_commands.command(name="sync", description="Clear old commands and re-sync (Admin only)")
    async def sync(self, interaction: discord.Interaction):
        """Clear and re-sync all slash commands for this guild."""
        if not permissions.is_admin(interaction.user):
            await interaction.response.send_message("Only server admins can use this command!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild

            # Step 1: Clear global commands (removes duplicates)
            self.bot.tree.clear_commands(guild=None)
            await self.bot.tree.sync()  # Push empty global list to Discord

            # Step 2: Sync to guild only
            self.bot.tree.copy_global_to(guild=guild)
            synced = await self.bot.tree.sync(guild=guild)

            await interaction.followup.send(f"Synced **{len(synced)}** commands. Global duplicates cleared!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Failed to sync commands: {e}", ephemeral=True)


# --- UI Components for /configure ---

class ForumChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, setting_key: str, setting_label: str, cog):
        super().__init__(
            placeholder=f"Select a forum for {setting_label}...",
            channel_types=[discord.ChannelType.forum],
            min_values=1, max_values=1,
        )
        self.setting_key = setting_key
        self.cog = cog
        self.game = None

    async def callback(self, interaction: discord.Interaction):
        server_config.set(self.setting_key, self.values[0].id)
        embed = self.cog._build_configure_embed()
        view = ConfigureView(self.cog, self.game)
        await interaction.response.edit_message(embed=embed, view=view)


class GameSettingToggle(discord.ui.Button):
    def __init__(self, game, setting_key: str, label: str, cog):
        self.game = game
        self.setting_key = setting_key
        self.cog = cog
        current = game.settings.get(setting_key, False)
        super().__init__(
            label=f"{label}: {'ON' if current else 'OFF'}",
            style=discord.ButtonStyle.green if current else discord.ButtonStyle.red,
            row=3,
        )

    async def callback(self, interaction: discord.Interaction):
        # Toggle the setting
        current = self.game.settings.get(self.setting_key, False)
        self.game.settings[self.setting_key] = not current
        database.save_game(self.game)
        # Rebuild
        embed = self.cog._build_configure_embed()
        view = ConfigureView(self.cog, self.game)
        await interaction.response.edit_message(embed=embed, view=view)


class ConfigureView(discord.ui.View):
    def __init__(self, cog, game=None):
        super().__init__(timeout=300)
        self.cog = cog
        self.game = game

        # Server forum selectors (rows 0-2)
        lobby_select = ForumChannelSelect("lobby_forum_id", "Lobby", cog)
        lobby_select.game = game
        disc_select = ForumChannelSelect("discussions_forum_id", "Discussions", cog)
        disc_select.game = game
        vote_select = ForumChannelSelect("voting_forum_id", "Voting", cog)
        vote_select.game = game
        self.add_item(lobby_select)
        self.add_item(disc_select)
        self.add_item(vote_select)

        # Game settings toggles (row 3) - only if in a game channel
        if game:
            self.add_item(GameSettingToggle(game, "player_say_enabled", "Player /say", cog))

    @discord.ui.button(label="Auto-Setup All", style=discord.ButtonStyle.blurple, row=4)
    async def auto_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        guild = interaction.guild
        mod_role = discord.utils.get(guild.roles, name=permissions.MODERATOR_ROLE_NAME)
        bot_member = guild.get_member(interaction.client.user.id)
        await forum_manager.get_or_create_lobby_forum(guild)
        await forum_manager.get_or_create_game_forums(guild, mod_role=mod_role, bot_member=bot_member)
        embed = self.cog._build_configure_embed()
        view = ConfigureView(self.cog, self.game)
        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, row=4)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.cog._build_configure_embed()
        view = ConfigureView(self.cog, self.game)
        await interaction.response.edit_message(embed=embed, view=view)


class PurgeConfirmView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=120)
        self.bot = bot

    @discord.ui.button(label="Confirm Purge", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(title="Purging...", description="Deleting threads, roles, and categories...", color=discord.Color.orange()),
            view=None
        )

        deleted = []
        guild = interaction.guild
        config = server_config.load_config()
        forum_ids = [
            config.get("lobby_forum_id"),
            config.get("discussions_forum_id"),
            config.get("voting_forum_id"),
        ]

        for fid in forum_ids:
            if not fid:
                continue
            forum = guild.get_channel(fid)
            if not isinstance(forum, discord.ForumChannel):
                continue
            for thread in forum.threads:
                try:
                    await thread.delete()
                    deleted.append(thread.name)
                except Exception:
                    pass
            async for thread in forum.archived_threads():
                try:
                    await thread.delete()
                    deleted.append(thread.name)
                except Exception:
                    pass

        # Clean up game roles
        from utils import role_manager
        roles_deleted = await role_manager.cleanup_all_game_roles(guild)

        # Clean up game categories
        categories_deleted = await forum_manager.cleanup_all_game_categories(guild)

        # Clear games database
        database.save_games({})

        await interaction.edit_original_response(
            embed=discord.Embed(
                title="Purge Complete",
                description=f"Deleted **{len(deleted)}** threads, **{roles_deleted}** roles, **{categories_deleted}** categories, and cleared all game data.",
                color=discord.Color.green()
            ),
            view=None
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(title="Purge Cancelled", color=discord.Color.greyple()),
            view=None
        )


async def setup(bot):
    """Setup function for cog."""
    await bot.add_cog(Moderator(bot))
