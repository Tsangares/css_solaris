"""
Forum Manager utilities for CSS Solaris.
Handles creation and management of forum channels.
"""

import discord
from typing import Tuple
from utils import server_config


MAIN_CATEGORY_NAME = "CSS SOLARIS"
LOBBY_FORUM_NAME = "Game Lobby"
DISCUSSIONS_FORUM_NAME = "Game Discussions"
VOTING_FORUM_NAME = "Game Voting"


def _find_forum_by_name(guild: discord.Guild, name: str) -> discord.ForumChannel:
    """Find a forum channel by name (case-insensitive, handles dash formatting)."""
    target = name.lower()
    for channel in guild.channels:
        if isinstance(channel, discord.ForumChannel):
            if channel.name.lower() in (target, target.replace(" ", "-")):
                return channel
    return None


async def get_or_create_main_category(guild: discord.Guild) -> discord.CategoryChannel:
    """Get or create the main CSS Solaris category for forums."""
    configured_id = server_config.get("main_category_id")
    if configured_id:
        channel = guild.get_channel(configured_id)
        if isinstance(channel, discord.CategoryChannel):
            return channel

    # Find by name
    for cat in guild.categories:
        if cat.name.upper() == MAIN_CATEGORY_NAME:
            server_config.set("main_category_id", cat.id)
            return cat

    # Create
    category = await guild.create_category(
        name=MAIN_CATEGORY_NAME,
        reason="CSS Solaris main category"
    )
    server_config.set("main_category_id", category.id)
    return category


async def get_or_create_lobby_forum(guild: discord.Guild) -> discord.ForumChannel:
    """Get or create the Game Lobby forum channel under the main category."""
    # Check config first
    configured_id = server_config.get("lobby_forum_id")
    if configured_id:
        channel = guild.get_channel(configured_id)
        if isinstance(channel, discord.ForumChannel):
            return channel

    # Fall back to name-based lookup
    forum = _find_forum_by_name(guild, LOBBY_FORUM_NAME)
    if forum:
        server_config.set("lobby_forum_id", forum.id)
        return forum

    # Create under main category
    category = await get_or_create_main_category(guild)
    forum = await guild.create_forum(
        name=LOBBY_FORUM_NAME,
        topic="Create and join CSS Solaris games here!",
        category=category
    )
    server_config.set("lobby_forum_id", forum.id)
    return forum


async def get_or_create_game_forums(
    guild: discord.Guild,
    mod_role: discord.Role = None,
    bot_member: discord.Member = None
) -> Tuple[discord.ForumChannel, discord.ForumChannel]:
    """
    Get or create the Game Discussions and Game Voting forum channels.

    Args:
        guild: Discord guild
        mod_role: Optional moderator role (for setting permissions on voting forum)
        bot_member: Optional bot member (for setting permissions on voting forum)

    Returns:
        Tuple of (discussions_forum, voting_forum)
    """
    discussions_forum = None
    voting_forum = None

    # Check config first
    config = server_config.load_config()
    disc_id = config.get("discussions_forum_id")
    vote_id = config.get("voting_forum_id")

    if disc_id:
        ch = guild.get_channel(disc_id)
        if isinstance(ch, discord.ForumChannel):
            discussions_forum = ch
    if vote_id:
        ch = guild.get_channel(vote_id)
        if isinstance(ch, discord.ForumChannel):
            voting_forum = ch

    # Fall back to name-based lookup
    if not discussions_forum:
        discussions_forum = _find_forum_by_name(guild, DISCUSSIONS_FORUM_NAME)
    if not voting_forum:
        voting_forum = _find_forum_by_name(guild, VOTING_FORUM_NAME)

    # Create missing forums under main category
    category = await get_or_create_main_category(guild)

    if not discussions_forum:
        discussions_forum = await guild.create_forum(
            name=DISCUSSIONS_FORUM_NAME,
            topic="Daily discussions for active CSS Solaris games",
            category=category
        )

    if not voting_forum:
        # Set up permissions for voting forum (read-only for everyone)
        overwrites = {}

        # Allow @everyone to view but not post (read-only)
        overwrites[guild.default_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False,
            send_messages_in_threads=False,
            create_public_threads=False
        )

        # Allow moderators to view (but not send messages - read-only)
        if mod_role:
            overwrites[mod_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,
                send_messages_in_threads=False,
                create_public_threads=False
            )

        # Allow bot to view, post, and post in threads
        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                send_messages_in_threads=True,
                create_public_threads=True,
                manage_threads=True,
                manage_messages=True
            )

        voting_forum = await guild.create_forum(
            name=VOTING_FORUM_NAME,
            topic="Vote tallies for active CSS Solaris games (Read-only - only bot can post)",
            overwrites=overwrites,
            category=category
        )
    else:
        # Update permissions on existing voting forum if needed
        if mod_role or bot_member:
            overwrites = {}

            # Allow @everyone to view but not post (read-only)
            overwrites[guild.default_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=False,
                send_messages_in_threads=False,
                create_public_threads=False
            )

            # Allow moderators to view (but not send messages - read-only)
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=False,
                    send_messages_in_threads=False,
                    create_public_threads=False
                )

            # Allow bot to view, post, and post in threads
            if bot_member:
                overwrites[bot_member] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    send_messages_in_threads=True,
                    create_public_threads=True,
                    manage_threads=True,
                    manage_messages=True
                )

            await voting_forum.edit(overwrites=overwrites)

    # Persist discovered/created IDs to config
    server_config.set("discussions_forum_id", discussions_forum.id)
    server_config.set("voting_forum_id", voting_forum.id)

    return discussions_forum, voting_forum


