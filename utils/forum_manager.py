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
        # Set up permissions for voting forum (hidden from @everyone)
        overwrites = {}

        # Hide from @everyone
        overwrites[guild.default_role] = discord.PermissionOverwrite(
            view_channel=False,
            send_messages=False
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
            topic="Daily voting for active CSS Solaris games (Mods only - vote tally tracking)",
            overwrites=overwrites
        )
    else:
        # Update permissions on existing voting forum if needed
        if mod_role or bot_member:
            overwrites = {}

            # Hide from @everyone
            overwrites[guild.default_role] = discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False
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
