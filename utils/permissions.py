"""
Permission utilities for CSS Solaris.
Three-tier role-based system: Admin > Moderator > Player.
"""

import discord
from typing import Optional
from models.game import Game


MODERATOR_ROLE_NAME = "CSS Solaris Moderator"

# Dev admins: can configure the bot (NPC management, server config, permissions)
# but don't automatically get game-level powers unless elevated.
DEV_ADMIN_USERNAMES = ["lorentz", "iron_helmet_games"]


def is_dev_admin(member: discord.Member) -> bool:
    """Check if a member is a hardcoded dev admin (bot configuration access)."""
    if not isinstance(member, discord.Member):
        return False
    return member.name.lower() in DEV_ADMIN_USERNAMES


def is_admin(member: discord.Member) -> bool:
    """Check if a member has admin-level permissions (server admin, manage_guild, or dev_admin)."""
    if not isinstance(member, discord.Member):
        return False
    if is_dev_admin(member):
        return True
    return member.guild_permissions.administrator or member.guild_permissions.manage_guild


def is_moderator(member: discord.Member) -> bool:
    """Check if a member has moderator-level permissions (admin OR CSS Solaris Moderator role)."""
    if not isinstance(member, discord.Member):
        return False
    if is_admin(member):
        return True
    return any(role.name == MODERATOR_ROLE_NAME for role in member.roles)


def can_manage_game(user_id: int, member: discord.Member, game: Game) -> bool:
    """Check if a user can manage a game (game creator, game mod, OR server moderator)."""
    return is_game_creator(user_id, game) or user_id in game.moderators or is_moderator(member)


def can_run_game(user_id: int, game: Game) -> bool:
    """Check if a user can run game actions like /endday, /endnight (creator + game mods only, NOT server admins)."""
    return is_game_creator(user_id, game) or user_id in game.moderators


def is_game_creator(user_id: int, game: Game) -> bool:
    """Check if a user is the creator of a game."""
    return user_id == game.creator_id


def is_player_in_game(user_id: int, game: Game) -> bool:
    """Check if a user is a player in a game."""
    return user_id in game.players


def is_player_alive(user_id: int, game: Game) -> bool:
    """Check if a player is alive in a game."""
    return game.is_player_alive(user_id)


def can_use_say(user_id: int, member: discord.Member, game: Game) -> bool:
    """Check if a user can use /say in a game. Mods always can; players only if enabled."""
    if can_manage_game(user_id, member, game):
        return True
    if is_player_in_game(user_id, game) and game.settings.get("player_say_enabled", False):
        return True
    return False
