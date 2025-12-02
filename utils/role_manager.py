"""
Discord role management for CSS Solaris.
Creates and manages Discord roles for game teams.
"""

import discord
from typing import Dict, List


async def create_game_roles(guild: discord.Guild, game_name: str) -> Dict[str, int]:
    """
    Create Discord roles for a game.

    Args:
        guild: Discord guild to create roles in
        game_name: Name of the game

    Returns:
        Dictionary mapping team name to role ID:
        {"crew": role_id, "saboteur": role_id, "dead": role_id}
    """
    # Create Crew role (blue)
    crew_role = await guild.create_role(
        name=f"{game_name} - Crew",
        color=discord.Color.blue(),
        mentionable=False,
        reason=f"CSS Solaris game role for {game_name}"
    )

    # Create Saboteur role (red)
    saboteur_role = await guild.create_role(
        name=f"{game_name} - Saboteur",
        color=discord.Color.red(),
        mentionable=False,
        reason=f"CSS Solaris game role for {game_name}"
    )

    # Create Dead role (dark gray)
    dead_role = await guild.create_role(
        name=f"{game_name} - Dead",
        color=discord.Color.dark_gray(),
        mentionable=False,
        reason=f"CSS Solaris game role for {game_name}"
    )

    return {
        "crew": crew_role.id,
        "saboteur": saboteur_role.id,
        "dead": dead_role.id
    }


async def assign_player_role(guild: discord.Guild, user_id: int, role_id: int) -> bool:
    """
    Add a Discord role to a member.

    Args:
        guild: Discord guild
        user_id: Discord user ID
        role_id: Role ID to assign

    Returns:
        True if role was assigned, False if member or role not found
    """
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
    """
    Remove a Discord role from a member.

    Args:
        guild: Discord guild
        user_id: Discord user ID
        role_id: Role ID to remove

    Returns:
        True if role was removed, False if member or role not found
    """
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
    """
    Delete game roles when game ends.

    Args:
        guild: Discord guild
        role_ids: List of role IDs to delete
    """
    for role_id in role_ids:
        try:
            role = guild.get_role(role_id)
            if role:
                await role.delete(reason="CSS Solaris game ended")
        except Exception:
            # Role might already be deleted or bot lacks permissions
            pass
