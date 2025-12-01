"""
Permission utilities for CSS Solaris.
Handles permission checks for commands.
"""

import discord
from typing import Optional
from models.game import Game


MODERATOR_ROLE_NAME = "CSS Solaris Moderator"


def is_game_creator(user_id: int, game: Game) -> bool:
    """
    Check if a user is the creator of a game.

    Args:
        user_id: Discord user ID
        game: Game object

    Returns:
        True if user is the game creator
    """
    return user_id == game.creator_id


def is_moderator(member: discord.Member) -> bool:
    """
    Check if a member has moderator permissions.

    Args:
        member: Discord Member object

    Returns:
        True if member has moderator permissions
    """
    # Check for administrator or manage_guild permissions
    if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
        return True

    # Check if user has the CSS Solaris Moderator role
    for role in member.roles:
        if role.name == MODERATOR_ROLE_NAME:
            return True

    return False


def can_manage_game(user_id: int, member: discord.Member, game: Game) -> bool:
    """
    Check if a user can manage a game (start, end day, etc.).

    Args:
        user_id: Discord user ID
        member: Discord Member object
        game: Game object

    Returns:
        True if user can manage the game
    """
    return is_game_creator(user_id, game) or is_moderator(member)


def is_player_in_game(user_id: int, game: Game) -> bool:
    """
    Check if a user is a player in a game.

    Args:
        user_id: Discord user ID
        game: Game object

    Returns:
        True if user is in the game
    """
    return user_id in game.players


def is_player_alive(user_id: int, game: Game) -> bool:
    """
    Check if a player is alive in a game.

    Args:
        user_id: Discord user ID
        game: Game object

    Returns:
        True if player is alive
    """
    return game.is_player_alive(user_id)
