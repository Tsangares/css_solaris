"""
Forum Manager utilities for CSS Solaris.
Handles creation and management of forum channels.
"""

import discord
from typing import Tuple


LOBBY_FORUM_NAME = "Game Lobby"
DISCUSSIONS_FORUM_NAME = "Game Discussions"
VOTING_FORUM_NAME = "Game Voting"


async def get_or_create_lobby_forum(guild: discord.Guild) -> discord.ForumChannel:
    """
    Get or create the Game Lobby forum channel.

    Args:
        guild: Discord guild

    Returns:
        ForumChannel for game lobbies
    """
    # Try to find existing forum (case-insensitive, handles Discord's auto-formatting)
    target_name_lower = LOBBY_FORUM_NAME.lower()
    for channel in guild.channels:
        if isinstance(channel, discord.ForumChannel):
            # Match both "Game Lobby" and "game-lobby" style names
            if channel.name.lower() == target_name_lower or channel.name.lower() == target_name_lower.replace(" ", "-"):
                return channel

    # Create new forum
    forum = await guild.create_forum(
        name=LOBBY_FORUM_NAME,
        topic="Create and join CSS Solaris games here!"
    )
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

    # Normalize names for comparison
    discussions_name_lower = DISCUSSIONS_FORUM_NAME.lower()
    voting_name_lower = VOTING_FORUM_NAME.lower()

    # Try to find existing forums (case-insensitive, handles Discord's auto-formatting)
    for channel in guild.channels:
        if isinstance(channel, discord.ForumChannel):
            channel_name_lower = channel.name.lower()

            # Match both "Game Discussions" and "game-discussions" style names
            if (channel_name_lower == discussions_name_lower or
                channel_name_lower == discussions_name_lower.replace(" ", "-")):
                discussions_forum = channel
            elif (channel_name_lower == voting_name_lower or
                  channel_name_lower == voting_name_lower.replace(" ", "-")):
                voting_forum = channel

    # Create missing forums
    if not discussions_forum:
        discussions_forum = await guild.create_forum(
            name=DISCUSSIONS_FORUM_NAME,
            topic="Daily discussions for active CSS Solaris games"
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

        # Allow bot to view and post
        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                create_public_threads=True,
                manage_threads=True
            )

        voting_forum = await guild.create_forum(
            name=VOTING_FORUM_NAME,
            topic="Vote tallies for active CSS Solaris games (Read-only - only bot can post)",
            overwrites=overwrites
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

            # Allow bot to view and post
            if bot_member:
                overwrites[bot_member] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    create_public_threads=True,
                    manage_threads=True
                )

            await voting_forum.edit(overwrites=overwrites)

    return discussions_forum, voting_forum


async def create_private_channels(
    guild: discord.Guild,
    game_name: str,
    mod_role: discord.Role = None,
    bot_member: discord.Member = None
) -> Tuple[discord.TextChannel, discord.TextChannel]:
    """
    Create private channels for saboteurs and dead players.

    Args:
        guild: Discord guild
        game_name: Name of the game
        mod_role: Optional moderator role
        bot_member: Optional bot member

    Returns:
        Tuple of (saboteur_channel, dead_channel)
    """
    # Saboteur Channel (private, saboteurs only + mods + bot)
    saboteur_overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False)
    }

    # Moderators can view (read-only)
    if mod_role:
        saboteur_overwrites[mod_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False
        )

    # Bot can view and post
    if bot_member:
        saboteur_overwrites[bot_member] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_messages=True
        )

    saboteur_channel = await guild.create_text_channel(
        name=f"🔴-{game_name.lower().replace(' ', '-')}-saboteurs",
        topic=f"Private channel for {game_name} saboteurs to coordinate. Mods can view but not send.",
        overwrites=saboteur_overwrites,
        reason=f"CSS Solaris saboteur channel for {game_name}"
    )

    # Dead Channel (read-only for dead players, mods can post)
    dead_overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False)
    }

    # Moderators can view and post
    if mod_role:
        dead_overwrites[mod_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True
        )

    # Bot can view and post
    if bot_member:
        dead_overwrites[bot_member] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_messages=True
        )

    dead_channel = await guild.create_text_channel(
        name=f"💀-{game_name.lower().replace(' ', '-')}-afterlife",
        topic=f"Eliminated players from {game_name} can watch here. Read-only for dead players.",
        overwrites=dead_overwrites,
        reason=f"CSS Solaris afterlife channel for {game_name}"
    )

    # Send welcome messages
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

    return saboteur_channel, dead_channel
