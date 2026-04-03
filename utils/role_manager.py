"""
Discord role management for CSS Solaris.
Creates and manages Discord roles for games.
"""

import discord
from typing import Dict, List

# Prefix for all game roles so we can identify them for cleanup
GAME_ROLE_PREFIX = "CSS: "


async def create_game_roles(guild: discord.Guild, game_name: str) -> Dict[str, int]:
    """
    Create Discord roles for a game.
    - "CSS: GameName" - all players (for @mentions and thread permissions)
    - "CSS: GameName Dead" - eliminated players

    Returns:
        {"player": role_id, "dead": role_id}
    """
    player_role = await guild.create_role(
        name=f"{GAME_ROLE_PREFIX}{game_name}",
        color=discord.Color.green(),
        mentionable=True,
        reason=f"CSS Solaris game role for {game_name}"
    )

    dead_role = await guild.create_role(
        name=f"{GAME_ROLE_PREFIX}{game_name} Dead",
        color=discord.Color.dark_gray(),
        mentionable=False,
        reason=f"CSS Solaris dead role for {game_name}"
    )

    return {
        "player": player_role.id,
        "dead": dead_role.id
    }


async def assign_player_role(guild: discord.Guild, user_id: int, role_id: int) -> bool:
    """Add a Discord role to a member."""
    try:
        member = await guild.fetch_member(user_id)
        role = guild.get_role(role_id)
        if not role or not member:
            return False
        await member.add_roles(role, reason="CSS Solaris game role assignment")
        return True
    except Exception:
        return False


async def remove_player_role(guild: discord.Guild, user_id: int, role_id: int) -> bool:
    """Remove a Discord role from a member."""
    try:
        member = await guild.fetch_member(user_id)
        role = guild.get_role(role_id)
        if not role or not member:
            return False
        await member.remove_roles(role, reason="CSS Solaris game role removal")
        return True
    except Exception:
        return False


async def cleanup_game_roles(guild: discord.Guild, role_ids: List[int]):
    """Delete game roles when game ends."""
    for role_id in role_ids:
        try:
            role = guild.get_role(role_id)
            if role:
                await role.delete(reason="CSS Solaris game ended")
        except Exception:
            pass


async def cleanup_all_game_roles(guild: discord.Guild) -> int:
    """Delete ALL CSS Solaris game roles from the server. Returns count deleted."""
    deleted = 0
    for role in guild.roles:
        if role.name.startswith(GAME_ROLE_PREFIX):
            try:
                await role.delete(reason="CSS Solaris purge")
                deleted += 1
            except Exception:
                pass
    return deleted