GAME_CATEGORY_PREFIX = "🎮 "


async def create_private_channels(
    guild: discord.Guild,
    game_name: str,
    mod_role: discord.Role = None,
    bot_member: discord.Member = None,
    creator_id: int = None
) -> Tuple[discord.CategoryChannel, discord.TextChannel, discord.TextChannel, discord.TextChannel]:
    """
    Create a game category with MC booth, saboteur, and dead channels.

    Returns:
        Tuple of (category, mc_channel, saboteur_channel, dead_channel)
    """
    # Create category (hidden from @everyone)
    category_overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False)
    }
    if mod_role:
        category_overwrites[mod_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False
        )
    if bot_member:
        category_overwrites[bot_member] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            manage_messages=True
        )

    category = await guild.create_category(
        name=f"{GAME_CATEGORY_PREFIX}{game_name}",
        overwrites=category_overwrites,
        reason=f"CSS Solaris game category for {game_name}"
    )

    # MC booth (creator + bot + mods only)
    mc_overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False)
    }
    if bot_member:
        mc_overwrites[bot_member] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_messages=True
        )
    if mod_role:
        mc_overwrites[mod_role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True
        )
    if creator_id:
        creator_member = guild.get_member(creator_id)
        if creator_member:
            mc_overwrites[creator_member] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True
            )

    mc_channel = await guild.create_text_channel(
        name=f"🎭-mc-booth",
        topic=f"MC workspace for {game_name}. Plan events, draft narration, manage the game.",
        category=category,
        overwrites=mc_overwrites,
        reason=f"CSS Solaris MC channel for {game_name}"
    )

    mc_embed = discord.Embed(
        title=f"🎭 {game_name} — MC Booth",
        description="Welcome, MC! This is your private workspace. Players can't see this channel.",
        color=discord.Color.purple()
    )
    mc_embed.add_field(
        name="📜 Game Flow",
        value=(
            "1. **Day Phase** — Players discuss and `/vote` to eliminate someone\n"
            "2. **`/endday`** — Tallies votes, eliminates the player (role hidden until dawn), night begins\n"
            "3. **Night Phase** — Discussion locked. Saboteurs use `/kill` in their private channel to pick a target. Majority vote wins, random on ties\n"
            "4. **`/endnight`** — Executes the kill, reveals yesterday's voted player's role, creates the next day\n"
            "5. Repeat until crew or saboteurs win"
        ),
        inline=False
    )
    mc_embed.add_field(
        name="🎭 MC Commands",
        value=(
            "- `/narrate <text>` — quick styled narration to discussion\n"
            "- `/narrate <message link>` — forward a rich message with images\n"
            "- `/say <message>` / `/say <message> as_npc:<name>` — bot or NPC speech\n"
            "- `/smite @player \"reason\"` — instantly eliminate a player\n"
            "- `/revive @player` — bring a dead player back\n"
            "- `/protect @player` — shield from death tonight (night only)\n"
            "- `/unprotect @player` — remove protection\n"
            "- `/lock` / `/unlock` — lock/unlock the current thread\n"
            "- `/endday` / `/endnight` — advance game phases\n"
            "- `/mod add @user` — give someone game mod access\n"
            "- `/panel` — view full game state overview"
        ),
        inline=False
    )
    mc_embed.add_field(
        name="⚙️ How Night Kill + Protection Works",
        value=(
            "During night, alive saboteurs use `/kill @player` in their channel (majority vote, random on tie). "
            "NPC saboteurs auto-vote when `/endnight` runs.\n\n"
            "**Deferred kills:** The vote elimination from `/endday` is NOT instant — the player is queued for death "
            "and actually dies at dawn when `/endnight` runs. This gives you time to `/protect` them.\n\n"
            "**`/protect @player`** — shields them from BOTH the vote kill and the night kill. "
            "The dawn announcement will say they were mysteriously saved."
        ),
        inline=False
    )
    mc_embed.add_field(
        name="🏆 Win Conditions (configurable)",
        value=(
            "**Crew wins** when: all saboteurs eliminated *(default)*\n"
            "**Saboteurs win** when: they control ≥50% of alive players *(default)*\n"
            "**Saboteur ratio**: ~33% of players *(default)*\n\n"
            "Change these with `/configure` before starting the game."
        ),
        inline=False
    )
    mc_embed.add_field(
        name="⏰ Timers",
        value=(
            "A 24h timer runs for both day and night. When it expires:\n"
            "- Day: discussion auto-locks (you still run `/endday`)\n"
            "- Night: unvoted saboteurs auto-pick random targets\n"
            "Configure with `/configure` → day_duration_hours"
        ),
        inline=False
    )
    await mc_channel.send(embed=mc_embed)

    # Saboteur channel under category
    saboteur_channel = await guild.create_text_channel(
        name=f"🔴-saboteurs",
        topic=f"Private channel for {game_name} saboteurs to coordinate.",
        category=category,
        reason=f"CSS Solaris saboteur channel for {game_name}"
    )

    # Dead channel under category
    dead_channel = await guild.create_text_channel(
        name=f"💀-afterlife",
        topic=f"Eliminated players from {game_name} spectate here.",
        category=category,
        reason=f"CSS Solaris afterlife channel for {game_name}"
    )

    # Welcome messages
    saboteur_embed = discord.Embed(
        title=f"🔴 {game_name} - Saboteur Channel",
        description=(
            "Welcome, saboteurs! This is your private coordination channel.\n\n"
            "**Your Goal:** Eliminate crew members until you control ≥50% of the ship.\n\n"
            "**Strategy Tips:**\n"
            "• Don't all vote the same way - it looks suspicious!\n"
            "• Spread out accusations to create chaos\n"
            "• Defend each other subtly, but not too obviously\n"
            "• If one saboteur is caught, the rest should act shocked\n\n"
            "Good luck! 🔪"
        ),
        color=discord.Color.red()
    )
    await saboteur_channel.send(embed=saboteur_embed)

    dead_embed = discord.Embed(
        title=f"💀 {game_name} - Afterlife",
        description=(
            "Welcome to the afterlife! This channel is for eliminated players.\n\n"
            "You can watch the game continue, but please don't reveal information to living players!\n\n"
            "Enjoy spectating! 👻"
        ),
        color=discord.Color.dark_gray()
    )
    await dead_channel.send(embed=dead_embed)

    return category, mc_channel, saboteur_channel, dead_channel


async def cleanup_game_category(guild: discord.Guild, category_id: int):
    """Delete a game category and all its channels."""
    try:
        category = guild.get_channel(category_id)
        if isinstance(category, discord.CategoryChannel):
            for channel in category.channels:
                try:
                    await channel.delete(reason="CSS Solaris game ended")
                except Exception:
                    pass
            await category.delete(reason="CSS Solaris game ended")
    except Exception:
        pass


async def cleanup_all_game_categories(guild: discord.Guild) -> int:
    """Delete ALL CSS Solaris game categories. Returns count deleted."""
    deleted = 0
    for category in guild.categories:
        if category.name.startswith(GAME_CATEGORY_PREFIX):
            for channel in category.channels:
                try:
                    await channel.delete(reason="CSS Solaris purge")
                except Exception:
                    pass
            try:
                await category.delete(reason="CSS Solaris purge")
                deleted += 1
            except Exception:
                pass
    return deleted
